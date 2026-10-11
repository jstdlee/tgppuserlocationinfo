import json

import pytest
from typer.testing import CliRunner

from tgppuserlocationinfo import DecodeError, decode, decode_location, decode_plmn
from tgppuserlocationinfo.main import app

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


def test_tai_ncgi_2byte_and_3byte_tac():
    c = decode_location("8802f480abcd02f4800123456789").components
    assert c["TAI"]["tac"]["decimal"] == 0xABCD and c["NCGI"]["gnb_id"] == 0x123456
    c = decode_location("8802f480abcdef02f4800123456789").components
    assert c["TAI"]["tac"]["decimal"] == 0xABCDEF and c["TAI"]["tac"]["hex"] == "abcdef"


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


def test_cli_errors():
    r = runner.invoke(app, ["invalidhex"])
    assert r.exit_code == 1 and "Invalid hexadecimal string." in r.stdout
    r = runner.invoke(app, ["8202f480"])
    assert r.exit_code == 1 and "Expected 13 bytes for type 130, got 4" in r.stdout
