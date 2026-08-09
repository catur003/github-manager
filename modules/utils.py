"""
utils.py
Fungsi-fungsi bantu (utility) yang dipakai di seluruh module.
Tidak boleh ada hardcode path di sini - semua path relatif terhadap
lokasi project (BASE_DIR) atau repository aktif yang dipilih user.
"""

import os
import subprocess
import shutil
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console

_spinner_console = Console()


@contextmanager
def spinner(text: str):
    """
    PRIORITAS 6: spinner konsisten buat semua operasi yang makan waktu
    (push/pull/fetch/merge/clone/extract), ganti print status statis biasa.
    Pakai: `with spinner("Mengirim (push)..."):`
    """
    with _spinner_console.status(f"[cyan]{text}[/cyan]", spinner="dots"):
        yield


# Lokasi root project (folder github-manager/)
BASE_DIR: Path = Path(__file__).resolve().parent.parent
CONFIG_DIR: Path = BASE_DIR / "config"
LOGS_DIR: Path = BASE_DIR / "logs"
BACKUP_DIR: Path = BASE_DIR / "backup"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"

# Versi aplikasi saat ini & lokasi repo GitHub resmi (dipakai modules/update.py)
APP_VERSION: str = "1.5.1"
GITHUB_REPO: str = "catur003/github-manager"


def ensure_dirs() -> None:
    """Pastikan folder config, logs, backup selalu ada."""
    for d in (CONFIG_DIR, LOGS_DIR, BACKUP_DIR):
        d.mkdir(parents=True, exist_ok=True)


def now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Kembalikan waktu sekarang dalam format string."""
    return datetime.now().strftime(fmt)


class GitError(Exception):
    """Exception khusus untuk error Git yang sudah diterjemahkan
    menjadi pesan ramah manusia."""
    def __init__(self, human_message: str, raw_error: str = ""):
        self.human_message = human_message
        self.raw_error = raw_error
        super().__init__(human_message)


def run_git(args: List[str], cwd: Optional[str] = None,
            timeout: int = 60) -> Tuple[bool, str, str]:
    """
    Jalankan perintah git menggunakan subprocess.
    Mengembalikan tuple (sukses, stdout, stderr).
    Tidak pernah melempar traceback ke pemanggil - semua error
    dikembalikan sebagai string agar bisa ditangani dengan pesan ramah.
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        success = result.returncode == 0
        # PRIORITAS 7: catat tiap perintah git ke debug.log (lazy import
        # biar gak circular import, karena logger.py juga import utils.py)
        from modules.logger import log_debug
        log_debug(
            redact_secrets(f"git {' '.join(args)} | cwd={cwd or '.'} | exit={result.returncode}")
        )
        return success, result.stdout.rstrip(), redact_secrets(result.stderr.strip())
    except FileNotFoundError:
        return False, "", "Git tidak ditemukan. Pastikan git sudah terinstall (pkg install git)."
    except subprocess.TimeoutExpired:
        from modules.logger import log_debug
        log_debug(f"git {' '.join(args)} | cwd={cwd or '.'} | TIMEOUT")
        return False, "", "Perintah git terlalu lama merespon (timeout)."
    except Exception as e:  # noqa: BLE001
        return False, "", f"Terjadi kesalahan tak terduga: {e}"


def is_git_repo(path: str) -> bool:
    """Cek apakah path adalah repository git yang valid."""
    if not path or not os.path.isdir(path):
        return False
    ok, out, _ = run_git(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return ok and out.strip() == "true"


def find_git_repos(search_root: str, max_depth: int = 4) -> List[str]:
    """Cari folder yang mengandung .git di bawah search_root (otomatis)."""
    SKIP_DIRS = {"node_modules", ".cache", ".npm", "venv", ".venv",
                 "__pycache__", ".gradle", ".dart_tool", "build", "dist"}
    found = []
    search_root = os.path.expanduser(search_root)
    base_depth = search_root.rstrip(os.sep).count(os.sep)
    for root, dirs, _files in os.walk(search_root):
        depth = root.rstrip(os.sep).count(os.sep) - base_depth
        if depth > max_depth:
            dirs[:] = []
            continue
        if ".git" in dirs:
            found.append(root)
            dirs[:] = [d for d in dirs if d != ".git"]
        # Skip folder berat yang gak mungkin isi repo git lain di dalamnya -
        # mempercepat scan signifikan di HP dengan banyak project/node_modules.
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
    return found


def normalize_repo_url(text: str) -> str:
    """
    Ubah input singkat 'owner/repo' menjadi URL HTTPS GitHub lengkap.
    Kalau input sudah berupa URL (https://, git@, dll) dikembalikan apa adanya.
    """
    text = text.strip()
    if not text:
        return text
    if text.startswith(("http://", "https://", "git@", "ssh://")):
        return text
    parts = text.split("/")
    if len(parts) == 2 and all(parts) and " " not in text:
        owner, repo = parts
        repo = repo[:-4] if repo.endswith(".git") else repo
        return f"https://github.com/{owner}/{repo}.git"
    return text


def extract_owner_repo(url: str) -> Optional[Tuple[str, str]]:
    """Kebalikan dari normalize_repo_url(): dari URL remote GitHub (https,
    ssh://, atau git@ bentuk scp-like), ambil (owner, repo). Return None
    kalau bukan URL GitHub yang valid atau gak bisa diparse.

    Dipakai fitur yang butuh tahu 'owner/repo' dari repo lokal (Hapus
    Repository & Ubah Visibilitas di GitHub) - supaya user gak perlu
    ngetik ulang manual nama repo yang sudah ada di remote origin-nya."""
    if not url:
        return None
    url = url.strip()
    if url.endswith(".git"):
        url = url[:-4]

    # Bentuk scp-like: git@github.com:owner/repo
    if url.startswith("git@"):
        if ":" not in url:
            return None
        path = url.split(":", 1)[1]
    elif url.startswith(("https://", "http://", "ssh://")):
        # Buang skema, ambil bagian setelah host (github.com/owner/repo...)
        without_scheme = url.split("://", 1)[1]
        if "/" not in without_scheme:
            return None
        host, path = without_scheme.split("/", 1)
        if "github.com" not in host.lower():
            return None
    else:
        return None

    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if not owner or not repo:
        return None
    return owner, repo


def sha1_of_file(path: str) -> Optional[str]:
    """Hash SHA1 isi file di disk. None kalau file gak bisa dibaca."""
    import hashlib
    try:
        h = hashlib.sha1()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def sha1_of_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha1(data).hexdigest()


def list_top_level_dirs(root: str, extra_levels: int = 1) -> List[str]:
    """
    Kembalikan daftar sub-folder (relatif, diakhiri '/') di dalam root,
    sampai `extra_levels` tingkat ke dalam - dipakai buat folder picker
    supaya user tinggal pilih, bukan ngetik path manual.
    """
    results: List[str] = []

    def _walk(current: str, rel: str, depth: int):
        try:
            entries = sorted(os.listdir(current))
        except OSError:
            return
        for name in entries:
            if name.startswith("."):
                continue
            full = os.path.join(current, name)
            if os.path.isdir(full):
                rel_path = f"{rel}{name}/"
                results.append(rel_path)
                if depth < extra_levels:
                    _walk(full, rel_path, depth + 1)

    _walk(root, "", 0)
    return results


def human_size(num_bytes: float) -> str:
    """Ubah ukuran byte menjadi format yang mudah dibaca (KB, MB, dst)."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def count_files_in_dir(path: str) -> int:
    """Hitung jumlah file (bukan folder) di dalam path secara rekursif.
    Folder .git dikecualikan karena isinya ratusan file internal git
    (objects/refs) yang bukan bagian dari file project. File/folder hidden
    lain (diawali '.') juga dikecualikan, konsisten dengan konvensi yang
    sama di list_top_level_dirs()/find_git_repos() - supaya hitungan
    'X file berubah' di ringkasan Upload gak salah gara-gara file
    konfigurasi hidden (.env, dll) ikut kehitung."""
    total = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d != ".git" and not d.startswith(".")]
        total += len([f for f in files if not f.startswith(".")])
    return total


def safe_copy_tree(src: str, dst: str) -> None:
    """Copy folder src ke dst, menimpa jika sudah ada isinya."""
    if os.path.isdir(dst):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copytree(src, dst)


def redact_secrets(text: str) -> str:
    """
    Samarkan kredensial (token/password) yang mungkin nempel di URL git
    (pola 'https://user:TOKEN@host/...') sebelum ditulis ke log atau
    ditampilkan ke layar. Dipakai di semua titik logging (log_activity,
    log_debug) supaya token GitHub PAT dsb tidak pernah tersimpan
    plaintext di logs/*.log.
    """
    import re
    return re.sub(r'(https?://)([^/@\s:]+):([^/@\s]+)@', r'\1\2:***@', text)


def safe_zip_member_path(dest_dir: str, member_name: str) -> Optional[str]:
    """
    PRIORITAS SECURITY - Zip Slip protection.
    Hitung path absolut tujuan untuk sebuah entry ZIP, dan pastikan hasilnya
    tetap berada di dalam dest_dir. Entry yang mengandung '../', path absolut,
    atau trik lain untuk keluar dari dest_dir akan ditolak (return None).
    Semua kode yang mengekstrak ZIP (upload, restore backup, update) WAJIB
    lewat fungsi ini, jangan langsung os.path.join(dest_dir, member_name).
    """
    dest_abs = os.path.realpath(dest_dir)
    # Buang null byte & normalisasi separator sebelum join
    member_name = member_name.replace("\x00", "")
    target = os.path.realpath(os.path.join(dest_abs, member_name))
    if target == dest_abs or target.startswith(dest_abs + os.sep):
        return target
    return None


def confirm_text(expected: str, prompt_text: str) -> bool:
    """
    Minta user mengetik ulang teks tertentu (misal 'YA') untuk konfirmasi
    aksi berbahaya. Mengembalikan True hanya jika teks cocok persis.
    """
    import questionary
    answer = questionary.text(prompt_text).ask()
    return answer is not None and answer.strip() == expected


def pick_folder_in_repo(repo: str, prompt_text: str = "Pilih folder tujuan:") -> Optional[str]:
    """
    Tampilkan folder picker interaktif dari isi repo (root + 1 level ke
    dalam) supaya user tinggal pilih, bukan ngetik path manual. Selalu ada
    opsi '/' (root repo) dan 'Path lain (ketik manual)' sebagai fallback.
    Mengembalikan path ABSOLUT ke folder tujuan, atau None kalau dibatalkan.
    """
    import questionary
    subdirs = list_top_level_dirs(repo, extra_levels=1)
    choices = ["/ (root repository)"] + subdirs + ["Path lain (ketik manual)", "Batal"]
    pilihan = questionary.select(prompt_text, choices=choices).ask()
    if not pilihan or pilihan == "Batal":
        return None
    if pilihan == "Path lain (ketik manual)":
        manual = questionary.text("Masukkan sub-folder tujuan (kosongkan untuk root):", default="").ask()
        if manual is None:
            return None
        manual = manual.strip().strip("/")
        return os.path.join(repo, manual) if manual else repo
    if pilihan.startswith("/ (root"):
        return repo
    return os.path.join(repo, pilihan.rstrip("/"))
