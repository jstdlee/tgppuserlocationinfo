import typer

from .decoder import DecodeError, decode_location

app = typer.Typer(add_completion=False)


def decode(hex_string: str, gnb_id_bits: int = 24) -> dict:
    """Decode to a plain dict (JSON friendly). Raises DecodeError."""
    return decode_location(hex_string, gnb_id_bits).to_dict()


@app.command()
def decode_location_info(
    hex_string: str = typer.Argument(..., help="hex of 3GPP-User-Location-Info"),
    text: bool = typer.Option(False, "--text", help="human readable output"),
    gnb_id_bits: int = typer.Option(24, help="gNB ID length (22..32) for NCGI"),
):
    """Decode 3GPP User Location Info (CGI, SAI, RAI, TAI, ECGI, eNodeB, NCGI)."""
    import json
    try:
        info = decode_location(hex_string, gnb_id_bits)
    except DecodeError as e:
        typer.echo(json.dumps({"error": str(e)}, indent=2))
        raise typer.Exit(code=1)
    typer.echo(str(info) if text else info.to_json())


if __name__ == "__main__":
    app()
