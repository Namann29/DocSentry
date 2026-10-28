from hypothesis import given, strategies as st

from app.identifiers import (gstin_checksum, validate_aadhaar, validate_gstin, validate_pan, verhoeff_checksum,
                             verhoeff_valid)

digits11 = st.text(alphabet="0123456789", min_size=11, max_size=11)


@given(digits11)
def test_verhoeff_roundtrip(body):
    assert verhoeff_valid(body + verhoeff_checksum(body))


@given(digits11, st.integers(0, 11), st.integers(1, 9))
def test_verhoeff_detects_every_single_digit_error(body, pos, delta):
    full = body + verhoeff_checksum(body)
    corrupted = full[:pos] + str((int(full[pos]) + delta) % 10) + full[pos + 1:]
    assert corrupted != full
    assert not verhoeff_valid(corrupted)


@given(digits11, st.integers(0, 10))
def test_verhoeff_detects_adjacent_transpositions(body, pos):
    full = body + verhoeff_checksum(body)
    if full[pos] == full[pos + 1]:
        return
    swapped = full[:pos] + full[pos + 1] + full[pos] + full[pos + 2:]
    assert not verhoeff_valid(swapped)


def test_aadhaar_rules():
    body = "23456789012"
    good = body + verhoeff_checksum(body)
    chk = validate_aadhaar(good)
    assert chk.valid_format and chk.checksum_valid and chk.masked == "XXXX XXXX " + good[-4:]
    bad = validate_aadhaar("1" + good[1:])
    assert not bad.valid_format and "First digit" in bad.issues[0]
    assert not validate_aadhaar("1234").valid_format


def test_pan_structure():
    ok = validate_pan("ABCPS1234D")
    assert ok.valid_format and ok.holder_type == "Individual" and ok.surname_initial == "S"
    assert validate_pan("ABCCS1234D").holder_type == "Company"
    assert not validate_pan("ABC1S1234D").valid_format


def test_gstin_checksum_roundtrip():
    body = "09ABCPS1234D1Z"
    g = body + gstin_checksum(body)
    chk = validate_gstin(g)
    assert chk.valid_format and chk.checksum_valid and chk.embedded_pan == "ABCPS1234D" and chk.state_code == "09"
    wrong = g[:-1] + ("A" if g[-1] != "A" else "B")
    assert not validate_gstin(wrong).checksum_valid