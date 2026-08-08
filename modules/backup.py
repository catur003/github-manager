"""
backup.py
Menu Backup: Backup ZIP, Restore ZIP, List Backup, Hapus Backup.
Juga dipakai secara internal oleh modules/upload.py untuk backup
otomatis sebelum overwrite.
"""

import os
import re
import shutil
import zipfile
from datetime import datetime

import questionary
from rich.console import Console
from rich.table import Table

from modules.utils import BACKUP_DIR, ensure_dirs, human_size, safe_zip_member_path
from modules.settings import load_config
from modules.logger import log_activity, log_error

console = Console()

# Pola nama file backup format baru: {nama_repo}__YYYY-MM-DD_HH-MM[_label].zip
_BACKUP_NAME_RE = re.compile(r'^(.+)__\d{4}-\d{2}-\d{2}_\d{2}-\d{2}(?:_.+)?\.zip$', re.IGNORECASE)


def _sanitize_repo_name(repo_path: str) -> str:
    """Ubah nama folder repo jadi string aman dipakai sebagai prefix nama file
    (hanya alfanumerik, dash, underscore - karakter lain diganti '-')."""
    name = os.path.basename(repo_path.rstrip("/")) or "repo"
    safe = re.sub(r'[^A-Za-z0-9_-]', '-', name)
    return safe or "repo"


def _get_active_repo() -> str | None:
    """Ambil path repository aktif dari config, atau None + pesan kalau belum dipilih."""
    config = load_config()
    repo = config.get("active_repository", "")
    if not repo:
        console.print("[yellow]Repository tidak ditemukan. Silakan pilih repository terlebih dahulu.[/yellow]")
        return None
    return repo


def buat_backup_zip(repo_path: str, silent_label: str | None = None) -> str | None:
    """
    Buat file ZIP backup dari repo_path ke folder backup/.
    Nama file: {nama_repo}__YYYY-MM-DD_HH-MM[_label].zip
    BUGFIX: sebelumnya nama file cuma timestamp (YYYY-MM-DD_HH-MM.zip) tanpa
    nama repo - backup dari semua project (ZenStock, SPP Hub, Web Desa, dst)
    tercampur jadi satu daftar di Restore/Hapus/List, jadi restore backup
    project A ke folder project B bisa kejadian tanpa disadari. Sekarang
    nama repo ikut disertakan di nama file supaya list_backup()/
    restore_zip()/hapus_backup() bisa difilter hanya milik repo aktif.
    Mengembalikan path file backup jika berhasil, None jika gagal.
    """
    ensure_dirs()
    repo_name = _sanitize_repo_name(repo_path)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    suffix = f"_{silent_label}" if silent_label else ""
    zip_name = f"{repo_name}__{timestamp}{suffix}.zip"
    zip_path = BACKUP_DIR / zip_name

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(repo_path):
                dirs[:] = [d for d in dirs if d != ".git"]
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, repo_path)
                    zf.write(full_path, rel_path)
    except OSError as e:
        console.print(f"[red]Gagal membuat backup: {e}[/red]")
        log_error("Gagal membuat backup ZIP", e)
        return None

    if not silent_label:
        console.print(f"[green]Backup berhasil dibuat: {zip_path}[/green]")
    log_activity(f"Backup dibuat: {zip_name}")
    return str(zip_path)


def backup_zip_menu() -> None:
    """Menu untuk membuat backup ZIP secara manual."""
    repo = _get_active_repo()
    if not repo:
        return
    console.print("[cyan]Membuat backup dari repository aktif...[/cyan]")
    buat_backup_zip(repo)


def _list_all_backup_files() -> list[str]:
    """Ambil semua file backup ZIP di folder backup/, tanpa filter repo."""
    ensure_dirs()
    return sorted([f for f in os.listdir(BACKUP_DIR) if f.lower().endswith(".zip")], reverse=True)


def _list_backup_files_for_repo(repo_path: str) -> list[str]:
    """Ambil daftar backup ZIP milik repo tertentu saja (format baru,
    prefix nama repo cocok)."""
    repo_name = _sanitize_repo_name(repo_path)
    prefix = f"{repo_name}__"
    return [f for f in _list_all_backup_files() if f.startswith(prefix)]


def _list_legacy_backup_files() -> list[str]:
    """Backup format lama (sebelum fix isolasi per-repo) - nama file cuma
    timestamp tanpa nama repo, jadi tidak bisa dipastikan milik repo mana.
    Ditampilkan terpisah dengan peringatan, TIDAK ikut hilang/ke-filter
    diam-diam supaya user tetap bisa mengaksesnya."""
    return [f for f in _list_all_backup_files() if not _BACKUP_NAME_RE.match(f)]


def list_backup() -> None:
    """Tampilkan daftar backup milik repository aktif saja."""
    repo = _get_active_repo()
    if not repo:
        return
    files = _list_backup_files_for_repo(repo)
    legacy = _list_legacy_backup_files()
    if not files:
        console.print(f"[yellow]Belum ada backup untuk '{os.path.basename(repo)}'.[/yellow]")
    else:
        table = Table(title=f"Daftar Backup - {os.path.basename(repo)}", header_style="bold cyan")
        table.add_column("Nama File")
        table.add_column("Ukuran")
        for f in files:
            size = (BACKUP_DIR / f).stat().st_size
            table.add_row(f, human_size(size))
        console.print(table)
    if legacy:
        console.print(
            f"[dim]ℹ {len(legacy)} backup lama (format sebelum update ini, tanpa nama repo) "
            f"tidak ditampilkan di sini karena tidak bisa dipastikan milik repo mana. "
            f"Masih ada di folder backup/ dan bisa dibuka manual lewat file manager.[/dim]"
        )


def restore_zip() -> None:
    """Pulihkan (restore) repository dari salah satu file backup ZIP milik repo aktif."""
    repo = _get_active_repo()
    if not repo:
        return
    files = _list_backup_files_for_repo(repo)
    if not files:
        console.print(f"[yellow]Belum ada backup untuk '{os.path.basename(repo)}' yang bisa di-restore.[/yellow]")
        return
    pilihan = questionary.select("Pilih backup untuk di-restore:", choices=files + ["Batal"]).ask()
    if not pilihan or pilihan == "Batal":
        return
    config = load_config()
    if config.get("konfirmasi_delete", True):
        yakin = questionary.confirm(
            f"Restore akan menimpa isi repository aktif dengan isi '{pilihan}'. Lanjutkan?", default=False
        ).ask()
        if not yakin:
            console.print("[yellow]Dibatalkan.[/yellow]")
            return
    zip_path = BACKUP_DIR / pilihan
    try:
        # SECURITY: Zip Slip protection - jangan pakai extractall() langsung,
        # validasi tiap entry supaya tidak bisa menulis di luar folder repo.
        with zipfile.ZipFile(zip_path, "r") as z:
            skipped = 0
            for member in z.infolist():
                if member.is_dir():
                    continue
                target_path = safe_zip_member_path(repo, member.filename)
                if target_path is None:
                    skipped += 1
                    log_error("Zip Slip diblokir saat restore", raw_detail=f"entry ditolak: {member.filename}")
                    continue
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with z.open(member) as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            if skipped:
                console.print(f"[yellow]⚠ {skipped} entry mencurigakan di ZIP backup dilewati (tidak diekstrak).[/yellow]")
    except zipfile.BadZipFile as e:
        console.print("[red]File backup rusak atau tidak valid.[/red]")
        log_error("Gagal restore backup, ZIP rusak", e)
        return
    except OSError as e:
        console.print(f"[red]Gagal melakukan restore: {e}[/red]")
        log_error("Gagal restore backup", e)
        return
    console.print(f"[green]Restore dari '{pilihan}' berhasil.[/green]")
    log_activity(f"Restore backup: {pilihan}")


def hapus_backup() -> None:
    """Hapus file backup ZIP milik repo aktif yang dipilih user."""
    repo = _get_active_repo()
    if not repo:
        return
    files = _list_backup_files_for_repo(repo)
    if not files:
        console.print(f"[yellow]Belum ada backup untuk '{os.path.basename(repo)}' yang bisa dihapus.[/yellow]")
        return
    pilihan = questionary.select("Pilih backup yang ingin dihapus:", choices=files + ["Batal"]).ask()
    if not pilihan or pilihan == "Batal":
        return
    config = load_config()
    if config.get("konfirmasi_delete", True):
        yakin = questionary.confirm(f"Yakin ingin menghapus backup '{pilihan}'?", default=False).ask()
        if not yakin:
            console.print("[yellow]Dibatalkan.[/yellow]")
            return
    try:
        os.remove(BACKUP_DIR / pilihan)
    except OSError as e:
        console.print(f"[red]Gagal menghapus backup: {e}[/red]")
        log_error("Gagal menghapus backup", e)
        return
    console.print(f"[green]Backup '{pilihan}' berhasil dihapus.[/green]")
    log_activity(f"Backup dihapus: {pilihan}")


def show_help() -> None:
    """Tampilkan penjelasan singkat untuk menu ini."""
    console.print(
        "\n[bold cyan]Bantuan - Backup[/bold cyan]\n"
        "- Backup ZIP: membuat salinan ZIP dari repository aktif ke folder backup/.\n"
        "- Restore ZIP: mengembalikan isi repository dari salah satu file backup.\n"
        "- List Backup: menampilkan semua backup yang tersimpan.\n"
        "- Hapus Backup: menghapus file backup yang sudah tidak dibutuhkan.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    """Tampilkan menu interaktif dan proses pilihan user."""
    while True:
        console.rule("[bold cyan]Backup")
        choice = questionary.select(
            "Pilih aksi:",
            choices=["Backup ZIP", "Restore ZIP", "List Backup", "Hapus Backup", "? Help", "Kembali"],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Backup ZIP": backup_zip_menu,
                "Restore ZIP": restore_zip,
                "List Backup": list_backup,
                "Hapus Backup": hapus_backup,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Backup", e)
