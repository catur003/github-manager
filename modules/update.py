"""
update.py
PRIORITAS 5: Update Manager - cek versi terbaru dari GitHub Releases,
tawarkan auto-update (download + timpa file .py, config/logs/backup
dibiarkan aman/tidak ikut ketimpa).
"""

import json
import os
import shutil
import tempfile
import urllib.request
import urllib.error
import zipfile

import questionary
from rich.console import Console

from modules.utils import APP_VERSION, GITHUB_REPO, BASE_DIR
from modules.logger import log_activity, log_error

console = Console()

# Folder/file yang TIDAK boleh ketimpa/tergantikan saat auto-update,
# karena isinya data milik user (bukan bagian dari source code aplikasi).
_PROTECTED = {"config", "logs", "backup", ".git"}


def _parse_version(v: str) -> tuple:
    v = v.strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _fetch_latest_release() -> dict | None:
    """Ambil info release terbaru dari GitHub API. None kalau gagal/belum ada release."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "github-manager-updater"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # repo belum punya release sama sekali
        log_error("Gagal cek update (HTTPError)", e)
        return None
    except Exception as e:  # noqa: BLE001
        log_error("Gagal cek update", e)
        return None


def check_update(silent: bool = False) -> None:
    """Cek apakah ada versi baru. silent=True dipakai buat cek otomatis saat start (tanpa spam kalau gagal/sudah terbaru)."""
    if not silent:
        console.print("[cyan]Mengecek update dari GitHub...[/cyan]")

    release = _fetch_latest_release()
    if release is None:
        if not silent:
            console.print(
                f"[yellow]Belum ada release resmi di github.com/{GITHUB_REPO}, "
                f"atau tidak ada koneksi internet.[/yellow]"
            )
        return

    latest_tag = release.get("tag_name", "")
    latest_ver = _parse_version(latest_tag)
    current_ver = _parse_version(APP_VERSION)

    if latest_ver <= current_ver:
        if not silent:
            console.print(f"[green]Sudah pakai versi terbaru (v{APP_VERSION}).[/green]")
        return

    console.print(
        f"\n[bold yellow]Update tersedia![/bold yellow] "
        f"v{APP_VERSION} -> {latest_tag}\n"
    )
    notes = (release.get("body") or "").strip()
    if notes:
        console.print(f"[dim]Catatan rilis:[/dim]\n{notes}\n")

    mau_update = questionary.confirm("Update sekarang?", default=True).ask()
    if not mau_update:
        console.print("[yellow]Update dilewati.[/yellow]")
        return

    zip_url = release.get("zipball_url")
    if not zip_url:
        console.print("[red]Tidak menemukan file update di release ini.[/red]")
        return

    _do_update(zip_url, latest_tag)


def _do_update(zip_url: str, latest_tag: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, "update.zip")
        try:
            console.print("[cyan]Mengunduh update...[/cyan]")
            req = urllib.request.Request(zip_url, headers={"User-Agent": "github-manager-updater"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(zip_path, "wb") as f:
                shutil.copyfileobj(resp, f)
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Gagal mengunduh update: {e}[/red]")
            log_error("Gagal download update", e)
            return

        extract_dir = os.path.join(tmp, "extracted")
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)
        except zipfile.BadZipFile as e:
            console.print("[red]File update rusak/tidak valid.[/red]")
            log_error("ZIP update rusak", e)
            return

        # GitHub zipball selalu bungkus isi dalam 1 folder: <owner>-<repo>-<sha>/
        top_items = os.listdir(extract_dir)
        if len(top_items) != 1:
            console.print("[red]Struktur file update tidak dikenali.[/red]")
            return
        source_root = os.path.join(extract_dir, top_items[0])

        console.print("[cyan]Menerapkan update (file lama akan ditimpa)...[/cyan]")
        copied = 0
        for name in os.listdir(source_root):
            if name in _PROTECTED:
                continue  # lewati folder data user
            src = os.path.join(source_root, name)
            dst = os.path.join(BASE_DIR, name)
            try:
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                copied += 1
            except OSError as e:
                console.print(f"[red]Gagal menimpa '{name}': {e}[/red]")
                log_error(f"Gagal update file {name}", e)

        console.print(
            f"[green]✓ Update ke {latest_tag} selesai[/green] ({copied} item diperbarui).\n"
            f"[dim]Silakan restart aplikasi untuk memakai versi baru.[/dim]"
        )
        log_activity(f"Update berhasil ke {latest_tag}")


def menu() -> None:
    console.rule("[bold cyan]Update Manager")
    console.print(f"Versi terpasang saat ini: [bold]v{APP_VERSION}[/bold]\n")
    check_update(silent=False)
    questionary.text("\nTekan Enter untuk kembali...").ask()
