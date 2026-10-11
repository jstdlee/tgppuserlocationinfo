import json

import typer

from .decoder import DecodeError, decode_location

app = typer.Typer(add_completion=False)


def decode(hex_string: str, gnb_id_bits: int = 24) -> dict:
    """Decode to a plain dict (JSON friendly). Raises DecodeError."""
    return decode_location(hex_string, gnb_id_bits).to_dict()


def _fail(message: str) -> None:
    """Print a JSON error on stderr and exit 1 (stdout stays empty)."""
    typer.echo(json.dumps({"error": message}, indent=2), err=True)
    raise typer.Exit(code=1)


@app.command()
def decode_location_info(
    hex_string: str = typer.Argument(..., help="hex of 3GPP-User-Location-Info"),
    text: bool = typer.Option(False, "--text", help="human readable output"),
    json_out: bool = typer.Option(False, "--json",
                                  help="JSON output (default); not with --text"),
    gnb_id_bits: int = typer.Option(24, help="gNB ID length (22..32) for NCGI"),
):
    """Decode 3GPP User Location Info (CGI, SAI, RAI, TAI, ECGI, eNodeB, NCGI,
    5GS TAI).

    Result goes to stdout. Errors go to stderr as JSON, exit code 1.
    """
    if text and json_out:
        _fail("--text and --json are mutually exclusive.")
    try:
        info = decode_location(hex_string, gnb_id_bits)
    except DecodeError as e:
        _fail(str(e))
    typer.echo(str(info) if text else info.to_json())


if __name__ == "__main__":
    app()
