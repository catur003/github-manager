"""
logger.py
Menangani pencatatan log aktivitas (logs/activity.log) dan
log error / traceback teknis (logs/error.log).

Pengguna TIDAK PERNAH melihat traceback Python secara langsung.
Traceback hanya disimpan di logs/error.log untuk keperluan debugging.
"""

import traceback
from datetime import datetime

from modules.utils import LOGS_DIR, ensure_dirs

ACTIVITY_LOG = LOGS_DIR / "activity.log"
ERROR_LOG = LOGS_DIR / "error.log"


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


def read_recent_activity(n: int = 20) -> list[str]:
    """Kembalikan n baris terakhir dari log aktivitas."""
    if not ACTIVITY_LOG.exists():
        return []
    with open(ACTIVITY_LOG, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [line.rstrip("\n") for line in lines[-n:]]
