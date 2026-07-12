"""
pull.py
Menu Pull: Pull, Fetch, Refresh.
"""

import questionary
from rich.console import Console

from modules.utils import run_git
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


def pull() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    console.print("[cyan]Mengambil (pull) perubahan terbaru dari remote...[/cyan]")
    ok, out, err = run_git(["pull"], cwd=repo, timeout=120)
    if not ok:
        console.print(f"[red]Pull gagal: {_friendly(err)}[/red]")
        log_error("Pull gagal", raw_detail=err)
        return
    console.print(f"[green]Pull berhasil.[/green]\n{out}")
    log_activity("Pull berhasil")


def fetch() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    console.print("[cyan]Mengecek (fetch) info terbaru dari remote...[/cyan]")
    ok, out, err = run_git(["fetch"], cwd=repo, timeout=120)
    if not ok:
        console.print(f"[red]Fetch gagal: {_friendly(err)}[/red]")
        log_error("Fetch gagal", raw_detail=err)
        return
    console.print("[green]Fetch berhasil. Info remote sudah diperbarui.[/green]")
    log_activity("Fetch berhasil")


def refresh() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    ok, out, err = run_git(["status", "-sb"], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal mengambil status: {err}[/red]")
        return
    console.print(out)


def _friendly(err: str) -> str:
    low = err.lower()
    if "could not resolve host" in low or "network" in low:
        return "Tidak dapat terhubung ke internet. Periksa koneksi kamu."
    if "conflict" in low:
        return "Terjadi conflict saat pull. Selesaikan conflict terlebih dahulu."
    if "authentication" in low or "permission denied" in low:
        return "Autentikasi gagal. Periksa username/token/SSH key kamu."
    return err or "Terjadi kesalahan yang tidak diketahui."


def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Pull[/bold cyan]\n"
        "- Pull: mengambil sekaligus menggabungkan perubahan terbaru dari remote.\n"
        "- Fetch: hanya mengecek perubahan di remote tanpa menggabungkannya.\n"
        "- Refresh: menampilkan status terbaru branch dibanding remote.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    while True:
        console.rule("[bold cyan]Pull")
        choice = questionary.select(
            "Pilih aksi:",
            choices=["Pull", "Fetch", "Refresh", "? Help", "Kembali"],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Pull": pull,
                "Fetch": fetch,
                "Refresh": refresh,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Pull", e)
