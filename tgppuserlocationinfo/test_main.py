import json

import pytest
from typer.testing import CliRunner

from tgppuserlocationinfo import DecodeError, decode, decode_location, decode_plmn
from tgppuserlocationinfo.main import app

try:  # Click < 8.2 mixes stderr into stdout unless told otherwise
    runner = CliRunner(mix_stderr=False)
except TypeError:  # Click >= 8.2 always keeps them apart
    runner = CliRunner()


def test_plmn_two_digit():
    assert (decode_plmn(bytes.fromhex("02f480")).mcc,
            decode_plmn(bytes.fromhex("02f480")).mnc) == ("204", "08")


def test_plmn_three_digit():
    # MCC 310, MNC 410: 13 | 0 | 14 -> octets 13 01? MCC2=1,MCC1=3 -> 0x13;
    # MNC3=0,MCC3=0 -> 0x00; MNC2=1,MNC1=4 -> 0x14
    p = decode_plmn(bytes.fromhex("130014"))
    assert (p.mcc, p.mnc) == ("310", "410")


def test_plmn_invalid():
    with pytest.raises(DecodeError):
        decode_plmn(bytes.fromhex("0af480"))


def test_cgi():
    r = decode_location("0002f4800102" + "0304").components["CGI"]
    assert r["plmn"] == "20408"
    assert r["lac"]["decimal"] == 0x0102 and r["ci"]["decimal"] == 0x0304


def test_sai():
    r = decode_location("0102f48012345678").components["SAI"]
    assert r["lac"]["decimal"] == 0x1234 and r["sac"]["decimal"] == 0x5678


def test_rai_ff_filler():
    r = decode_location("0202f48012342aff").components["RAI"]
    assert r["rac"]["decimal"] == 0x2A


def test_tai_2digit_and_3digit():
    r = decode_location("8002f4808790").components["TAI"]
    assert r["tac"]["decimal"] == 34704 and r["mnc"] == "08"
    r = decode_location("80130014abcd").components["TAI"]
    assert r["mnc"] == "410" and r["tac"]["hex"] == "abcd"


def test_ecgi_28_bits_spare_ignored():
    # first nibble 0xF is spare; ECI = 0x1234567
    r = decode_location("8102f480f1234567").components["ECGI"]
    assert r["eci"]["decimal"] == 0x1234567
    assert r["enb_id"] == 0x12345 and r["cell_id"] == 0x67


def test_tai_ecgi_example():
    info = decode("8202f480879002f480003a0d21")
    c = info["components"]
    assert info["geo_type"] == 130 and c["TAI"]["tac"]["decimal"] == 34704
    assert c["ECGI"]["eci"]["decimal"] == 3804449


def test_enodeb_20_bits():
    r = decode_location("8302f480f12345").components["eNodeB"]
    assert r["enb_id"]["decimal"] == 0x12345


def test_tai_enodeb():
    c = decode_location("8402f4808790" + "02f480012345").components
    assert c["TAI"]["tac"]["decimal"] == 0x8790
    assert c["eNodeB"]["enb_id"]["decimal"] == 0x12345


def test_extended_enodeb_long_and_short():
    long = decode_location("8502f4801fffff").components["eNodeB"]
    assert (long["bits"], long["enb_id"]["decimal"]) == (21, 0x1FFFFF)
    short = decode_location("8502f48083ffff").components["eNodeB"]
    assert short["short"] and short["bits"] == 18
    assert short["enb_id"]["decimal"] == 0x3FFFF


def test_tai_extended_enodeb():
    c = decode_location("8602f480000102f480000001").components
    assert c["TAI"]["tac"]["decimal"] == 1 and c["eNodeB"]["enb_id"]["decimal"] == 1


def test_ncgi_gnb_split():
    # NCI = 0x123456789 (36 bits); 24-bit gNB ID = 0x123456, cell 0x789
    r = decode_location("8702f4800123456789").components["NCGI"]
    assert r["nci"]["decimal"] == 0x123456789
    assert (r["gnb_id"], r["cell_id"]) == (0x123456, 0x789)
    r = decode_location("8702f4800123456789", gnb_id_bits=32).components["NCGI"]
    assert (r["gnb_id"], r["cell_id"]) == (0x12345678, 0x9)


def test_5gs_tai_3byte_tac():
    # Type 136 = 5GS TAI only: PLMN + 3-octet TAC (TS 29.061, TS 38.413 9.3.3.11)
    r = decode_location("8802f480abcdef")
    assert r.type_name == "5GS TAI" and list(r.components) == ["TAI"]
    tac = r.components["TAI"]["tac"]
    assert tac == {"decimal": 0xABCDEF, "hex": "abcdef"}


def test_5gs_tai_and_ncgi():
    # Type 137: TAI (3-byte TAC) then NCGI
    r = decode_location("8902f480abcdef02f4800123456789")
    assert r.type_name == "5GS TAI+NCGI"
    assert r.components["TAI"]["tac"]["decimal"] == 0xABCDEF
    n = r.components["NCGI"]
    assert n["nci"]["decimal"] == 0x123456789 and n["gnb_id"] == 0x123456
    assert not r.warnings


@pytest.mark.parametrize("h,frag", [
    ("8802f480abcd02f4800123456789", "TAI and NCGI is type 137"),  # old 136 layout
    ("8802f480abcdef02f4800123456789", "TAI and NCGI is type 137"),
    ("8802f480abcd", "Expected 7 bytes for type 136"),
    ("8902f480abcd02f4800123456789", "Expected 15 bytes for type 137"),
    ("8a0e12", "not supported"),   # 138 NG-RAN Node ID
    ("8b0e12", "not supported"),   # 139 5GS TAI + NG-RAN Node ID
])
def test_5g_type_errors(h, frag):
    with pytest.raises(DecodeError, match=frag):
        decode_location(h)


def test_ncgi_spare_nibble_warning():
    # Spare bits must be zero. A set high nibble is masked and flagged,
    # because Wireshark reads the spare bits in the low nibble instead.
    r = decode_location("8702f480f123456789")
    assert r.components["NCGI"]["nci"]["decimal"] == 0x123456789
    assert len(r.warnings) == 1 and "spare" in r.warnings[0]
    assert json.loads(r.to_json())["warnings"] == r.warnings
    assert "warning:" in str(r)
    assert "warnings" not in decode_location("8702f4800123456789").to_dict()


# Regression vectors from independent implementations / data (see SOURCES in
# the README). No real packet capture with types 135-137 was found.
@pytest.mark.parametrize("h,check", [
    # sigscale/ocs ocs_log.erl layout + cgrates uli_test.go vectors
    ("871300620123456789", lambda c: c["NCGI"]["nci"]["decimal"] == 0x123456789
        and (c["NCGI"]["mcc"], c["NCGI"]["mnc"]) == ("310", "260")),
    ("88130062123456", lambda c: c["TAI"]["tac"]["decimal"] == 0x123456),
    ("891300620000011300620000000101", lambda c: c["TAI"]["tac"]["decimal"] == 1
        and c["NCGI"]["nci"]["decimal"] == 257),
    # CHF CDR text dump (cdr1.txt): TAI 640/001 TAC H'131150, NCGI NRCI H'0000000001
    ("894610001311504610000000000001", lambda c: c["TAI"]["tac"]["decimal"] == 0x131150
        and (c["TAI"]["mcc"], c["TAI"]["mnc"]) == ("640", "001")
        and c["NCGI"]["nci"]["decimal"] == 1),
], ids=["ncgi-cgrates", "5gs-tai-cgrates", "5gs-tai-ncgi-cgrates", "5gs-tai-ncgi-cdr"])
def test_5g_regression_vectors(h, check):
    r = decode_location(h)
    assert check(r.components) and not r.warnings


def test_bytes_and_prefix_input():
    assert decode_location(bytes.fromhex("8002f4808790")).geo_type == 128
    assert decode_location("0x80 02f4-808790").geo_type == 128


def test_json_and_text():
    info = decode_location("8002f4808790")
    assert json.loads(info.to_json())["type_name"] == "TAI"
    assert "tac=34704" in str(info)


@pytest.mark.parametrize("h", ["", "99" + "00" * 6, "8202f480", "zz"])
def test_errors(h):
    with pytest.raises(DecodeError):
        decode_location(h)


def test_cli_json_and_text():
    r = runner.invoke(app, ["8202f480879002f480003a0d21"])
    assert r.exit_code == 0 and '"geo_type": 130' in r.stdout
    r = runner.invoke(app, ["8202f480879002f480003a0d21", "--text"])
    assert "TAI+ECGI" in r.stdout
    r = runner.invoke(app, ["8202f480879002f480003a0d21", "--json"])
    assert r.exit_code == 0 and json.loads(r.stdout)["geo_type"] == 130
    assert r.stdout == runner.invoke(app, ["8202f480879002f480003a0d21"]).stdout
    assert r.stderr == ""


def test_cli_text_json_exclusive():
    r = runner.invoke(app, ["8002f4808790", "--text", "--json"])
    assert r.exit_code == 1 and r.stdout == ""
    assert "mutually exclusive" in json.loads(r.stderr)["error"]


def test_cli_errors():
    r = runner.invoke(app, ["invalidhex"])
    assert r.exit_code == 1 and r.stdout == ""
    assert json.loads(r.stderr)["error"] == "Invalid hexadecimal string."
    r = runner.invoke(app, ["8202f480"])
    assert r.exit_code == 1 and r.stdout == ""
    assert "Expected 13 bytes for type 130, got 4" in json.loads(r.stderr)["error"]


# Vectors built by hand from TS 29.274 figs 8.21.1-1 .. 8.21.8-1 (octet 1 = MCC2|MCC1,
# octet 2 = MNC3|MCC3, octet 3 = MNC2|MNC1).
@pytest.mark.parametrize("hexplmn,mcc,mnc", [
    ("130062", "310", "260"),   # 3-digit MNC
    ("64f000", "460", "00"),    # 2-digit MNC with leading zero
    ("00f110", "001", "01"),    # leading-zero MCC, 2-digit MNC
    ("42f210", "242", "01"),
    ("32f504", "235", "40"),    # 3GPP example: MCC 235 MNC 40
])
def test_plmn_hand_vectors(hexplmn, mcc, mnc):
    p = decode_plmn(bytes.fromhex(hexplmn))
    assert (p.mcc, p.mnc) == (mcc, mnc)


def test_mnc_three_digits_keeps_leading_zero():
    # MCC 234, MNC 015: MCC2|MCC1=0x32, MNC3|MCC3=0x54, MNC2|MNC1=0x10
    p = decode_plmn(bytes([(3 << 4) | 2, (5 << 4) | 4, (1 << 4) | 0]))
    assert (p.mcc, p.mnc) == ("234", "015")


def test_ecgi_hand_built_bit_layout():
    # ECI = 28 bits starting at bit 4 of octet e+3: octets 0x0A 0xBC 0xDE 0xF1
    r = decode_location("8102f4800abcdef1").components["ECGI"]
    assert r["eci"]["decimal"] == 0xABCDEF1
    assert (r["enb_id"], r["cell_id"]) == (0xABCDE, 0xF1)


def test_extended_enodeb_spare_bits_ignored():
    # long: bit 8 = 0, bits 7-6 spare (set), 21 bit value 0x0AAAAA
    r = decode_location("8502f480" + "6aaaaa").components["eNodeB"]
    assert (r["bits"], r["enb_id"]["decimal"]) == (21, 0x0AAAAA)
    # short: SMeNB=1, bits 5-3 junk (ignored), 18 bit value 0x2AAAA
    r = decode_location("8502f480" + "bd" + "aaaa").components["eNodeB"]
    assert (r["bits"], r["enb_id"]["decimal"]) == (18, 0x1AAAA)


@pytest.mark.parametrize("h", ["0x8002f4808790", "0X80 02 F4 80 87 90",
                               "80:02:f4:80:87:90", " 80-02-f4-80-87-90\n"])
def test_hex_input_forms(h):
    assert decode_location(h).components["TAI"]["tac"]["decimal"] == 0x8790


@pytest.mark.parametrize("h", ["8002f480879", "0x", "   ", "8002f48087900", "8002f480879000"])
def test_hex_input_rejected(h):
    with pytest.raises(DecodeError):
        decode_location(h)


def test_too_long_and_bytearray():
    with pytest.raises(DecodeError):
        decode_location("8202f480879002f480003a0d2100")
    assert decode_location(bytearray.fromhex("8002f4808790")).geo_type == 128


def test_gnb_id_bits_bounds():
    for bad in (21, 33):
        with pytest.raises(DecodeError):
            decode_location("8702f4800123456789", gnb_id_bits=bad)
    r = decode_location("8702f4800123456789", gnb_id_bits=22).components["NCGI"]
    assert (r["gnb_id"], r["cell_id"]) == (0x123456789 >> 14, 0x123456789 & 0x3FFF)


def test_cli_gnb_bits_and_exit_codes():
    r = runner.invoke(app, ["8702f4800123456789", "--gnb-id-bits", "32"])
    assert r.exit_code == 0 and json.loads(r.stdout)["components"]["NCGI"]["gnb_id"] == 0x12345678
    r = runner.invoke(app, ["8702f4800123456789", "--gnb-id-bits", "21"])
    assert r.exit_code == 1 and r.stdout == "" and "gnb_id_bits" in r.stderr
    r = runner.invoke(app, [""])
    assert r.exit_code == 1 and r.stdout == "" and "Empty input" in r.stderr
