"""
repository.py
Menu Repository: pilih repository, cari otomatis, clone, tambah,
ganti, dan lihat repository aktif.
"""

import os

import questionary
from rich.console import Console

from modules.utils import run_git, is_git_repo, find_git_repos, GitError
from modules.settings import load_config, save_config
from modules.logger import log_activity, log_error

console = Console()


def _set_active_repository(path: str) -> None:
    config = load_config()
    config["active_repository"] = os.path.abspath(path)
    save_config(config)


def pilih_repository() -> None:
    """Pilih repository dari daftar hasil pencarian otomatis di home directory."""
    home = os.path.expanduser("~")
    console.print("[cyan]Mencari repository Git di sekitar home directory...[/cyan]")
    repos = find_git_repos(home)
    if not repos:
        console.print("[yellow]Tidak ditemukan repository Git. "
                       "Gunakan 'Tambah Repository' untuk memasukkan path manual.[/yellow]")
        return
    pilihan = questionary.select("Pilih repository:", choices=repos + ["Batal"]).ask()
    if pilihan and pilihan != "Batal":
        _set_active_repository(pilihan)
        console.print(f"[green]Repository aktif diubah ke: {pilihan}[/green]")
        log_activity(f"Repository dipilih: {pilihan}")


def cari_repository_otomatis() -> None:
    """Cari repository Git otomatis mulai dari path yang diberikan user."""
    start_path = questionary.text(
        "Masukkan folder awal pencarian (kosongkan untuk home):", default=""
    ).ask()
    if start_path is None:
        return
    start_path = start_path.strip() or os.path.expanduser("~")
    if not os.path.isdir(start_path):
        console.print("[red]Folder tidak ditemukan.[/red]")
        return
    console.print(f"[cyan]Mencari repository di {start_path}...[/cyan]")
    repos = find_git_repos(start_path)
    if not repos:
        console.print("[yellow]Tidak ada repository Git ditemukan di folder tersebut.[/yellow]")
        return
    pilihan = questionary.select("Repository ditemukan:", choices=repos + ["Batal"]).ask()
    if pilihan and pilihan != "Batal":
        _set_active_repository(pilihan)
        console.print(f"[green]Repository aktif diubah ke: {pilihan}[/green]")
        log_activity(f"Repository dipilih (pencarian otomatis): {pilihan}")


def clone_repository() -> None:
    """Clone repository dari URL remote."""
    url = questionary.text("Masukkan URL repository yang ingin di-clone:").ask()
    if not url:
        return
    tujuan = questionary.text(
        "Masukkan folder tujuan (kosongkan untuk folder default):", default=""
    ).ask()
    if tujuan is None:
        return
    args = ["clone", url]
    if tujuan.strip():
        args.append(tujuan.strip())
    console.print("[cyan]Sedang melakukan clone...[/cyan]")
    ok, out, err = run_git(args)
    if not ok:
        console.print(f"[red]Clone gagal: {_human_git_error(err)}[/red]")
        log_error("Clone repository gagal", raw_detail=err)
        return
    console.print(f"[green]Clone berhasil.[/green]\n{out}")
    log_activity(f"Repository di-clone dari {url}")

    folder_name = tujuan.strip() if tujuan.strip() else url.rstrip("/").split("/")[-1].replace(".git", "")
    if os.path.isdir(folder_name):
        jadikan_aktif = questionary.confirm(
            f"Jadikan '{folder_name}' sebagai repository aktif?", default=True
        ).ask()
        if jadikan_aktif:
            _set_active_repository(folder_name)


def tambah_repository() -> None:
    """Tambah repository dengan memasukkan path secara manual."""
    path = questionary.text("Masukkan path folder repository:").ask()
    if not path:
        return
    path = os.path.expanduser(path.strip())
    if not is_git_repo(path):
        console.print("[red]Repository tidak ditemukan. Pastikan folder tersebut adalah repository Git "
                       "(mengandung folder .git).[/red]")
        return
    _set_active_repository(path)
    console.print(f"[green]Repository '{path}' berhasil ditambahkan dan dijadikan aktif.[/green]")
    log_activity(f"Repository ditambahkan: {path}")


def ganti_repository() -> None:
    """Ganti repository aktif ke path lain."""
    tambah_repository()


def lihat_repository_aktif() -> None:
    """Tampilkan repository yang sedang aktif."""
    config = load_config()
    repo = config.get("active_repository", "")
    if not repo or not is_git_repo(repo):
        console.print("[yellow]Belum ada repository aktif. "
                       "Silakan pilih repository terlebih dahulu.[/yellow]")
        return
    console.print(f"[cyan]Repository aktif:[/cyan] {repo}")


def _human_git_error(stderr: str) -> str:
    """Ubah pesan error git mentah menjadi pesan ramah pengguna."""
    stderr_lower = stderr.lower()
    if "not found" in stderr_lower or "does not exist" in stderr_lower:
        return "Repository tidak ditemukan. Silakan pilih repository terlebih dahulu."
    if "already exists" in stderr_lower:
        return "Folder tujuan sudah ada dan tidak kosong."
    if "could not resolve host" in stderr_lower or "network" in stderr_lower:
        return "Tidak dapat terhubung ke internet. Periksa koneksi kamu."
    if "authentication" in stderr_lower or "permission denied" in stderr_lower:
        return "Autentikasi gagal. Periksa username/token/SSH key kamu."
    return stderr or "Terjadi kesalahan yang tidak diketahui."


def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Repository[/bold cyan]\n"
        "- Pilih Repository: memilih repository dari hasil pencarian otomatis.\n"
        "- Cari Repository Otomatis: mencari folder Git mulai dari path tertentu.\n"
        "- Clone Repository: mengunduh repository baru dari URL remote.\n"
        "- Tambah Repository: menambahkan repository dengan path manual.\n"
        "- Ganti Repository: mengganti repository aktif.\n"
        "- Lihat Repository Aktif: menampilkan repository yang sedang dipakai.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    while True:
        console.rule("[bold cyan]Repository")
        choice = questionary.select(
            "Pilih aksi:",
            choices=[
                "Pilih Repository",
                "Cari Repository Git Otomatis",
                "Clone Repository",
                "Tambah Repository",
                "Ganti Repository",
                "Lihat Repository Aktif",
                "? Help",
                "Kembali",
            ],
        ).ask()

        if choice is None or choice == "Kembali":
            return
        try:
            if choice == "Pilih Repository":
                pilih_repository()
            elif choice == "Cari Repository Git Otomatis":
                cari_repository_otomatis()
            elif choice == "Clone Repository":
                clone_repository()
            elif choice == "Tambah Repository":
                tambah_repository()
            elif choice == "Ganti Repository":
                ganti_repository()
            elif choice == "Lihat Repository Aktif":
                lihat_repository_aktif()
            elif choice == "? Help":
                show_help()
        except GitError as e:
            console.print(f"[red]{e.human_message}[/red]")
            log_error("GitError di menu Repository", raw_detail=e.raw_error)
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Repository", e)
