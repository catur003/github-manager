"""
push.py
Menu Push: Push, Force Push (dengan konfirmasi ketik 'YA'),
penjelasan Apa itu Push / Force Push.
"""

import questionary
from rich.console import Console

from modules.utils import run_git, confirm_text
from modules.settings import load_config
from modules.logger import log_activity, log_error

console = Console()


def _get_active_repo() -> str | None:
    config = load_config()
    repo = config.get("active_repository", "")
    if not repo:
        console.print("[yellow]Repository tidak ditemukan. Silakan pilih repository terlebih dahulu.[/yellow]")
        return None
    return repo


def push() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    ok, branch, _err = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    branch = branch if ok else "HEAD"
    console.print(f"[cyan]Mengirim (push) branch '{branch}' ke remote...[/cyan]")
    ok, out, err = run_git(["push", "origin", branch], cwd=repo, timeout=120)
    if not ok:
        console.print(f"[red]Push gagal: {_friendly(err)}[/red]")
        log_activity("Push gagal")
        log_error("Push gagal", raw_detail=err)
        return
    console.print(f"[green]Push berhasil.[/green]\n{out}")
    log_activity("Push berhasil")


def force_push() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    apa_itu_force_push()
    config = load_config()
    if config.get("konfirmasi_force_push", True):
        console.print("[yellow]Force Push akan MENIMPA riwayat commit di remote. "
                       "Perubahan orang lain bisa hilang jika belum di-pull.[/yellow]")
        setuju = confirm_text("YA", "Ketik 'YA' untuk melanjutkan Force Push:")
        if not setuju:
            console.print("[yellow]Force Push dibatalkan.[/yellow]")
            return
    ok, branch, _err = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    branch = branch if ok else "HEAD"
    ok, out, err = run_git(["push", "--force", "origin", branch], cwd=repo, timeout=120)
    if not ok:
        console.print(f"[red]Force Push gagal: {_friendly(err)}[/red]")
        log_activity("Force Push gagal")
        log_error("Force Push gagal", raw_detail=err)
        return
    console.print(f"[green]Force Push berhasil.[/green]\n{out}")
    log_activity("Force Push berhasil")


def apa_itu_push() -> None:
    console.print(
        "\n[bold cyan]Apa itu Push?[/bold cyan]\n"
        "Push adalah proses mengirim commit dari komputer/HP kamu ke\n"
        "repository di server (misalnya GitHub), agar orang lain juga bisa\n"
        "melihat perubahan yang sudah kamu buat.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def apa_itu_force_push() -> None:
    console.print(
        "\n[bold yellow]Apa itu Force Push?[/bold yellow]\n"
        "Force Push memaksa remote (server) untuk memakai riwayat commit dari\n"
        "komputer/HP kamu, walaupun berbeda dengan riwayat yang sudah ada di\n"
        "server. Ini BERBAHAYA karena bisa menghapus/menimpa commit orang lain\n"
        "yang belum sempat kamu ambil (pull). Gunakan hanya jika benar-benar\n"
        "yakin.\n"
    )


def _friendly(err: str) -> str:
    low = err.lower()
    if "rejected" in low:
        return "Push ditolak oleh remote. Kemungkinan ada perubahan baru di server, coba Pull terlebih dahulu."
    if "could not resolve host" in low or "network" in low:
        return "Tidak dapat terhubung ke internet. Periksa koneksi kamu."
    if "authentication" in low or "permission denied" in low:
        return "Autentikasi gagal. Periksa username/token/SSH key kamu."
    if "no upstream branch" in low or "has no upstream" in low:
        return "Branch ini belum punya remote upstream. Push akan otomatis mengatur upstream saat pertama kali."
    return err or "Terjadi kesalahan yang tidak diketahui."


def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Push[/bold cyan]\n"
        "- Push: mengirim commit lokal ke remote.\n"
        "- Force Push: menimpa riwayat commit di remote (berbahaya, perlu ketik 'YA').\n"
        "- Apa itu Push / Apa itu Force Push: penjelasan konsep.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    while True:
        console.rule("[bold cyan]Push")
        choice = questionary.select(
            "Pilih aksi:",
            choices=["Push", "Force Push", "Apa itu Push", "Apa itu Force Push", "? Help", "Kembali"],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Push": push,
                "Force Push": force_push,
                "Apa itu Push": apa_itu_push,
                "Apa itu Force Push": apa_itu_force_push,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Push", e)
