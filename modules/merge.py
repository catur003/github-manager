"""
merge.py
Menu Merge: Merge Lokal (pilih source & target branch, konfirmasi,
tampilkan conflict, jika berhasil tawarkan hapus branch source).
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


def _list_branches(repo: str) -> list[str]:
    ok, out, _err = run_git(["branch", "--list"], cwd=repo)
    if not ok or not out:
        return []
    return [line.replace("*", "").strip() for line in out.splitlines() if line.strip()]


def merge_lokal() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    branches = _list_branches(repo)
    if len(branches) < 2:
        console.print("[yellow]Minimal harus ada 2 branch untuk melakukan merge.[/yellow]")
        return

    source = questionary.select("Pilih Source Branch (yang akan digabung):", choices=branches + ["Batal"]).ask()
    if not source or source == "Batal":
        return
    target_choices = [b for b in branches if b != source] + ["Batal"]
    target = questionary.select("Pilih Target Branch (tujuan penggabungan):", choices=target_choices).ask()
    if not target or target == "Batal":
        return

    console.print(f"[cyan]Akan menggabungkan '{source}' ke dalam '{target}'.[/cyan]")
    yakin = questionary.confirm("Lanjutkan merge?", default=True).ask()
    if not yakin:
        console.print("[yellow]Dibatalkan.[/yellow]")
        return

    ok, _out, err = run_git(["checkout", target], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal pindah ke branch target: {err}[/red]")
        return

    ok, out, err = run_git(["merge", source], cwd=repo)
    if not ok:
        if "conflict" in (out + err).lower():
            console.print("[red]Terjadi CONFLICT saat merge. Merge dihentikan.[/red]")
            ok2, status_out, _err2 = run_git(["status"], cwd=repo)
            if ok2:
                console.print(status_out)
            console.print("[yellow]Selesaikan conflict secara manual, lalu lakukan Git Add dan Commit.[/yellow]")
            log_activity(f"Merge {source} ke {target} gagal - conflict")
            log_error("Merge conflict", raw_detail=err)
            return
        console.print(f"[red]Merge gagal: {err}[/red]")
        log_error("Merge gagal", raw_detail=err)
        return

    console.print(f"[green]Merge berhasil.[/green]\n{out}")
    log_activity(f"Merge {source} ke {target} berhasil")

    hapus = questionary.confirm(f"Merge berhasil. Hapus branch '{source}' sekarang?", default=False).ask()
    if hapus:
        ok, _out, err = run_git(["branch", "-d", source], cwd=repo)
        if not ok:
            console.print(f"[red]Gagal menghapus branch: {err}[/red]")
            return
        console.print(f"[green]Branch '{source}' berhasil dihapus.[/green]")
        log_activity(f"Branch {source} dihapus setelah merge")


def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Merge[/bold cyan]\n"
        "Merge Lokal menggabungkan isi Source Branch ke dalam Target Branch.\n"
        "Jika terjadi conflict, proses akan dihentikan agar kamu bisa\n"
        "menyelesaikannya secara manual. Jika berhasil, kamu bisa memilih\n"
        "untuk langsung menghapus branch sumber.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    while True:
        console.rule("[bold cyan]Merge")
        choice = questionary.select(
            "Pilih aksi:",
            choices=["Merge Lokal", "? Help", "Kembali"],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            if choice == "Merge Lokal":
                merge_lokal()
            elif choice == "? Help":
                show_help()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Merge", e)
