# TGPPUserLocationInfo 🌍

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A Python package for handling and processing user location information with precision and ease.

## references
1. 3GPP TS 29.061, clause 16.4.7.2 (3GPP-User-Location-Info, Rel-19 V19.1.0)
2. 3GPP TS 29.060, clause 7.7.51 (User Location Information, types 0-2)
3. 3GPP TS 29.274, clause 8.21 (CGI, SAI, RAI, TAI, ECGI, eNodeB ID fields)
4. 3GPP TS 38.413, clauses 9.3.1.7 (NR-CGI), 9.3.3.11 (TAI), 9.3.3.5 (PLMN)

## Features

Decodes 3GPP-User-Location-Info (TS 29.061 clause 16.4.7.2, layouts from TS 29.060, TS 29.274 sec 8.21 and TS 38.413 sec 9.3):

| Type | Name | Bytes |
|---|---|---|
| 0 / 1 / 2 | CGI / SAI / RAI (3G, Gn per TS 29.060) | 8 |
| 128 / 129 / 130 | TAI / ECGI / TAI+ECGI (4G) | 6 / 8 / 13 |
| 131 / 132 | eNodeB ID (20 bit) / TAI+eNodeB ID | 7 / 12 |
| 133 / 134 | extended eNodeB ID (21 or 18 bit) / TAI+ext | 7 / 12 |
| 135 | NCGI (PLMN + 36 bit NR Cell Identity) | 9 |
| 136 | 5GS TAI (PLMN + 3-octet TAC) | 7 |
| 137 | 5GS TAI + NCGI | 15 |
| 138 / 139 | NG-RAN Node ID / 5GS TAI + NG-RAN Node ID | not decoded (error) |

Notes:

- PLMN uses BCD digits; MNC digit 3 = 0xF gives a 2-digit MNC.
- The 5GS TAC has 3 octets (TS 38.413 9.3.3.11). Type 136 is the TAI only. The
  TAI and NCGI together is type 137. An old-style 136 value of 14 or 15 bytes
  gives an error with a hint.
- The NR Cell Identity is 36 bits, right aligned in 5 octets. The 4 spare bits
  are the high nibble and must be zero (TS 29.061 / TS 29.274 8.21.5 style;
  also used by sigscale/ocs and cgrates). If the high nibble is not zero, the
  decoder masks it and adds a `warnings` entry. Wireshark's GTPv2 dissector
  masks `0xfffffffff0` (spare in the low nibble), so Wireshark can show a
  different NCI for the same bytes.
- The gNB ID length is not in the attribute: pass `--gnb-id-bits` (22..32, default 24).

```python
from tgppuserlocationinfo import decode_location
info = decode_location("8202f480879002f480003a0d21")   # hex or bytes
print(info)            # human readable
print(info.to_json())  # JSON
info.to_dict()["components"]["ECGI"]["eci"]["decimal"]
```

```bash
python -m tgppuserlocationinfo 8202f480879002f480003a0d21          # JSON (default)
python -m tgppuserlocationinfo 8202f480879002f480003a0d21 --json   # JSON, explicit
python -m tgppuserlocationinfo 8202f480879002f480003a0d21 --text   # human readable
```

`--json` and `--text` are mutually exclusive. The result goes to stdout. An
error goes to stderr as JSON (`{"error": "..."}`) with exit code 1, and stdout
stays empty.

## Verification and SOURCES

Layouts were checked against the ETSI PDFs of TS 38.413 V19.4.0, TS 29.060
V19.0.0, TS 29.061 V19.1.0, TS 29.274 V19.6.0 and TS 23.003 V19.8.0, and
against independent code: Wireshark `packet-gtpv2.c` / `packet-gtp.c`
(types 0-2 and 128-137; 5GS TAC fix for bug 17738), sigscale/ocs
`ocs_log.erl` and cgrates `uli.go` / `uli_test.go`.

Test vectors for types 135-137 (`test_main.py`) come from the cgrates unit
tests (`871300620123456789`, `88130062123456`,
`891300620000011300620000000101`) and from the TAI/NCGI values in a CHF CDR
text dump (type 137, TAC `131150`, NRCI `0000000001`). Types 0-2 and 128-134
use hand-built vectors from the spec figures. No real packet capture (pcap)
with types 135-137 was found: the Wireshark sample captures page lists no such
Diameter, RADIUS, GTPv2 or NGAP capture. These vectors are therefore spec- and
implementation-derived, not captured on a live network.

## 📋 Requirements

This package requires Python 3.12 or later. Dependencies are managed through `pyproject.toml`.


## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📫 Contact

If you have any questions or suggestions, please open an issue in the repository.

---

<div align="center">
Made with ❤️ using Python
</div>