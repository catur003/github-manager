"""
commit.py
Menu Commit: input pesan commit, tampilkan Commit ID, commit terakhir,
riwayat commit, amend commit.
"""

import questionary
from rich.console import Console
from rich.table import Table

from modules.utils import run_git
from modules.settings import load_config
from modules.logger import log_activity, log_error

console = Console()


def _get_active_repo() -> str | None:
    """Ambil path repository aktif dari config, atau None + pesan kalau belum dipilih."""
    config = load_config()
    repo = config.get("active_repository", "")
    if not repo:
        console.print("[yellow]Repository tidak ditemukan. Silakan pilih repository terlebih dahulu.[/yellow]")
        return None
    return repo


def buat_commit() -> None:
    """Buat commit baru dari perubahan yang sudah di-stage, minta pesan commit."""
    repo = _get_active_repo()
    if not repo:
        return
    ok, staged, _err = run_git(["diff", "--cached", "--name-only"], cwd=repo)
    if not ok or not staged:
        console.print("[yellow]Tidak ada file di staging area. Gunakan menu 'Git Add' terlebih dahulu.[/yellow]")
        return
    pesan = questionary.text("Masukkan pesan commit:").ask()
    if not pesan or not pesan.strip():
        console.print("[yellow]Pesan commit tidak boleh kosong. Dibatalkan.[/yellow]")
        return
    ok, out, err = run_git(["commit", "-m", pesan.strip()], cwd=repo)
    if not ok:
        console.print(f"[red]Commit gagal: {_friendly(err)}[/red]")
        log_error("Commit gagal", raw_detail=err)
        return
    ok2, commit_id, _err = run_git(["rev-parse", "--short", "HEAD"], cwd=repo)
    console.print(f"[green]Commit berhasil.[/green] Commit ID: [bold]{commit_id if ok2 else '-'}[/bold]")
    log_activity(f"Commit berhasil ({commit_id if ok2 else ''})")


def commit_terakhir() -> None:
    """Tampilkan detail commit paling akhir."""
    repo = _get_active_repo()
    if not repo:
        return
    ok, out, err = run_git(["log", "-1", "--pretty=format:%h | %an | %ad | %s", "--date=short"], cwd=repo)
    if not ok or not out:
        console.print("[yellow]Belum ada commit di repository ini.[/yellow]")
        return
    console.print(f"[cyan]Commit terakhir:[/cyan] {out}")


def riwayat_commit() -> None:
    """Tampilkan riwayat beberapa commit terakhir."""
    repo = _get_active_repo()
    if not repo:
        return
    ok, out, err = run_git(["log", "--pretty=format:%h|%an|%ad|%s", "--date=short", "-n", "20"], cwd=repo)
    if not ok or not out:
        console.print("[yellow]Belum ada riwayat commit.[/yellow]")
        return
    table = Table(title="Riwayat Commit (20 terakhir)", header_style="bold cyan")
    table.add_column("ID")
    table.add_column("Author")
    table.add_column("Tanggal")
    table.add_column("Pesan")
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            table.add_row(*parts)
    console.print(table)


def amend_commit() -> None:
    """Ubah (amend) commit terakhir dengan perubahan/pesan baru."""
    repo = _get_active_repo()
    if not repo:
        return
    ok, last, _err = run_git(["log", "-1", "--pretty=%s"], cwd=repo)
    if not ok:
        console.print("[yellow]Belum ada commit untuk di-amend.[/yellow]")
        return
    console.print(f"[dim]Pesan commit terakhir: {last}[/dim]")
    pesan_baru = questionary.text("Masukkan pesan commit baru (kosongkan untuk pakai pesan lama):").ask()
    args = ["commit", "--amend"]
    if pesan_baru and pesan_baru.strip():
        args += ["-m", pesan_baru.strip()]
    else:
        args += ["--no-edit"]
    ok, out, err = run_git(args, cwd=repo)
    if not ok:
        console.print(f"[red]Amend gagal: {_friendly(err)}[/red]")
        log_error("Amend commit gagal", raw_detail=err)
        return
    console.print("[green]Commit terakhir berhasil di-amend.[/green]")
    log_activity("Amend commit berhasil")


def _friendly(err: str) -> str:
    """Ubah pesan error git mentah jadi pesan yang mudah dipahami user."""
    low = err.lower()
    if "nothing to commit" in low:
        return "Tidak ada perubahan untuk di-commit."
    if "please tell me who you are" in low:
        return "Identitas Git belum diatur. Atur Nama dan Email Git di menu Pengaturan."
    return err or "Terjadi kesalahan yang tidak diketahui."


def show_help() -> None:
    """Tampilkan penjelasan singkat untuk menu ini."""
    console.print(
        "\n[bold cyan]Bantuan - Commit[/bold cyan]\n"
        "- Buat Commit: menyimpan perubahan yang sudah di-add dengan sebuah pesan.\n"
        "- Commit Terakhir: menampilkan info commit paling baru.\n"
        "- Riwayat Commit: menampilkan daftar commit sebelumnya.\n"
        "- Amend Commit: mengubah commit terakhir (pesan atau isi).\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    """Tampilkan menu interaktif dan proses pilihan user."""
    while True:
        console.rule("[bold cyan]Commit")
        choice = questionary.select(
            "Pilih aksi:",
            choices=["Buat Commit", "Commit Terakhir", "Riwayat Commit", "Amend Commit", "? Help", "Kembali"],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Buat Commit": buat_commit,
                "Commit Terakhir": commit_terakhir,
                "Riwayat Commit": riwayat_commit,
                "Amend Commit": amend_commit,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Commit", e)
