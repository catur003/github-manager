"""
gitadd.py
Menu Git Add: Add Semua, Add File Tertentu, Unstage, Refresh.
"""

import questionary
from rich.console import Console
from rich.table import Table

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


def _status_files(repo: str) -> list[tuple[str, str]]:
    ok, out, _err = run_git(["status", "--porcelain"], cwd=repo)
    if not ok or not out:
        return []
    result = []
    for line in out.splitlines():
        code = line[:2]
        path = line[3:]
        result.append((code, path))
    return result


def tampilkan_status(repo: str) -> None:
    files = _status_files(repo)
    if not files:
        console.print("[green]Tidak ada perubahan. Working tree bersih.[/green]")
        return
    table = Table(title="Status Perubahan", header_style="bold cyan")
    table.add_column("Status")
    table.add_column("File")
    for code, path in files:
        table.add_row(code.strip() or "?", path)
    console.print(table)


def add_semua() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    tampilkan_status(repo)
    ok, _out, err = run_git(["add", "-A"], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal menambahkan file: {err}[/red]")
        log_error("Gagal git add -A", raw_detail=err)
        return
    console.print("[green]Semua perubahan berhasil ditambahkan ke staging area.[/green]")
    log_activity("Git Add berhasil (semua file)")


def add_file_tertentu() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    files = _status_files(repo)
    if not files:
        console.print("[green]Tidak ada perubahan untuk ditambahkan.[/green]")
        return
    choices = [path for _code, path in files]
    dipilih = questionary.checkbox("Pilih file yang ingin ditambahkan (spasi untuk pilih):", choices=choices).ask()
    if not dipilih:
        console.print("[yellow]Tidak ada file dipilih.[/yellow]")
        return
    ok, _out, err = run_git(["add", *dipilih], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal menambahkan file: {err}[/red]")
        log_error("Gagal git add file tertentu", raw_detail=err)
        return
    console.print(f"[green]{len(dipilih)} file berhasil ditambahkan ke staging area.[/green]")
    log_activity(f"Git Add berhasil ({len(dipilih)} file)")


def unstage() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    ok, out, _err = run_git(["diff", "--cached", "--name-only"], cwd=repo)
    if not ok or not out:
        console.print("[yellow]Tidak ada file di staging area.[/yellow]")
        return
    staged = out.splitlines()
    dipilih = questionary.checkbox("Pilih file yang ingin di-unstage:", choices=staged + ["Unstage Semua"]).ask()
    if not dipilih:
        return
    if "Unstage Semua" in dipilih:
        ok, _out, err = run_git(["reset"], cwd=repo)
    else:
        ok, _out, err = run_git(["reset", *dipilih], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal unstage: {err}[/red]")
        return
    console.print("[green]Berhasil unstage.[/green]")
    log_activity("Unstage berhasil")


def refresh() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    tampilkan_status(repo)


def git_status_lengkap() -> None:
    """Tampilan lengkap untuk menu 'Git Status' di menu utama:
    Modified, Added, Deleted, Untracked, Ahead, Behind, Clean."""
    repo = _get_active_repo()
    if not repo:
        return
    files = _status_files(repo)
    modified = added = deleted = untracked = 0
    for code, _path in files:
        if code.strip() == "??":
            untracked += 1
        elif "M" in code:
            modified += 1
        elif "A" in code:
            added += 1
        elif "D" in code:
            deleted += 1

    ok, branch, _err = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    branch = branch if ok else "-"
    ahead = behind = 0
    ok, ahead_behind, _err = run_git(
        ["rev-list", "--left-right", "--count", f"{branch}...origin/{branch}"], cwd=repo
    )
    if ok and ahead_behind:
        try:
            left, right = ahead_behind.split()
            ahead, behind = int(left), int(right)
        except ValueError:
            pass

    table = Table(title=f"Git Status - branch '{branch}'", header_style="bold cyan")
    table.add_column("Kategori")
    table.add_column("Jumlah")
    table.add_row("Modified", str(modified))
    table.add_row("Added", str(added))
    table.add_row("Deleted", str(deleted))
    table.add_row("Untracked", str(untracked))
    table.add_row("Ahead", str(ahead))
    table.add_row("Behind", str(behind))
    table.add_row("Clean", "Ya" if not files else "Tidak")
    console.print(table)


def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Git Add[/bold cyan]\n"
        "- Add Semua: menambahkan semua perubahan ke staging area.\n"
        "- Add File Tertentu: memilih file tertentu untuk ditambahkan.\n"
        "- Unstage: membatalkan file dari staging area (belum menghapus perubahan).\n"
        "- Refresh: menampilkan ulang status perubahan terkini.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    while True:
        console.rule("[bold cyan]Git Add")
        choice = questionary.select(
            "Pilih aksi:",
            choices=["Add Semua", "Add File Tertentu", "Unstage", "Refresh", "? Help", "Kembali"],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Add Semua": add_semua,
                "Add File Tertentu": add_file_tertentu,
                "Unstage": unstage,
                "Refresh": refresh,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Git Add", e)
