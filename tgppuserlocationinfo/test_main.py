import pytest
from typer.testing import CliRunner
from tgppuserlocationinfo.main import app

runner = CliRunner()

def test_decode_valid_tai_ecgi():
    result = runner.invoke(app, ["8202f480879002f480003a0d21"])
    assert result.exit_code == 0
    output = result.stdout
    assert '"GeoType": 130' in output
    assert '"TAI": {' in output
    assert '"MCC": "204"' in output
    assert '"MNC": "08"' in output
    assert '"Decimal": 34704' in output
    assert '"ECGI": {' in output
    assert '"Decimal": 3804449' in output

def test_decode_valid_5g_tai():
    result = runner.invoke(app, ["8402f480003a"])
    assert result.exit_code == 0
    output = result.stdout
    assert '"GeoType": 132' in output
    assert '"MCC": "204"' in output
    assert '"MNC": "08"' in output
    assert '"Decimal": 58' in output

def test_decode_invalid_hex_string():
    result = runner.invoke(app, ["invalidhex"])
    assert result.exit_code == 1
    output = result.stdout
    assert '"error": "Invalid hexadecimal string."' in output

def test_decode_unsupported_geo_type():
    result = runner.invoke(app, ["9902f4808790"])
    assert result.exit_code == 1
    output = result.stdout
    assert '"error": "Unsupported Geographic Location Type: 153.' in output

def test_decode_incorrect_length():
    result = runner.invoke(app, ["8202f480"])
    assert result.exit_code == 1
    output = result.stdout
    assert '"error": "Expected 13 bytes for type 130, got 4 bytes."' in output