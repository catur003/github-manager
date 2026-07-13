"""
branch.py
Menu Branch: lihat, checkout, buat, rename, delete, refresh.
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


def _list_branches(repo: str) -> list[str]:
    """Ambil daftar nama branch lokal di repository."""
    ok, out, _err = run_git(["branch", "--list"], cwd=repo)
    if not ok or not out:
        return []
    branches = []
    for line in out.splitlines():
        name = line.replace("*", "").strip()
        if name:
            branches.append(name)
    return branches


def lihat_branch() -> None:
    """Tampilkan daftar branch lokal beserta penanda branch aktif."""
    repo = _get_active_repo()
    if not repo:
        return
    ok, out, err = run_git(["branch", "-vv"], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal mengambil daftar branch: {err}[/red]")
        return
    table = Table(title="Daftar Branch", header_style="bold cyan")
    table.add_column("Branch")
    table.add_column("Info")
    for line in out.splitlines():
        aktif = line.startswith("*")
        clean = line.replace("*", "").strip()
        parts = clean.split(None, 1)
        name = parts[0] if parts else clean
        info = parts[1] if len(parts) > 1 else ""
        table.add_row(f"[green]{name} (aktif)[/green]" if aktif else name, info)
    console.print(table)


def checkout_branch() -> None:
    """Pindah (checkout) ke branch lain yang dipilih user."""
    repo = _get_active_repo()
    if not repo:
        return
    branches = _list_branches(repo)
    if not branches:
        console.print("[yellow]Tidak ada branch ditemukan.[/yellow]")
        return
    pilihan = questionary.select("Pilih branch untuk checkout:", choices=branches + ["Batal"]).ask()
    if not pilihan or pilihan == "Batal":
        return
    ok, out, err = run_git(["checkout", pilihan], cwd=repo)
    if not ok:
        console.print(f"[red]Checkout gagal: {_friendly(err)}[/red]")
        log_error("Checkout branch gagal", raw_detail=err)
        return
    console.print(f"[green]Berhasil pindah ke branch '{pilihan}'.[/green]")
    log_activity(f"Branch {pilihan} aktif")


def buat_branch_baru() -> None:
    """Buat branch baru dari branch aktif saat ini."""
    repo = _get_active_repo()
    if not repo:
        return
    nama = questionary.text("Masukkan nama branch baru:").ask()
    if not nama:
        return
    ok, out, err = run_git(["checkout", "-b", nama], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal membuat branch: {_friendly(err)}[/red]")
        log_error("Gagal membuat branch", raw_detail=err)
        return
    console.print(f"[green]Branch '{nama}' berhasil dibuat dan aktif.[/green]")
    log_activity(f"Branch baru dibuat: {nama}")


def rename_branch() -> None:
    """Ganti nama branch yang dipilih user."""
    repo = _get_active_repo()
    if not repo:
        return
    branches = _list_branches(repo)
    lama = questionary.select("Pilih branch yang ingin di-rename:", choices=branches + ["Batal"]).ask()
    if not lama or lama == "Batal":
        return
    baru = questionary.text(f"Nama baru untuk '{lama}':").ask()
    if not baru:
        return
    ok, out, err = run_git(["branch", "-m", lama, baru], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal rename branch: {_friendly(err)}[/red]")
        return
    console.print(f"[green]Branch '{lama}' berhasil diganti nama menjadi '{baru}'.[/green]")
    log_activity(f"Branch {lama} diubah nama menjadi {baru}")


def delete_branch() -> None:
    """Hapus branch lokal (dengan konfirmasi kalau belum ter-merge)."""
    repo = _get_active_repo()
    if not repo:
        return
    branches = _list_branches(repo)
    if not branches:
        console.print("[yellow]Tidak ada branch untuk dihapus.[/yellow]")
        return
    target = questionary.select("Pilih branch yang ingin dihapus:", choices=branches + ["Batal"]).ask()
    if not target or target == "Batal":
        return
    config = load_config()
    if config.get("konfirmasi_delete", True):
        yakin = questionary.confirm(f"Yakin ingin menghapus branch '{target}'? Aksi ini tidak dapat dibatalkan.",
                                     default=False).ask()
        if not yakin:
            console.print("[yellow]Dibatalkan.[/yellow]")
            return
    ok, out, err = run_git(["branch", "-d", target], cwd=repo)
    if not ok:
        console.print(f"[yellow]Branch belum sepenuhnya di-merge. {_friendly(err)}[/yellow]")
        paksa = questionary.confirm("Hapus paksa branch ini? (perubahan yang belum di-merge akan hilang)",
                                     default=False).ask()
        if paksa:
            ok, out, err = run_git(["branch", "-D", target], cwd=repo)
            if not ok:
                console.print(f"[red]Gagal menghapus branch: {_friendly(err)}[/red]")
                return
        else:
            return
    console.print(f"[green]Branch '{target}' berhasil dihapus.[/green]")
    log_activity(f"Branch {target} dihapus")


def refresh() -> None:
    """Tampilkan ulang status branch/remote terkini."""
    lihat_branch()


def _friendly(err: str) -> str:
    """Ubah pesan error git mentah jadi pesan yang mudah dipahami user."""
    low = err.lower()
    if "not fully merged" in low:
        return "Branch belum sepenuhnya digabung (merge) ke branch lain."
    if "already exists" in low:
        return "Nama branch sudah digunakan."
    if "did not match any" in low or "not found" in low:
        return "Branch tidak ditemukan."
    return err or "Terjadi kesalahan yang tidak diketahui."


def show_help() -> None:
    """Tampilkan penjelasan singkat untuk menu ini."""
    console.print(
        "\n[bold cyan]Bantuan - Branch[/bold cyan]\n"
        "- Lihat Branch: menampilkan semua branch dan branch aktif saat ini.\n"
        "- Checkout Branch: berpindah ke branch lain.\n"
        "- Buat Branch Baru: membuat branch baru dari posisi saat ini.\n"
        "- Rename Branch: mengganti nama sebuah branch.\n"
        "- Delete Branch: menghapus branch (butuh konfirmasi).\n"
        "- Refresh: memuat ulang daftar branch.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    """Tampilkan menu interaktif dan proses pilihan user."""
    while True:
        console.rule("[bold cyan]Branch")
        choice = questionary.select(
            "Pilih aksi:",
            choices=[
                "Lihat Branch",
                "Checkout Branch",
                "Buat Branch Baru",
                "Rename Branch",
                "Delete Branch",
                "Refresh",
                "? Help",
                "Kembali",
            ],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Lihat Branch": lihat_branch,
                "Checkout Branch": checkout_branch,
                "Buat Branch Baru": buat_branch_baru,
                "Rename Branch": rename_branch,
                "Delete Branch": delete_branch,
                "Refresh": refresh,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Branch", e)
