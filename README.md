# TGPPUserLocationInfo 🌍

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A Python package for handling and processing user location information with precision and ease.

## references
1. 3gpp 29061
2. 3gpp 29273

## 🚀 Features

- User location data processing
- Easy-to-use API
- Lightweight and efficient
- Python 3.12+ support

## 📦 Installation

```bash
uv pip install tgppuserlocationinfo
```

## 🖥️ Usage Example


```python
# save this as example.py
from tgppuserlocationinfo import decode

data = "8202f480879002f480003a0d21"
decoded_data = decode(data)
print(f"Decoded Data: {decoded_data}")
```

```bash
python -m tgppuserlocationinfo 8202f480879002f480003a0d21

# or run exe
tgppuserlocationinfo.exe 8202f480879002f480003a0d21
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