"""
logger.py
Menangani pencatatan log aktivitas (logs/activity.log), log error
(logs/error.log), dan log debug teknis (logs/debug.log).

Pengguna TIDAK PERNAH melihat traceback Python secara langsung.
Traceback hanya disimpan di logs/error.log untuk keperluan debugging.
debug.log mencatat setiap perintah git yang dijalankan (buat trace
teknis kalau ada masalah yang gak sampai jadi exception).
"""

import traceback
from datetime import datetime

from modules.utils import LOGS_DIR, ensure_dirs

ACTIVITY_LOG = LOGS_DIR / "activity.log"
ERROR_LOG = LOGS_DIR / "error.log"
DEBUG_LOG = LOGS_DIR / "debug.log"


def _timestamp() -> str:
    return datetime.now().strftime("%H:%M")


def _full_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_activity(message: str) -> None:
    """Tulis satu baris aktivitas ke logs/activity.log.
    Contoh: '20:14 Repository dipilih'
    """
    ensure_dirs()
    try:
        with open(ACTIVITY_LOG, "a", encoding="utf-8") as f:
            f.write(f"{_timestamp()} {message}\n")
    except OSError:
        # Jangan biarkan kegagalan logging menghentikan aplikasi
        pass


def log_error(context: str, exc: Exception | None = None,
              raw_detail: str = "") -> None:
    """
    Simpan detail error/traceback teknis ke logs/error.log.
    'context' adalah pesan singkat, exc adalah exception (opsional).
    """
    ensure_dirs()
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n[{_full_timestamp()}] {context}\n")
            if raw_detail:
                f.write(f"Detail: {raw_detail}\n")
            if exc is not None:
                f.write(traceback.format_exc())
    except OSError:
        pass


def log_debug(message: str) -> None:
    """
    PRIORITAS 7: catat trace teknis ke logs/debug.log — dipakai buat
    hal-hal yang BUKAN error (contoh: tiap perintah git yang dijalankan,
    exit code, cwd), berguna buat nelusuri masalah yang gak sampai
    melempar exception tapi hasilnya aneh.
    """
    ensure_dirs()
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{_full_timestamp()}] {message}\n")
    except OSError:
        pass


def read_recent_activity(n: int = 20) -> list[str]:
    """Kembalikan n baris terakhir dari log aktivitas."""
    if not ACTIVITY_LOG.exists():
        return []
    with open(ACTIVITY_LOG, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [line.rstrip("\n") for line in lines[-n:]]


def read_recent_debug(n: int = 30) -> list[str]:
    """Kembalikan n baris terakhir dari log debug (perintah git yang dijalankan)."""
    if not DEBUG_LOG.exists():
        return []
    with open(DEBUG_LOG, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [line.rstrip("\n") for line in lines[-n:]]
