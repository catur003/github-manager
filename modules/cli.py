"""
cli.py
Logic aplikasi utama GitHub Manager (menu utama, routing, flag CLI).

Sengaja dipisah dari github-manager.py di root project supaya jadi SATU
sumber kebenaran yang bisa dipanggil dari dua jalur tanpa duplikasi kode:

1. `python github-manager.py` - jalur Termux/git clone/install.sh (asli).
   github-manager.py di root cuma jadi shim tipis yang import main() dari
   sini.
2. Entry point pip (`console_scripts` di pyproject.toml: github-manager =
   modules.cli:main) - jalur `pip install github-manager` lalu tinggal
   ketik `github-manager` di terminal, tanpa perlu tahu di mana file
   github-manager.py berada.

Kedua jalur pakai fungsi main() yang SAMA persis - kalau ada bugfix di
sini, otomatis berlaku buat kedua cara install, gak perlu disinkronkan
manual di dua tempat.
"""

import sys

import questionary
from rich.console import Console

from modules.utils import ensure_dirs, is_git_repo
from modules.settings import load_config, save_config
from modules.logger import log_activity, log_error, read_recent_activity, read_recent_debug
from modules import banner
import os
from modules import (
    dashboard,
    repository,
    branch,
    upload,
    gitadd,
    commit,
    push,
    pull,
    merge,
    stash,
    rebase,
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
    "9. Stash",
    "10. Rebase",
    "11. Backup",
    "12. Git Status",
    "13. Belajar Git",
    "14. Pengaturan",
    "15. Log Aktivitas",
    "16. Cek Update",
    "17. Log Debug",
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


def _handle_cli_flags() -> bool:
    """Tangani flag command-line simpel (--version/-v, --help/-h) SEBELUM
    masuk ke menu interaktif. Kembalikan True kalau aplikasi harus keluar
    setelah ini (flag ditangani), False kalau lanjut ke menu biasa.
    Sengaja pakai sys.argv manual (bukan argparse) - cuma 2 flag simpel,
    gak perlu dependency/parsing tambahan buat aplikasi menu interaktif."""
    args = sys.argv[1:]
    if any(a in ("--version", "-v") for a in args):
        banner.show_banner()
        return True
    if any(a in ("--help", "-h") for a in args):
        banner.show_banner()
        console.print(
            "\nCara pakai: github-manager\n"
            "Jalankan tanpa argumen untuk masuk ke menu interaktif.\n\n"
            "Opsi:\n"
            "  -v, --version   Tampilkan versi & info aplikasi\n"
            "  -h, --help      Tampilkan bantuan ini\n"
        )
        return True
    return False


def _main_loop() -> None:
    ensure_dirs()
    log_activity("Aplikasi dibuka")

    # Splash banner - HANYA muncul sekali sepanjang umur instalasi ini
    # (lihat modules/banner.py). Ini jaring pengaman yang jalan sama
    # persis baik diinstall lewat pip, npm, maupun git clone manual -
    # karena dipicu oleh RUN PERTAMA aplikasi, bukan oleh installer,
    # banner-nya gak bergantung sama ada/tidaknya post-install hook
    # (pip malah gak punya post-install hook resmi sama sekali - lihat
    # catatan di README/CHANGELOG).
    banner.show_banner_once()

    # Recent Repository logic
    config = load_config()
    active_repo = config.get("active_repository", "")
    if active_repo and is_git_repo(active_repo):
        console.clear()
        use_recent = questionary.confirm(
            f"Repository terakhir: {os.path.basename(active_repo)}\nGunakan kembali?", default=True
        ).ask()
        if use_recent:
            log_activity(f"Melanjutkan dengan repository terakhir: {active_repo}")
        else:
            # Kosongkan repo aktif dan biarkan user memilih repository lain
            # lewat Repository Manager sebelum masuk ke menu utama.
            config["active_repository"] = ""
            save_config(config)
            console.print("[cyan]Silakan pilih repository lain.[/cyan]")
            repository.repository_manager()

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
                repository.repository_manager()  # New Repository Manager
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
                stash.menu()
            elif pilihan.startswith("10."):
                rebase.menu()
            elif pilihan.startswith("11."):
                backup.menu()
            elif pilihan.startswith("12."):
                gitadd.git_status_lengkap()
                questionary.text("\nTekan Enter untuk kembali...").ask()
            elif pilihan.startswith("13."):
                help_module.menu()
            elif pilihan.startswith("14."):
                settings.menu()
            elif pilihan.startswith("15."):
                show_activity_log()
            elif pilihan.startswith("16."):
                update.menu()
            elif pilihan.startswith("17."):
                show_debug_log()
        except KeyboardInterrupt:
            console.print("\n[yellow]Dibatalkan oleh pengguna.[/yellow]")
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke logs/error.log.[/red]")
            log_error("Exception tak tertangani di menu utama", e)


def main() -> None:
    """Entry point tunggal - dipanggil dari github-manager.py (shim) DAN
    dari console_scripts pip. Menangani Ctrl+C di level paling luar supaya
    keluar bersih di kedua jalur."""
    try:
        if _handle_cli_flags():
            sys.exit(0)
        _main_loop()
    except KeyboardInterrupt:
        console.print("\n[cyan]Keluar dari aplikasi.[/cyan]")
        sys.exit(0)
