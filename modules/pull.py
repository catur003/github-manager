"""
pull.py
Menu Pull: Pull, Fetch, Refresh.
"""

import questionary
from rich.console import Console

from modules.utils import run_git, spinner
from modules.settings import load_config, record_repo_event
from modules.logger import log_activity, log_error
from modules import preflight

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
    # PRIORITAS 1 #2/#1: pre-flight check + auto upstream sebelum pull,
    # supaya user gak pernah lihat "no tracking information" mentah.
    if not preflight.preflight(repo, need_remote=True, need_upstream=True, label="Pull"):
        return
    with spinner("Mengambil (pull) perubahan terbaru dari remote..."):
        ok, out, err = run_git(["pull"], cwd=repo, timeout=120)
    if not ok:
        console.print(f"[red]Pull gagal: {_friendly(err)}[/red]")
        log_error("Pull gagal", raw_detail=err)
        return
    n_commit = out.count("\n") if out else 0
    console.print(f"[green]✓ Pull Berhasil[/green]\n\n{out or 'Sudah paling baru (tidak ada perubahan).'}")
    log_activity("Pull berhasil")
    record_repo_event(repo, "last_pull")
    # PRIORITAS 1 #3: refresh info repo abis pull (branch/remote sinkron lagi)
    run_git(["status", "--short"], cwd=repo)
    run_git(["branch", "-vv"], cwd=repo)
    run_git(["remote", "-v"], cwd=repo)


def fetch() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=True, need_upstream=False, label="Fetch"):
        return
    with spinner("Mengecek (fetch) info terbaru dari remote..."):
        ok, out, err = run_git(["fetch"], cwd=repo, timeout=120)
    if not ok:
        console.print(f"[red]Fetch gagal: {_friendly(err)}[/red]")
        log_error("Fetch gagal", raw_detail=err)
        return
    console.print("[green]✓ Fetch Berhasil.[/green] Info remote sudah diperbarui.")
    log_activity("Fetch berhasil")
    run_git(["status", "--short"], cwd=repo)
    run_git(["branch", "-vv"], cwd=repo)
    run_git(["remote", "-v"], cwd=repo)


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
    if "no tracking information" in low or "no upstream" in low:
        return "Branch belum memiliki upstream. Coba lagi - seharusnya sudah otomatis dihubungkan."
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
