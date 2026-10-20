"""Pure parsers for 402 responses: x402 (PAYMENT-REQUIRED / body) and MPP
(WWW-Authenticate: Payment). No network, no signing, no keys."""

import base64
import json
import re

TCHAR = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
TOKEN68 = re.compile(r"[A-Za-z0-9\-._~+/]+=*")

MPP_METHODS = ("tempo", "stripe", "evm", "lightning", "solana")
MPP_INTENTS = ("charge", "session", "subscription")

# Header names that look payment-related but are neither PAYMENT-REQUIRED nor
# WWW-Authenticate (those two are parsed structurally).
OTHER_PAYMENT_HEADER = re.compile(
    r"pay|x402|l402|lsat|price|invoice|macaroon|lightning|billing|cost|wallet|settle",
    re.I,
)
KNOWN = {"payment-required", "www-authenticate"}

# Classification labels (kept in Japanese: they are the article's terms).
X402_ONLY = "x402のみ"
MPP_ONLY = "MPPのみ"
DUAL = "両対応"
UNKNOWN_402 = "402だが形式不明"
NOT_402 = "402以外"
ERROR = "エラー"
WRAPPER_EST = "mppxのx402互換ラッパー由来と推定"


def b64_json(s):
    """Decode base64 / base64url (padding optional) into JSON. None on failure."""
    if not isinstance(s, str):
        return None
    t = s.strip().replace("-", "+").replace("_", "/")
    t += "=" * (-len(t) % 4)
    try:
        return json.loads(base64.b64decode(t, validate=False).decode("utf-8"))
    except Exception:
        return None


def _skip(s, i, chars=" \t"):
    while i < len(s) and s[i] in chars:
        i += 1
    return i


def _quoted(s, i):
    # s[i] == '"'
    i += 1
    out = []
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            out.append(s[i + 1])
            i += 2
            continue
        if c == '"':
            return "".join(out), i + 1
        out.append(c)
        i += 1
    return "".join(out), i


def parse_auth_challenges(value):
    """RFC 9110 §11.6.1 challenge list -> [{"scheme": str, "params": {}, "token68": str|None}].

    Handles several challenges in one header value (comma-separated).
    """
    out = []
    cur = None
    s = value or ""
    i = 0
    while i < len(s):
        i = _skip(s, i, " \t,")
        if i >= len(s):
            break
        m = TCHAR.match(s, i)
        if not m:
            i += 1  # garbage; skip a char
            continue
        tok = m.group(0)
        j = _skip(s, m.end())
        is_param = (
            cur is not None
            and j < len(s)
            and s[j] == "="
            and not re.match(r"=*\s*(,|$)", s[j:])
        )
        if is_param:
            j = _skip(s, j + 1)
            if j < len(s) and s[j] == '"':
                val, j = _quoted(s, j)
            else:
                vm = TCHAR.match(s, j)
                val = vm.group(0) if vm else ""
                j = vm.end() if vm else j
            cur["params"][tok.lower()] = val
            i = j
            continue
        # new challenge
        cur = {"scheme": tok, "params": {}, "token68": None}
        out.append(cur)
        i = j
        # optional token68 right after the scheme (e.g. "Basic abc=="), only
        # when it is not the start of a name=value auth-param
        t = TOKEN68.match(s, i)
        if t and re.match(r"\s*(,|$)", s[t.end():]) and not re.match(
            r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+\s*=\s*[^=,\s]", s[i:]
        ):
            cur["token68"] = t.group(0)
            i = t.end()
    return out


def bucket(v, allowed):
    v = (v or "").strip().lower()
    return v if v in allowed else ("other" if v else "missing")


def parse_mpp(www_auth_values):
    """All WWW-Authenticate values -> MPP summary. Only scheme 'Payment' counts as MPP."""
    challenges = []
    other_schemes = []
    for v in www_auth_values:
        for c in parse_auth_challenges(v):
            if c["scheme"].lower() != "payment":
                other_schemes.append(c["scheme"])
                continue
            p = c["params"]
            req = b64_json(p.get("request"))
            d = {
                "id": p.get("id"),
                "realm": p.get("realm"),
                "method": p.get("method"),
                "method_bucket": bucket(p.get("method"), MPP_METHODS),
                "intent": p.get("intent"),
                "intent_bucket": bucket(p.get("intent"), MPP_INTENTS),
                "expires": p.get("expires"),
                "has_digest": "digest" in p,
                "has_opaque": "opaque" in p,
                "request_decoded": req is not None,
                "amount": None,
                "currency": None,
                "recipient": None,
                "chain_id": None,
            }
            if isinstance(req, dict):
                d["amount"] = None if req.get("amount") is None else str(req.get("amount"))
                d["currency"] = req.get("currency")
                d["recipient"] = req.get("recipient")
                md = req.get("methodDetails")
                if isinstance(md, dict):
                    d["chain_id"] = md.get("chainId")
            challenges.append(d)
    return {
        "present": bool(challenges),
        "challenge_count": len(challenges),
        "challenges": challenges,
        "other_auth_schemes": other_schemes,
    }


def _accepts(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get("accepts"), list):
        return []
    out = []
    for a in obj["accepts"]:
        if isinstance(a, dict):
            out.append({"network": a.get("network"), "scheme": a.get("scheme")})
    return out


def parse_x402(payment_required_values, body_text):
    header_present = bool(payment_required_values)
    hdr = b64_json(payment_required_values[0]) if header_present else None
    body = None
    if body_text:
        try:
            body = json.loads(body_text)
        except Exception:
            body = None
    body_version = body.get("x402Version") if isinstance(body, dict) else None
    body_accepts = _accepts(body)
    header_accepts = _accepts(hdr)
    accepts = []
    for a in header_accepts + body_accepts:
        if a not in accepts:
            accepts.append(a)
    body_is_x402 = body_version is not None and bool(body_accepts)
    return {
        "present": header_present or body_is_x402,
        "payment_required_header": header_present,
        "header_decoded": hdr is not None,
        "header_x402Version": hdr.get("x402Version") if isinstance(hdr, dict) else None,
        "body_x402Version": body_version,
        "accepts": accepts,
    }


def other_payment_headers(header_names, other_auth_schemes):
    names = sorted({n.lower() for n in header_names if n.lower() not in KNOWN and OTHER_PAYMENT_HEADER.search(n)})
    names += [f"www-authenticate({s})" for s in sorted(set(other_auth_schemes))]
    return names


def classify(status, x402, mpp):
    """-> (label, wrapper_estimate: bool)."""
    if status is None:
        return ERROR, False
    if status != 402:
        return NOT_402, False
    hx, hm = x402["present"], mpp["present"]
    if hx and hm:
        schemes = {a.get("scheme") for a in x402["accepts"]}
        methods = {c["method_bucket"] for c in mpp["challenges"]}
        return DUAL, ("exact" in schemes and {"tempo", "evm"} <= methods)
    if hx:
        return X402_ONLY, False
    if hm:
        return MPP_ONLY, False
    return UNKNOWN_402, False
