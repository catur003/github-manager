#!/usr/bin/env python3
"""
github-manager.py
Entry point aplikasi GitHub Manager Termux v1.0.

Aplikasi CLI interaktif berbasis Python untuk mengelola Git tanpa perlu
mengingat perintah Git. Dijalankan di Termux Android (tanpa root).
"""

import sys
from pathlib import Path

# Pastikan folder project ada di sys.path agar 'modules' bisa di-import
# dari mana saja aplikasi ini dipanggil (tidak hardcode path).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import questionary  # noqa: E402
from rich.console import Console  # noqa: E402

from modules.utils import ensure_dirs  # noqa: E402
from modules.logger import log_activity, log_error, read_recent_activity, read_recent_debug  # noqa: E402
from modules import (  # noqa: E402
    dashboard,
    repository,
    branch,
    upload,
    gitadd,
    commit,
    push,
    pull,
    merge,
    backup,
    settings,
    update,
    help as help_module,
)

console = Console()

MAIN_MENU_CHOICES = [
    "1. Repository",
    "2. Branch",
    "3. Upload",
    "4. Git Add",
    "5. Commit",
    "6. Push",
    "7. Pull",
    "8. Merge",
    "9. Backup",
    "10. Git Status",
    "11. Belajar Git",
    "12. Pengaturan",
    "13. Log Aktivitas",
    "14. Cek Update",
    "15. Log Debug",
    "0. Keluar",
]


def show_activity_log() -> None:
    console.rule("[bold cyan]Log Aktivitas")
    lines = read_recent_activity(30)
    if not lines:
        console.print("[yellow]Belum ada aktivitas tercatat.[/yellow]")
    else:
        for line in lines:
            console.print(line)
    questionary.text("\nTekan Enter untuk kembali...").ask()


def show_debug_log() -> None:
    """PRIORITAS 7: viewer untuk logs/debug.log (trace perintah git teknis)."""
    console.rule("[bold cyan]Log Debug (teknis)")
    lines = read_recent_debug(30)
    if not lines:
        console.print("[yellow]Belum ada log debug tercatat.[/yellow]")
    else:
        for line in lines:
            console.print(f"[dim]{line}[/dim]")
    questionary.text("\nTekan Enter untuk kembali...").ask()


def main() -> None:
    ensure_dirs()
    log_activity("Aplikasi dibuka")

    while True:
        console.clear()
        dashboard.show_dashboard()

        pilihan = questionary.select(
            "\nMenu Utama - pilih aksi:",
            choices=MAIN_MENU_CHOICES,
        ).ask()

        if pilihan is None or pilihan.startswith("0."):
            console.print("[cyan]Sampai jumpa! Terima kasih sudah menggunakan GitHub Manager.[/cyan]")
            log_activity("Aplikasi ditutup")
            break

        try:
            if pilihan.startswith("1."):
                repository.menu()
            elif pilihan.startswith("2."):
                branch.menu()
            elif pilihan.startswith("3."):
                upload.menu()
            elif pilihan.startswith("4."):
                gitadd.menu()
            elif pilihan.startswith("5."):
                commit.menu()
            elif pilihan.startswith("6."):
                push.menu()
            elif pilihan.startswith("7."):
                pull.menu()
            elif pilihan.startswith("8."):
                merge.menu()
            elif pilihan.startswith("9."):
                backup.menu()
            elif pilihan.startswith("10."):
                gitadd.git_status_lengkap()
                questionary.text("\nTekan Enter untuk kembali...").ask()
            elif pilihan.startswith("11."):
                help_module.menu()
            elif pilihan.startswith("12."):
                settings.menu()
            elif pilihan.startswith("13."):
                show_activity_log()
            elif pilihan.startswith("14."):
                update.menu()
            elif pilihan.startswith("15."):
                show_debug_log()
        except KeyboardInterrupt:
            console.print("\n[yellow]Dibatalkan oleh pengguna.[/yellow]")
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke logs/error.log.[/red]")
            log_error("Exception tak tertangani di menu utama", e)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[cyan]Keluar dari aplikasi.[/cyan]")
        sys.exit(0)
