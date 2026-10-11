"""Decoder for the 3GPP-User-Location-Info attribute (3G / 4G / 5G).

Sources
- TS 29.061 clause 16.4.7.2 (3GPP-User-Location-Info AVP / RADIUS type 22):
  Geographic Location Type values and the layout of the Geographic Location.
- TS 29.274 clauses 8.21.1-8.21.8 (CGI, SAI, RAI, TAI, ECGI, macro eNodeB ID,
  extended macro eNodeB ID) and TS 23.003 clause 2.2 (PLMN BCD digits).
- TS 38.413 clause 9.3.1.7 (NR-CGI, 36-bit NR Cell Identity) and
  TS 38.300 / TS 38.413 clause 9.3.1.6 (gNB ID, 22..32 bits).

For GGSN (Gn) the types 0-2 follow TS 29.060 and have the same layout.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

DEFAULT_GNB_ID_BITS = 24

TYPE_NAMES = {
    0: "CGI",
    1: "SAI",
    2: "RAI",
    128: "TAI",
    129: "ECGI",
    130: "TAI+ECGI",
    131: "eNodeB ID",
    132: "TAI+eNodeB ID",
    133: "extended eNodeB ID",
    134: "TAI+extended eNodeB ID",
    135: "NCGI",
    136: "TAI+NCGI",
}

# Total length in bytes (type octet included). 136 also allows a 3-byte TAC.
_LENGTHS = {0: 8, 1: 8, 2: 8, 128: 6, 129: 8, 130: 13, 131: 7, 132: 12,
            133: 7, 134: 12, 135: 9, 136: (14, 15)}


class DecodeError(ValueError):
    """Raised when the input is not a valid 3GPP-User-Location-Info value."""


@dataclass(frozen=True)
class Plmn:
    mcc: str
    mnc: str

    def __str__(self) -> str:
        return self.mcc + self.mnc


def decode_plmn(raw: bytes) -> Plmn:
    """Decode a 3-byte PLMN (TS 29.274 fig 8.21.1-1).

    Octet 1: MCC2|MCC1, octet 2: MNC3|MCC3, octet 3: MNC2|MNC1.
    MNC digit 3 = 0xF means a 2-digit MNC.
    """
    if len(raw) != 3:
        raise DecodeError("PLMN must be 3 bytes")
    mcc1, mcc2 = raw[0] & 0xF, raw[0] >> 4
    mcc3, mnc3 = raw[1] & 0xF, raw[1] >> 4
    mnc1, mnc2 = raw[2] & 0xF, raw[2] >> 4
    for d in (mcc1, mcc2, mcc3, mnc1, mnc2):
        if d > 9:
            raise DecodeError(f"invalid BCD digit in PLMN {raw.hex()}")
    if mnc3 == 0xF:
        mnc = f"{mnc1}{mnc2}"
    elif mnc3 <= 9:
        mnc = f"{mnc1}{mnc2}{mnc3}"
    else:
        raise DecodeError(f"invalid MNC digit 3 in PLMN {raw.hex()}")
    return Plmn(f"{mcc1}{mcc2}{mcc3}", mnc)


def _field(value: int, raw: bytes) -> dict:
    return {"decimal": value, "hex": raw.hex()}


def _plmn_dict(raw: bytes) -> dict:
    p = decode_plmn(raw)
    return {"mcc": p.mcc, "mnc": p.mnc, "plmn": str(p)}


def _two(name: str, raw: bytes) -> dict:
    """PLMN + one 2-byte code (LAC based types)."""
    return {"hex": raw.hex(), **_plmn_dict(raw[:3]),
            "lac": _field(int.from_bytes(raw[3:5], "big"), raw[3:5])}


def _cgi(raw): d = _two("", raw); d["ci"] = _field(int.from_bytes(raw[5:7], "big"), raw[5:7]); return d
def _sai(raw): d = _two("", raw); d["sac"] = _field(int.from_bytes(raw[5:7], "big"), raw[5:7]); return d
def _rai(raw):
    d = _two("", raw)
    d["rac"] = _field(raw[5], raw[5:6])  # octet c+6 is 0xFF filler
    return d


def _tai(raw: bytes) -> dict:
    """TAI: PLMN + TAC (2 bytes; 3 bytes for 5GS)."""
    tac = raw[3:]
    return {"hex": raw.hex(), **_plmn_dict(raw[:3]),
            "tac": _field(int.from_bytes(tac, "big"), tac)}


def _ecgi(raw: bytes) -> dict:
    eci = int.from_bytes(raw[3:7], "big") & 0x0FFFFFFF  # 4 spare bits
    enb, cell = eci >> 8, eci & 0xFF
    return {"hex": raw.hex(), **_plmn_dict(raw[:3]),
            "eci": _field(eci, raw[3:7]), "enb_id": enb, "cell_id": cell}


def _enb(raw: bytes) -> dict:
    v = int.from_bytes(raw[3:6], "big") & 0x0FFFFF  # 20 bits
    return {"hex": raw.hex(), **_plmn_dict(raw[:3]),
            "enb_id": _field(v, raw[3:6])}


def _xenb(raw: bytes) -> dict:
    v = int.from_bytes(raw[3:6], "big")
    short = bool(v & 0x800000)  # SMeNB flag, bit 8 of octet g+3
    v &= 0x03FFFF if short else 0x1FFFFF  # 18 bit short / 21 bit long
    return {"hex": raw.hex(), **_plmn_dict(raw[:3]),
            "enb_id": _field(v, raw[3:6]), "bits": 18 if short else 21,
            "short": short}


def _ncgi(raw: bytes, gnb_bits: int) -> dict:
    """NCGI: PLMN + NR Cell Identity, 36 bits right aligned in 5 octets."""
    nci = int.from_bytes(raw[3:8], "big") & 0xFFFFFFFFF
    cell_bits = 36 - gnb_bits
    return {"hex": raw.hex(), **_plmn_dict(raw[:3]),
            "nci": _field(nci, raw[3:8]),
            "gnb_id_bits": gnb_bits,
            "gnb_id": nci >> cell_bits,
            "cell_id": nci & ((1 << cell_bits) - 1)}


@dataclass
class LocationInfo:
    geo_type: int
    type_name: str
    raw: bytes
    components: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"geo_type": self.geo_type, "type_name": self.type_name,
                "raw_hex": self.raw.hex(), "components": self.components}

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def __str__(self) -> str:
        lines = [f"{self.type_name} (type {self.geo_type})"]
        for name, c in self.components.items():
            parts = [f"{k}={v['decimal'] if isinstance(v, dict) else v}"
                     for k, v in c.items() if k != "hex"]
            lines.append(f"  {name}: " + " ".join(parts))
        return "\n".join(lines)


def to_bytes(data: str | bytes | bytearray) -> bytes:
    """Accept bytes or a hex string ('0x' prefix, spaces, dashes, colons ok)."""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    s = re.sub(r"[\s:-]", "", data)
    if s[:2].lower() == "0x":
        s = s[2:]
    try:
        return bytes.fromhex(s)
    except ValueError as e:
        raise DecodeError("Invalid hexadecimal string.") from e


def decode_location(data: str | bytes, gnb_id_bits: int = DEFAULT_GNB_ID_BITS
                    ) -> LocationInfo:
    """Decode a 3GPP-User-Location-Info value (type octet + location).

    gnb_id_bits (22..32) only affects the gNB ID / cell split of an NCGI;
    the length is not carried in the attribute, so the operator must supply it.
    """
    if not 22 <= gnb_id_bits <= 32:
        raise DecodeError("gnb_id_bits must be 22..32")
    raw = to_bytes(data)
    if not raw:
        raise DecodeError("Empty input.")
    t = raw[0]
    if t not in _LENGTHS:
        raise DecodeError(f"Unsupported Geographic Location Type: {t}. "
                          f"Supported types: {sorted(_LENGTHS)}")
    exp = _LENGTHS[t]
    allowed = exp if isinstance(exp, tuple) else (exp,)
    if len(raw) not in allowed:
        raise DecodeError(f"Expected {' or '.join(map(str, allowed))} bytes "
                          f"for type {t}, got {len(raw)} bytes.")
    b = raw[1:]
    c: dict = {}
    if t == 0: c["CGI"] = _cgi(b)
    elif t == 1: c["SAI"] = _sai(b)
    elif t == 2: c["RAI"] = _rai(b)
    elif t == 128: c["TAI"] = _tai(b)
    elif t == 129: c["ECGI"] = _ecgi(b)
    elif t == 130: c["TAI"], c["ECGI"] = _tai(b[:5]), _ecgi(b[5:])
    elif t == 131: c["eNodeB"] = _enb(b)
    elif t == 132: c["TAI"], c["eNodeB"] = _tai(b[:5]), _enb(b[5:])
    elif t == 133: c["eNodeB"] = _xenb(b)
    elif t == 134: c["TAI"], c["eNodeB"] = _tai(b[:5]), _xenb(b[5:])
    elif t == 135: c["NCGI"] = _ncgi(b, gnb_id_bits)
    elif t == 136:
        tai_len = len(b) - 8  # 5 (2-byte TAC) or 6 (3-byte 5GS TAC)
        c["TAI"], c["NCGI"] = _tai(b[:tai_len]), _ncgi(b[tai_len:], gnb_id_bits)
    return LocationInfo(t, TYPE_NAMES[t], raw, c)
