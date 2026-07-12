"""
utils.py
Fungsi-fungsi bantu (utility) yang dipakai di seluruh module.
Tidak boleh ada hardcode path di sini - semua path relatif terhadap
lokasi project (BASE_DIR) atau repository aktif yang dipilih user.
"""

import os
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# Lokasi root project (folder github-manager/)
BASE_DIR: Path = Path(__file__).resolve().parent.parent
CONFIG_DIR: Path = BASE_DIR / "config"
LOGS_DIR: Path = BASE_DIR / "logs"
BACKUP_DIR: Path = BASE_DIR / "backup"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"


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
        return success, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return False, "", "Git tidak ditemukan. Pastikan git sudah terinstall (pkg install git)."
    except subprocess.TimeoutExpired:
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
    return found


def human_size(num_bytes: float) -> str:
    """Ubah ukuran byte menjadi format yang mudah dibaca (KB, MB, dst)."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def count_files_in_dir(path: str) -> int:
    """Hitung jumlah file (bukan folder) di dalam path secara rekursif."""
    total = 0
    for _root, _dirs, files in os.walk(path):
        total += len(files)
    return total


def safe_copy_tree(src: str, dst: str) -> None:
    """Copy folder src ke dst, menimpa jika sudah ada isinya."""
    if os.path.isdir(dst):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copytree(src, dst)


def confirm_text(expected: str, prompt_text: str) -> bool:
    """
    Minta user mengetik ulang teks tertentu (misal 'YA') untuk konfirmasi
    aksi berbahaya. Mengembalikan True hanya jika teks cocok persis.
    """
    import questionary
    answer = questionary.text(prompt_text).ask()
    return answer is not None and answer.strip() == expected
