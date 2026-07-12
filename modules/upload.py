"""
upload.py
Menu Upload: upload ZIP (extract dengan/tanpa folder pembungkus, overwrite
repository, preview isi ZIP, backup otomatis sebelum overwrite, hitung
jumlah file, ringkasan perubahan), Upload File, dan Upload Folder.
"""

import os
import shutil
import zipfile
from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table

from modules.utils import run_git, count_files_in_dir, human_size
from modules.settings import load_config
from modules.logger import log_activity, log_error
from modules import backup as backup_module

console = Console()


def _get_active_repo() -> str | None:
    config = load_config()
    repo = config.get("active_repository", "")
    if not repo:
        console.print("[yellow]Repository tidak ditemukan. Silakan pilih repository terlebih dahulu.[/yellow]")
        return None
    return repo


def _pick_zip_from_download() -> str | None:
    download_dir = os.path.expanduser("~/storage/downloads")
    if not os.path.isdir(download_dir):
        download_dir = os.path.expanduser("~/Download")
    if not os.path.isdir(download_dir):
        console.print("[yellow]Folder Download tidak ditemukan. "
                       "Pastikan Termux storage sudah di-setup ('termux-setup-storage').[/yellow]")
        return None
    zips = [f for f in os.listdir(download_dir) if f.lower().endswith(".zip")]
    if not zips:
        console.print("[yellow]Tidak ada file ZIP di folder Download.[/yellow]")
        return None
    pilihan = questionary.select("Pilih file ZIP:", choices=zips + ["Batal"]).ask()
    if not pilihan or pilihan == "Batal":
        return None
    return os.path.join(download_dir, pilihan)


def _pick_zip_from_path() -> str | None:
    path = questionary.text("Masukkan path lengkap file ZIP:").ask()
    if not path:
        return None
    path = os.path.expanduser(path.strip())
    if not os.path.isfile(path) or not path.lower().endswith(".zip"):
        console.print("[red]File ZIP tidak ditemukan di path tersebut.[/red]")
        return None
    return path


def preview_zip(zip_path: str) -> None:
    """Tampilkan isi ZIP sebelum ekstraksi."""
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            table = Table(title=f"Preview isi ZIP ({len(names)} entri)", header_style="bold cyan")
            table.add_column("Nama File")
            table.add_column("Ukuran")
            for info in z.infolist()[:30]:
                table.add_row(info.filename, human_size(info.file_size))
            if len(names) > 30:
                table.add_row("...", f"dan {len(names) - 30} entri lainnya")
            console.print(table)
    except zipfile.BadZipFile:
        console.print("[red]File ZIP rusak atau tidak valid.[/red]")
        raise


def _has_single_wrapper_folder(zip_path: str) -> str | None:
    """Kembalikan nama folder pembungkus jika semua isi ZIP ada dalam satu folder."""
    with zipfile.ZipFile(zip_path, "r") as z:
        top_levels = set()
        for name in z.namelist():
            top = name.split("/")[0]
            top_levels.add(top)
        if len(top_levels) == 1:
            return top_levels.pop()
    return None


def upload_zip() -> None:
    repo = _get_active_repo()
    if not repo:
        return

    sumber = questionary.select(
        "Pilih sumber file ZIP:",
        choices=["Pilih ZIP dari Download", "Pilih ZIP dari path lain", "Batal"],
    ).ask()
    if not sumber or sumber == "Batal":
        return

    zip_path = _pick_zip_from_download() if sumber == "Pilih ZIP dari Download" else _pick_zip_from_path()
    if not zip_path:
        return

    try:
        preview_zip(zip_path)
    except zipfile.BadZipFile:
        log_error("ZIP rusak saat preview", raw_detail=zip_path)
        return

    wrapper = _has_single_wrapper_folder(zip_path)
    ekstrak_pilihan_choices = ["Ekstrak tanpa folder pembungkus", "Ekstrak dengan folder pembungkus", "Batal"]
    if not wrapper:
        ekstrak_pilihan_choices = ["Ekstrak apa adanya", "Batal"]

    cara_ekstrak = questionary.select("Bagaimana cara ekstrak ZIP ini?", choices=ekstrak_pilihan_choices).ask()
    if not cara_ekstrak or cara_ekstrak == "Batal":
        return

    timpa = questionary.confirm(
        "Timpa (overwrite) file yang sudah ada di repository jika bentrok?", default=True
    ).ask()

    config = load_config()
    if config.get("backup_otomatis", True) and timpa:
        console.print("[cyan]Membuat backup otomatis sebelum overwrite...[/cyan]")
        backup_module.buat_backup_zip(repo, silent_label="auto-before-upload")

    # Hitung file sebelum
    files_before = count_files_in_dir(repo)

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            if cara_ekstrak == "Ekstrak tanpa folder pembungkus" and wrapper:
                for member in z.infolist():
                    if member.is_dir():
                        continue
                    relative = member.filename.split("/", 1)
                    target_rel = relative[1] if len(relative) > 1 else relative[0]
                    if not target_rel:
                        continue
                    target_path = os.path.join(repo, target_rel)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with z.open(member) as src, open(target_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
            else:
                z.extractall(repo)
    except zipfile.BadZipFile as e:
        console.print("[red]Gagal mengekstrak: file ZIP rusak.[/red]")
        log_error("Gagal ekstrak ZIP", e, raw_detail=zip_path)
        return
    except OSError as e:
        console.print(f"[red]Gagal menulis file ke repository: {e}[/red]")
        log_error("Gagal menulis file hasil ekstrak ZIP", e)
        return

    files_after = count_files_in_dir(repo)
    _tampilkan_ringkasan_upload(repo, files_before, files_after)
    log_activity("Upload ZIP berhasil")


def upload_file() -> None:
    """Upload satu file ke repository (copy, tidak commit otomatis)."""
    repo = _get_active_repo()
    if not repo:
        return
    path = questionary.text("Masukkan path lengkap file yang ingin di-upload:").ask()
    if not path:
        return
    path = os.path.expanduser(path.strip())
    if not os.path.isfile(path):
        console.print("[red]File tidak ditemukan.[/red]")
        return
    subfolder = questionary.text(
        "Masukkan sub-folder tujuan di dalam repository (kosongkan untuk root):", default=""
    ).ask()
    tujuan_dir = os.path.join(repo, subfolder.strip()) if subfolder and subfolder.strip() else repo
    try:
        os.makedirs(tujuan_dir, exist_ok=True)
        tujuan_path = os.path.join(tujuan_dir, os.path.basename(path))
        shutil.copy2(path, tujuan_path)
    except OSError as e:
        console.print(f"[red]Gagal meng-copy file: {e}[/red]")
        log_error("Gagal upload file", e)
        return
    console.print(f"[green]File berhasil di-copy ke {tujuan_path}[/green]")
    console.print("[dim]Catatan: file belum di-commit. Gunakan menu 'Git Add' dan 'Commit' selanjutnya.[/dim]")
    log_activity("Upload File berhasil")


def upload_folder() -> None:
    """Upload folder tertentu ke repository (copy, tidak commit otomatis)."""
    repo = _get_active_repo()
    if not repo:
        return
    path = questionary.text("Masukkan path folder yang ingin di-upload:").ask()
    if not path:
        return
    path = os.path.expanduser(path.strip())
    if not os.path.isdir(path):
        console.print("[red]Folder tidak ditemukan.[/red]")
        return
    nama_folder = os.path.basename(path.rstrip("/"))
    tujuan_path = os.path.join(repo, nama_folder)
    try:
        shutil.copytree(path, tujuan_path, dirs_exist_ok=True)
    except OSError as e:
        console.print(f"[red]Gagal meng-copy folder: {e}[/red]")
        log_error("Gagal upload folder", e)
        return
    console.print(f"[green]Folder berhasil di-copy ke {tujuan_path}[/green]")
    console.print("[dim]Catatan: folder belum di-commit. Gunakan menu 'Git Add' dan 'Commit' selanjutnya.[/dim]")
    log_activity("Upload Folder berhasil")


def _tampilkan_ringkasan_upload(repo: str, files_before: int, files_after: int) -> None:
    ok, out, _err = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    branch = out if ok else "-"
    ok, status_out, _err = run_git(["status", "--porcelain"], cwd=repo)
    added = modified = deleted = 0
    if ok:
        for line in status_out.splitlines():
            code = line[:2]
            if "A" in code or "?" in code:
                added += 1
            elif "M" in code:
                modified += 1
            elif "D" in code:
                deleted += 1

    table = Table(title="Ringkasan Setelah Upload", header_style="bold cyan")
    table.add_column("Info")
    table.add_column("Nilai")
    table.add_row("Repository", os.path.basename(repo))
    table.add_row("Branch", branch)
    table.add_row("Jumlah file baru", str(added))
    table.add_row("Jumlah file berubah", str(modified))
    table.add_row("Jumlah file dihapus", str(deleted))
    table.add_row("Total file sebelum", str(files_before))
    table.add_row("Total file sesudah", str(files_after))
    console.print(table)
    console.print("[bold]Langkah berikutnya:[/bold] gunakan menu 'Git Add' lalu 'Commit' untuk menyimpan perubahan.")


def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Upload[/bold cyan]\n"
        "- Upload ZIP: mengekstrak file ZIP ke dalam repository aktif, dengan\n"
        "  opsi ekstrak dengan/tanpa folder pembungkus, preview isi, dan backup\n"
        "  otomatis sebelum menimpa file.\n"
        "- Upload File: menyalin satu file ke dalam repository (belum di-commit).\n"
        "- Upload Folder: menyalin satu folder ke dalam repository (belum di-commit).\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    while True:
        console.rule("[bold cyan]Upload")
        choice = questionary.select(
            "Pilih aksi:",
            choices=["Upload ZIP", "Upload File", "Upload Folder", "? Help", "Kembali"],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Upload ZIP": upload_zip,
                "Upload File": upload_file,
                "Upload Folder": upload_folder,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Upload", e)
