#!/usr/bin/env python3
"""
github-manager.py
Entry point aplikasi GitHub Manager - jalur Termux/git clone/install.sh.

File ini SENGAJA cuma jadi shim tipis. Logic aplikasi sebenarnya ada di
modules/cli.py, supaya jalur ini (`python github-manager.py`) dan jalur
pip (`console_scripts` entry point: github-manager = modules.cli:main)
sama-sama manggil fungsi yang PERSIS SAMA - gak ada logic yang perlu
disinkronkan manual di dua tempat.
"""

import sys
from pathlib import Path

# Pastikan folder project ada di sys.path agar 'modules' bisa di-import
# dari mana saja aplikasi ini dipanggil (tidak hardcode path). Kalau
# diinstall lewat pip, langkah ini gak diperlukan lagi (modules jadi
# package yang sudah ke-install di site-packages), tapi tetap aman untuk
# dijalankan - cuma nambahin folder project ke urutan pencarian import.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from modules.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
