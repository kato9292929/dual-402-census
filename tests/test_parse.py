import base64
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from census import parse as P  # noqa: E402

FX = pathlib.Path(__file__).parent / "fixtures"


def b64u(o):
    return base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip("=")


def load_http(stem):
    names, vals = [], {}
    for ln in (FX / f"{stem}.headers").read_text().splitlines():
        if ":" not in ln or ln.startswith("HTTP/"):
            continue
        k, v = ln.split(":", 1)
        names.append(k.strip())
        vals.setdefault(k.strip().lower(), []).append(v.strip())
    return names, vals, (FX / f"{stem}.body").read_text()


def test_exa_live_dual_402():
    names, vals, body = load_http("exa_search_post.redacted")
    x = P.parse_x402(vals.get("payment-required", []), body)
    m = P.parse_mpp(vals.get("www-authenticate", []))
    assert x["present"] and x["payment_required_header"] and x["header_decoded"]
    assert x["body_x402Version"] == 2 and x["header_x402Version"] == 2
    nets = {a["network"] for a in x["accepts"]}
    assert "eip155:8453" in nets and any(n.startswith("solana:") for n in nets)
    assert m["challenge_count"] == 1
    c = m["challenges"][0]
    assert (c["method"], c["intent"]) == ("tempo", "charge")
    assert c["amount"] == "7000" and c["chain_id"] == 4217
    assert c["currency"].lower().startswith("0x20c0")
    assert c["recipient"].endswith("dbC") and c["expires"] and c["has_opaque"]
    label, wrap = P.classify(402, x, m)
    assert label == P.DUAL and wrap is False  # tempo only, no evm challenge


def test_multiple_challenges_one_header_and_wrapper_estimate():
    r1 = b64u({"amount": "1000", "currency": "0xabc", "recipient": "0x1111"})
    r2 = b64u({"amount": "1000", "currency": "0xdef", "recipient": "0x2222", "methodDetails": {"chainId": 8453}})
    hdr = (
        f'Payment id="a", realm="r", method="tempo", intent="charge", request="{r1}", expires="2030-01-01T00:00:00Z", '
        f'Payment id="b", realm="r", method="evm", intent="charge", request="{r2}"'
    )
    m = P.parse_mpp([hdr])
    assert m["challenge_count"] == 2
    assert [c["method"] for c in m["challenges"]] == ["tempo", "evm"]
    assert m["challenges"][1]["chain_id"] == 8453
    x = P.parse_x402([], json.dumps({"x402Version": 1, "accepts": [{"scheme": "exact", "network": "base"}]}))
    assert P.classify(402, x, m) == (P.DUAL, True)


def test_multiple_headers_and_other_schemes():
    m = P.parse_mpp(['Bearer realm="api"', 'Payment id="x", method="stripe", intent="session", request="!!notb64"', "L402 macaroon=\"m\", invoice=\"lnbc1\""])
    assert m["challenge_count"] == 1
    c = m["challenges"][0]
    assert c["method_bucket"] == "stripe" and c["intent_bucket"] == "session" and c["request_decoded"] is False
    assert m["other_auth_schemes"] == ["Bearer", "L402"]
    assert P.classify(402, P.parse_x402([], "{}"), m) == (P.MPP_ONLY, False)
    assert P.other_payment_headers(["X-Price", "Content-Type", "PAYMENT-REQUIRED"], m["other_auth_schemes"]) == [
        "x-price", "www-authenticate(Bearer)", "www-authenticate(L402)"]


def test_token68_and_unknown_buckets():
    cs = P.parse_auth_challenges('Basic YWxhZGRpbjpvcGVuc2VzYW1l, Payment method="lightning", intent="weird"')
    assert cs[0]["scheme"] == "Basic" and cs[0]["token68"] == "YWxhZGRpbjpvcGVuc2VzYW1l"
    m = P.parse_mpp(['Payment method="foo", intent="weird"'])
    assert m["challenges"][0]["method_bucket"] == "other" and m["challenges"][0]["intent_bucket"] == "other"


def test_x402_header_only_and_unknown_and_non402():
    hdr = base64.b64encode(json.dumps({"x402Version": 2, "accepts": [{"scheme": "exact", "network": "solana:5eyk"}]}).encode()).decode()
    x = P.parse_x402([hdr], "")
    assert x["present"] and x["header_x402Version"] == 2 and x["body_x402Version"] is None
    assert P.classify(402, x, P.parse_mpp([])) == (P.X402_ONLY, False)
    empty = P.parse_x402([], "<html>pay up</html>")
    assert P.classify(402, empty, P.parse_mpp([])) == (P.UNKNOWN_402, False)
    assert P.classify(200, x, P.parse_mpp([]))[0] == P.NOT_402
    assert P.classify(None, empty, P.parse_mpp([]))[0] == P.ERROR
