"""
upload.py
Menu Upload: Upload File, Upload Folder, Upload ZIP (Extract),
Upload ZIP (No Extract).

Semua sumber file/folder dipilih lewat picker interaktif (Downloads/Home/
Browse Folder/Manual Path) - user tidak perlu mengetik path manual kecuali
memang memilih itu. Tujuan di dalam repository juga dipilih lewat folder
picker (bukan mengetik path).
"""

import os
import shutil
import zipfile
from typing import Optional, Tuple

import questionary
from rich.console import Console
from rich.table import Table

from modules.utils import (
    run_git, count_files_in_dir, human_size, pick_folder_in_repo,
    sha1_of_file, sha1_of_bytes, spinner,
)
from modules.settings import load_config
from modules.logger import log_activity, log_error
from modules import backup as backup_module
from modules import preflight

console = Console()


def _get_active_repo() -> Optional[str]:
    config = load_config()
    repo = config.get("active_repository", "")
    if not repo:
        console.print("[yellow]Repository tidak ditemukan. Silakan pilih repository terlebih dahulu.[/yellow]")
        return None
    return repo


def _downloads_dir() -> str:
    for candidate in ("~/storage/downloads", "~/Download", "~/Downloads"):
        path = os.path.expanduser(candidate)
        if os.path.isdir(path):
            return path
    return os.path.expanduser("~")


# ---------------------------------------------------------------------------
# PRIORITAS 3 #8/#9 - Picker sumber file, tidak perlu ketik path manual
# ---------------------------------------------------------------------------

def _browse_for_path(start_dir: str, want_ext: Optional[str] = None,
                      pick_folder: bool = False) -> Optional[str]:
    """
    Browser folder interaktif sederhana. Kalau pick_folder=True, user
    memilih FOLDER (bisa langsung pilih folder saat ini). Kalau False,
    user menavigasi sampai memilih sebuah FILE (opsional difilter want_ext).
    """
    current = os.path.abspath(start_dir)
    while True:
        try:
            entries = sorted(os.listdir(current))
        except OSError as e:
            console.print(f"[red]Tidak bisa membaca folder ini: {e}[/red]")
            return None

        dirs = [e for e in entries if os.path.isdir(os.path.join(current, e)) and not e.startswith(".")]
        files = []
        if not pick_folder:
            files = [e for e in entries if os.path.isfile(os.path.join(current, e)) and not e.startswith(".")]
            if want_ext:
                files = [f for f in files if f.lower().endswith(want_ext)]

        choices = []
        if pick_folder:
            choices.append("[Pilih folder ini]")
        parent = os.path.dirname(current.rstrip("/"))
        if parent and parent != current:
            choices.append(".. (naik satu folder)")
        choices += [f"[DIR] {d}/" for d in dirs]
        choices += files
        choices.append("Batal")

        pilihan = questionary.select(f"Browse: {current}", choices=choices).ask()
        if not pilihan or pilihan == "Batal":
            return None
        if pilihan == "[Pilih folder ini]":
            return current
        if pilihan.startswith(".."):
            current = parent
            continue
        if pilihan.startswith("[DIR] "):
            current = os.path.join(current, pilihan[6:].rstrip("/"))
            continue
        return os.path.join(current, pilihan)


def _pick_source_file(label: str = "file", want_ext: Optional[str] = None,
                       include_home: bool = True) -> Optional[str]:
    """
    Menu sumber standar: Downloads (default) / Home / Browse Folder / Manual Path.
    """
    choices = ["Downloads"]
    if include_home:
        choices.append("Home")
    choices += ["Browse Folder", "Manual Path", "Batal"]

    sumber = questionary.select(f"Pilih sumber {label}:", choices=choices).ask()
    if not sumber or sumber == "Batal":
        return None

    if sumber == "Downloads":
        return _browse_for_path(_downloads_dir(), want_ext=want_ext)
    if sumber == "Home":
        return _browse_for_path(os.path.expanduser("~"), want_ext=want_ext)
    if sumber == "Browse Folder":
        return _browse_for_path(os.path.expanduser("~"), want_ext=want_ext)
    if sumber == "Manual Path":
        path = questionary.text(f"Masukkan path lengkap {label}:").ask()
        if not path:
            return None
        path = os.path.expanduser(path.strip())
        if not os.path.isfile(path):
            console.print("[red]File tidak ditemukan di path tersebut.[/red]")
            return None
        return path
    return None


def _pick_source_folder(label: str = "folder") -> Optional[str]:
    choices = ["Home", "Browse Folder", "Manual Path", "Batal"]
    sumber = questionary.select(f"Pilih sumber {label}:", choices=choices).ask()
    if not sumber or sumber == "Batal":
        return None
    if sumber == "Home":
        return _browse_for_path(os.path.expanduser("~"), pick_folder=True)
    if sumber == "Browse Folder":
        return _browse_for_path(os.path.expanduser("~"), pick_folder=True)
    if sumber == "Manual Path":
        path = questionary.text(f"Masukkan path lengkap {label}:").ask()
        if not path:
            return None
        path = os.path.expanduser(path.strip())
        if not os.path.isdir(path):
            console.print("[red]Folder tidak ditemukan.[/red]")
            return None
        return path
    return None


# ---------------------------------------------------------------------------
# ZIP helpers - preview, wrapper detection, diff (PRIORITAS 3 #12/#13)
# ---------------------------------------------------------------------------

def preview_zip(zip_path: str) -> None:
    """Tampilkan isi ZIP mentah (nama & ukuran) sebelum ekstraksi."""
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            table = Table(title=f"Isi ZIP ({len(names)} entri)", header_style="bold cyan")
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


def _has_single_wrapper_folder(zip_path: str) -> Optional[str]:
    """Kembalikan nama folder pembungkus jika semua isi ZIP ada dalam satu folder."""
    with zipfile.ZipFile(zip_path, "r") as z:
        top_levels = set()
        for name in z.namelist():
            top = name.split("/")[0]
            top_levels.add(top)
        if len(top_levels) == 1:
            return top_levels.pop()
    return None


def _zip_target_rel(member_name: str, strip_wrapper: bool) -> Optional[str]:
    """Path relatif tujuan (di dalam folder tujuan) untuk satu entri ZIP."""
    if strip_wrapper:
        parts = member_name.split("/", 1)
        rel = parts[1] if len(parts) > 1 else parts[0]
    else:
        rel = member_name
    return rel or None


def _compute_zip_diff(zip_path: str, dest_dir: str, strip_wrapper: bool) -> Tuple[int, int, int, dict]:
    """
    PRIORITAS 3 #13 - Preview Perubahan ZIP.
    Hitung berapa file akan Tambah / Update / Delete kalau ZIP ini
    diekstrak ke dest_dir, dibandingkan isi dest_dir SEKARANG.
    Return (tambah, update, delete, target_map) - target_map dipakai lagi
    saat proses ekstraksi supaya gak perlu hitung ulang.
    """
    tambah = update = 0
    target_map: dict = {}  # target_path -> zip member name

    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.infolist():
            if member.is_dir():
                continue
            rel = _zip_target_rel(member.filename, strip_wrapper)
            if not rel:
                continue
            target_path = os.path.join(dest_dir, rel)
            target_map[target_path] = member.filename

            if not os.path.exists(target_path):
                tambah += 1
                continue

            local_hash = sha1_of_file(target_path)
            with z.open(member) as f:
                zip_hash = sha1_of_bytes(f.read())
            if local_hash != zip_hash:
                update += 1

    # Delete: file yang SEKARANG ada di dest_dir tapi gak ada di ZIP sama sekali.
    delete = 0
    if os.path.isdir(dest_dir):
        for root, _dirs, files in os.walk(dest_dir):
            if os.sep + ".git" in root or root.rstrip("/").endswith(".git"):
                continue
            for fname in files:
                full = os.path.join(root, fname)
                if full not in target_map:
                    delete += 1

    return tambah, update, delete, target_map


def _confirm_zip_changes(tambah: int, update: int, delete: int) -> bool:
    table = Table(title="Preview Perubahan ZIP", header_style="bold cyan")
    table.add_column("Jenis")
    table.add_column("Jumlah")
    table.add_row("Tambah", str(tambah))
    table.add_row("Update", str(update))
    table.add_row("Delete (info saja, TIDAK dihapus otomatis)", str(delete))
    console.print(table)
    return bool(questionary.confirm("Lanjutkan ekstrak?", default=True).ask())


# ---------------------------------------------------------------------------
# Upload ZIP (Extract)
# ---------------------------------------------------------------------------

def upload_zip_extract() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=False, label="Upload ZIP"):
        return

    zip_path = _pick_source_file("file ZIP", want_ext=".zip")
    if not zip_path:
        return

    try:
        preview_zip(zip_path)
    except zipfile.BadZipFile:
        log_error("ZIP rusak saat preview", raw_detail=zip_path)
        return

    dest_dir = pick_folder_in_repo(repo, "Pilih folder tujuan ekstrak di dalam repository:")
    if dest_dir is None:
        return

    wrapper = _has_single_wrapper_folder(zip_path)
    strip_wrapper = True
    if wrapper:
        console.print(f"[cyan]Folder pembungkus terdeteksi: '{wrapper}/'[/cyan]")
        pilihan = questionary.select(
            "Bagaimana perlakuan folder pembungkus ini?",
            choices=["(*) Hapus Folder Pembungkus", "( ) Pertahankan Folder Pembungkus", "Batal"],
        ).ask()
        if not pilihan or pilihan == "Batal":
            return
        strip_wrapper = pilihan.startswith("(*)")

    # PRIORITAS 3 #13: preview Tambah/Update/Delete sebelum benar-benar ekstrak
    with spinner("Menghitung perubahan..."):
        tambah, update, delete, target_map = _compute_zip_diff(zip_path, dest_dir, strip_wrapper)
    if not _confirm_zip_changes(tambah, update, delete):
        console.print("[yellow]Dibatalkan.[/yellow]")
        return

    timpa = questionary.confirm(
        "Timpa (overwrite) file yang sudah ada di repository jika bentrok?", default=True
    ).ask()

    config = load_config()
    if config.get("backup_otomatis", True) and timpa:
        console.print("[cyan]Membuat backup otomatis sebelum overwrite...[/cyan]")
        backup_module.buat_backup_zip(repo, silent_label="auto-before-upload")

    files_before = count_files_in_dir(repo)

    try:
        with spinner("Mengekstrak..."):
            with zipfile.ZipFile(zip_path, "r") as z:
                for member in z.infolist():
                    if member.is_dir():
                        continue
                    rel = _zip_target_rel(member.filename, strip_wrapper)
                    if not rel:
                        continue
                    target_path = os.path.join(dest_dir, rel)
                    if os.path.exists(target_path) and not timpa:
                        continue
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with z.open(member) as src, open(target_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
    except zipfile.BadZipFile as e:
        console.print("[red]Gagal mengekstrak: file ZIP rusak.[/red]")
        log_error("Gagal ekstrak ZIP", e, raw_detail=zip_path)
        return
    except OSError as e:
        console.print(f"[red]Gagal menulis file ke repository: {e}[/red]")
        log_error("Gagal menulis file hasil ekstrak ZIP", e)
        return

    files_after = count_files_in_dir(repo)
    # delete selalu 0 di sini: ekstrak ZIP TIDAK PERNAH menghapus file yang
    # gak ada di ZIP (baris "Delete" di Preview cuma informasi, bukan aksi).
    _tampilkan_ringkasan_upload(
        repo, files_before, files_after, extra_label="Upload ZIP (Extract)",
        override_counts=(tambah, update, 0),
    )
    log_activity("Upload ZIP (Extract) berhasil")


def upload_zip_no_extract() -> None:
    """PRIORITAS 3 #10 - salin file ZIP apa adanya ke repository, tanpa ekstrak."""
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=False, label="Upload ZIP (No Extract)"):
        return

    zip_path = _pick_source_file("file ZIP", want_ext=".zip")
    if not zip_path:
        return

    dest_dir = pick_folder_in_repo(repo, "Pilih folder tujuan (ZIP disalin apa adanya):")
    if dest_dir is None:
        return

    files_before = count_files_in_dir(repo)
    try:
        os.makedirs(dest_dir, exist_ok=True)
        target_path = os.path.join(dest_dir, os.path.basename(zip_path))
        shutil.copy2(zip_path, target_path)
    except OSError as e:
        console.print(f"[red]Gagal menyalin ZIP: {e}[/red]")
        log_error("Gagal upload ZIP (no extract)", e)
        return

    files_after = count_files_in_dir(repo)
    console.print(f"[green]ZIP berhasil disalin ke {target_path} (tanpa ekstrak).[/green]")
    _tampilkan_ringkasan_upload(repo, files_before, files_after, extra_label="Upload ZIP (No Extract)")
    log_activity("Upload ZIP (No Extract) berhasil")


# ---------------------------------------------------------------------------
# Upload File / Folder
# ---------------------------------------------------------------------------

def upload_file() -> None:
    """PRIORITAS 3 #8 - Upload satu file lewat picker, bukan ketik path manual."""
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=False, label="Upload File"):
        return

    path = _pick_source_file("file")
    if not path:
        return

    dest_dir = pick_folder_in_repo(repo, "Pilih folder tujuan di dalam repository:")
    if dest_dir is None:
        return

    try:
        os.makedirs(dest_dir, exist_ok=True)
        tujuan_path = os.path.join(dest_dir, os.path.basename(path))
        shutil.copy2(path, tujuan_path)
    except OSError as e:
        console.print(f"[red]Gagal meng-copy file: {e}[/red]")
        log_error("Gagal upload file", e)
        return
    console.print(f"[green]✓ Upload Berhasil[/green]\n\n"
                  f"Repository : {os.path.basename(repo)}\n"
                  f"File       : {os.path.basename(path)}\n"
                  f"Tujuan     : {tujuan_path}\n")
    console.print("[dim]Catatan: file belum di-commit. Gunakan menu 'Git Add' dan 'Commit' selanjutnya.[/dim]")
    log_activity("Upload File berhasil")


def upload_folder() -> None:
    """Upload folder tertentu ke repository (copy, tidak commit otomatis)."""
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=False, label="Upload Folder"):
        return

    path = _pick_source_folder("folder")
    if not path:
        return

    dest_parent = pick_folder_in_repo(repo, "Pilih folder tujuan di dalam repository:")
    if dest_parent is None:
        return

    nama_folder = os.path.basename(path.rstrip("/"))
    tujuan_path = os.path.join(dest_parent, nama_folder)
    try:
        shutil.copytree(path, tujuan_path, dirs_exist_ok=True)
    except OSError as e:
        console.print(f"[red]Gagal meng-copy folder: {e}[/red]")
        log_error("Gagal upload folder", e)
        return
    console.print(f"[green]✓ Upload Berhasil[/green]\n\nFolder berhasil di-copy ke {tujuan_path}\n")
    console.print("[dim]Catatan: folder belum di-commit. Gunakan menu 'Git Add' dan 'Commit' selanjutnya.[/dim]")
    log_activity("Upload Folder berhasil")


def _tampilkan_ringkasan_upload(repo: str, files_before: int, files_after: int,
                                 extra_label: str = "Upload",
                                 override_counts: Optional[Tuple[int, int, int]] = None) -> None:
    """override_counts, kalau diisi (added, modified, deleted), dipakai
    langsung tanpa hitung ulang dari 'git status' - dipakai Upload ZIP
    (Extract) supaya angkanya konsisten dengan tabel Preview Perubahan ZIP,
    dan gak ketimpa status git lain yang gak terkait aksi ini."""
    ok, branch, _err = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    branch = branch if ok else "-"

    if override_counts is not None:
        added, modified, deleted = override_counts
    else:
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

    table = Table(title=f"Ringkasan Setelah {extra_label}", header_style="bold cyan")
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

    # PRIORITAS 1 #3: refresh info repo (branch/remote/status) abis upload
    run_git(["status", "--short"], cwd=repo)
    run_git(["branch", "-vv"], cwd=repo)
    run_git(["remote", "-v"], cwd=repo)


def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Upload[/bold cyan]\n"
        "- Upload File: menyalin satu file ke repository lewat picker (Downloads/Home/Browse/Manual).\n"
        "- Upload Folder: menyalin satu folder utuh ke repository.\n"
        "- Upload ZIP (Extract): mengekstrak isi ZIP ke repository, dengan\n"
        "  deteksi folder pembungkus dan preview perubahan (Tambah/Update/Delete).\n"
        "- Upload ZIP (No Extract): menyalin file ZIP apa adanya, tanpa dibongkar.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    while True:
        console.rule("[bold cyan]Upload")
        choice = questionary.select(
            "Pilih aksi:",
            choices=[
                "Upload File",
                "Upload Folder",
                "Upload ZIP (Extract)",
                "Upload ZIP (No Extract)",
                "? Help",
                "Kembali",
            ],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Upload File": upload_file,
                "Upload Folder": upload_folder,
                "Upload ZIP (Extract)": upload_zip_extract,
                "Upload ZIP (No Extract)": upload_zip_no_extract,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Upload", e)
