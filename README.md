# TGPPUserLocationInfo 🌍

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A Python package for handling and processing user location information with precision and ease.

## references
1. 3GPP TS 29.061, clause 16.4.7.2 (3GPP-User-Location-Info)
2. 3GPP TS 29.274, clause 8.21 (CGI, SAI, RAI, TAI, ECGI, eNodeB ID fields)
3. 3GPP TS 38.413, clause 9.3.1.7 (NR-CGI)

## Features

Decodes 3GPP-User-Location-Info (TS 29.061 clause 16.4.7.2, layouts from TS 29.274 sec 8.21 and TS 38.413 sec 9.3.1.7):

| Type | Name | Bytes |
|---|---|---|
| 0 / 1 / 2 | CGI / SAI / RAI (3G, Gn per TS 29.060) | 8 |
| 128 / 129 / 130 | TAI / ECGI / TAI+ECGI (4G) | 6 / 8 / 13 |
| 131 / 132 | eNodeB ID (20 bit) / TAI+eNodeB ID | 7 / 12 |
| 133 / 134 | extended eNodeB ID (21 or 18 bit) / TAI+ext | 7 / 12 |
| 135 / 136 | NCGI (36 bit NCI) / TAI+NCGI (5G) | 9 / 14 (15 with 3-byte 5GS TAC) |

PLMN uses BCD digits; MNC digit 3 = 0xF gives a 2-digit MNC. The gNB ID length is not in the attribute: pass `--gnb-id-bits` (22..32, default 24).

```python
from tgppuserlocationinfo import decode_location
info = decode_location("8202f480879002f480003a0d21")   # hex or bytes
print(info)            # human readable
print(info.to_json())  # JSON
info.to_dict()["components"]["ECGI"]["eci"]["decimal"]
```

```bash
python -m tgppuserlocationinfo 8202f480879002f480003a0d21 --text
```

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