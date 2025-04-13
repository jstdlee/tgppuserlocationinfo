import typer
import re
import json

app = typer.Typer()

def decode_plmn(plmn_bytes: bytes) -> tuple[str, str]:
    """
    Decode MCC and MNC from a 3-byte PLMN identity.
    - MCC digit 2: bits 8-5 of octet 1
    - MCC digit 1: bits 4-1 of octet 1
    - MCC digit 3: bits 8-5 of octet 2
    - MNC digit 3: bits 4-1 of octet 2
    - MNC digit 2: bits 8-5 of octet 3
    - MNC digit 1: bits 4-1 of octet 3
    """
    if len(plmn_bytes) != 3:
        raise ValueError("PLMN must be 3 bytes")
    octet1, octet2, octet3 = plmn_bytes
    mcc_digit1 = octet1 & 0x0F          # Bits 4-1 of octet 1
    mcc_digit2 = (octet1 >> 4) & 0x0F   # Bits 8-5 of octet 1
    mcc_digit3 = octet2 & 0x0F          # Bits 8-5 of octet 2
    mnc_digit3 = (octet2 >> 4) & 0x0F   # Bits 4-1 of octet 2
    mnc_digit1 = octet3 & 0x0F          # Bits 4-1 of octet 3
    mnc_digit2 = (octet3 >> 4) & 0x0F   # Bits 8-5 of octet 3
    
    mcc = f"{mcc_digit1}{mcc_digit2}{mcc_digit3}"
    # If MNC digit 3 is 0xF, it's a 2-digit MNC; otherwise, 3-digit
    if mnc_digit3 == 0xF:
        mnc = f"{mnc_digit1}{mnc_digit2}"
    else:
        mnc = f"{mnc_digit1}{mnc_digit2}{mnc_digit3}"
    return mcc, mnc

def format_to_utf8(data: bytes) -> str:
    """
    Convert bytes to a UTF-8 string with  escapes for non-printable characters.
    """
    result = []
    for byte in data:
        if 32 <= byte <= 126:  # Printable ASCII range
            result.append(chr(byte))
        else:
            result.append(f"\\x{byte:02x}")
    return "".join(result)

def decode(hex_string: str):
    """
    Decode a 3GPP-User-Location-Info hexadecimal string and output in JSON format.
    
    Supports:
    - CGI (type 128): 7 bytes
    - SAI (type 129): 7 bytes
    - TAI+ECGI (type 130): 13 bytes
    - 5G TAI (type 132): 6 bytes
    
    Handles plain hex strings (e.g., '8202f480879002f480003a0d21') and '0x'-prefixed strings
    (e.g., '0x8202f480879002f480003a0d21'). MCC and MNC are decoded dynamically.

    Outputs:
    - JSON object with TGPPUserLocationInfo and decoded components
    """
    # Remove '0x' prefix if present
    if hex_string.startswith("0x"):
        hex_string = hex_string[2:]
    
    # Remove any separators (spaces, dashes)
    hex_string = re.sub(r"[\s-]", "", hex_string)
    
    # Convert hex string to bytes
    try:
        data = bytes.fromhex(hex_string)
    except ValueError:
        typer.echo(json.dumps({"error": "Invalid hexadecimal string."}, indent=2))
        raise typer.Exit(code=1)
    
    # Check the first byte (Geographic Location Type)
    geo_type = data[0]
    expected_lengths = {
        0: 7,   # CGI
        1: 7,   # SAI  
        2: 7,   # RAI
        128: 7, # TAI
        129: 7, # ECGI 
        130: 13,# TAI and ECGI
        131: 7, # eNodeB ID
        132: 7, # TAI and eNodeB ID
        133: 7, # extended eNodeB ID
        134: 7  # TAI and extended eNodeB ID
    }
    
    if geo_type not in expected_lengths:
        typer.echo(json.dumps({
            "error": f"Unsupported Geographic Location Type: {geo_type}. Supported types: {list(expected_lengths.keys())}"
        }, indent=2))
        raise typer.Exit(code=1)
    
    expected_length = expected_lengths[geo_type]
    if len(data) < expected_length:
        typer.echo(json.dumps({
            "error": f"Expected {expected_length} bytes for type {geo_type}, got {len(data)} bytes."
        }, indent=2))
        raise typer.Exit(code=1)
    
    # Format the entire data into UTF-8 text with \xHH for non-printable chars
    formatted_string = format_to_utf8(data)
    
    # Initialize the result dictionary
    result = {
        "TGPPUserLocationInfo": formatted_string,
        "GeoType": geo_type,
        "DecodedComponents": {}
    }
    
    # Decode based on the type
    if geo_type == 0:  # CGI
        plmn_bytes = data[1:4]
        lac = int.from_bytes(data[4:6], 'big')  # Location Area Code
        ci = int.from_bytes(data[6:8], 'big')   # Cell Identity
        mcc, mnc = decode_plmn(plmn_bytes)
        result["DecodedComponents"]["CGI"] = {
            "Hex": data[1:].hex(),
            "MCC": mcc,
            "MNC": mnc,
            "LAC": {
                "Decimal": lac,
                "Hex": data[4:6].hex()
            },
            "CI": {
                "Decimal": ci,
                "Hex": data[6:8].hex()
            }
        }
    
    elif geo_type == 128:  # TAI
        plmn_bytes = data[1:4]
        lac = int.from_bytes(data[4:6], 'big')
        ci = int.from_bytes(data[6:8], 'big')
        mcc, mnc = decode_plmn(plmn_bytes)
        result["DecodedComponents"]["CGI"] = {
            "Hex": data[1:].hex(),
            "MCC": mcc,
            "MNC": mnc,
            "LAC": {
                "Decimal": lac,
                "Hex": data[4:6].hex()
            },
            "CI": {
                "Decimal": ci,
                "Hex": data[6:8].hex()
            }
        }
    
    elif geo_type == 129:  # SAI
        if len(data) != 7:
            typer.echo(json.dumps({
                "error": f"Expected 7 bytes for SAI, got {len(data)} bytes."
            }, indent=2))
            raise typer.Exit(code=1)
        plmn_bytes = data[1:4]
        lac = int.from_bytes(data[4:6], 'big')
        sac = int.from_bytes(data[6:8], 'big')
        mcc, mnc = decode_plmn(plmn_bytes)
        result["DecodedComponents"]["SAI"] = {
            "Hex": data[1:].hex(),
            "MCC": mcc,
            "MNC": mnc,
            "LAC": {
                "Decimal": lac,
                "Hex": data[4:6].hex()
            },
            "SAC": {
                "Decimal": sac,
                "Hex": data[6:8].hex()
            }
        }
    
    elif geo_type == 1:  # SAI
        plmn_bytes = data[1:4]
        lac = int.from_bytes(data[4:6], 'big')  # Location Area Code
        sac = int.from_bytes(data[6:8], 'big')  # Service Area Code
        mcc, mnc = decode_plmn(plmn_bytes)
        result["DecodedComponents"]["SAI"] = {
            "Hex": data[1:].hex(),
            "MCC": mcc,
            "MNC": mnc,
            "LAC": {
                "Decimal": lac,
                "Hex": data[4:6].hex()
            },
            "SAC": {
                "Decimal": sac,
                "Hex": data[6:8].hex()
            }
        }
    
    elif geo_type == 2:  # RAI
        plmn_bytes = data[1:4]
        lac = int.from_bytes(data[4:6], 'big')  # Location Area Code
        rac = int.from_bytes(data[6:8], 'big')  # Routing Area Code
        mcc, mnc = decode_plmn(plmn_bytes)
        result["DecodedComponents"]["RAI"] = {
            "Hex": data[1:].hex(),
            "MCC": mcc,
            "MNC": mnc,
            "LAC": {
                "Decimal": lac,
                "Hex": data[4:6].hex()
            },
            "RAC": {
                "Decimal": rac,
                "Hex": data[6:8].hex()
            }
        }
    
    elif geo_type == 130:  # TAI and ECGI
        tai_bytes = data[1:6]
        ecgi_bytes = data[6:]
        tai_mcc, tai_mnc = decode_plmn(tai_bytes[:3])
        ecgi_mcc, ecgi_mnc = decode_plmn(ecgi_bytes[:3])
        tai_tac = int.from_bytes(tai_bytes[3:5], 'big')
        ecgi_eci = int.from_bytes(ecgi_bytes[3:], 'big')
        result["DecodedComponents"]["TAI"] = {
            "Hex": tai_bytes.hex(),
            "MCC": tai_mcc,
            "MNC": tai_mnc,
            "TAC": {
                "Decimal": tai_tac,
                "Hex": tai_bytes[3:5].hex()
            }
        }
        result["DecodedComponents"]["ECGI"] = {
            "Hex": ecgi_bytes.hex(),
            "MCC": ecgi_mcc,
            "MNC": ecgi_mnc,
            "ECI": {
                "Decimal": ecgi_eci,
                "Hex": ecgi_bytes[3:].hex()
            }
        }
    
    elif geo_type == 132:  # 5G TAI
        plmn_bytes = data[1:4]
        tac = int.from_bytes(data[4:7], 'big')
        mcc, mnc = decode_plmn(plmn_bytes)
        result["DecodedComponents"]["5G_TAI"] = {
            "Hex": data[1:].hex(),
            "MCC": mcc,
            "MNC": mnc,
            "TAC": {
                "Decimal": tac,
                "Hex": data[4:7].hex()
            }
        }
    
    # Output the result in JSON format
    typer.echo(json.dumps(result, indent=2))
    return 0  # Explicitly return success exit code

@app.command()
def decode_location_info(hex_string: str):
    """
    Command-line interface for decoding 3GPP User Location Info.
    
    Args:
        hex_string (str): Hexadecimal string to decode.
    """
    try:
        decode(hex_string)
    except Exception as e:
        typer.echo(json.dumps({"error": str(e)}, indent=2))
        raise typer.Exit(code=1)
    
if __name__ == "__main__":
    app()