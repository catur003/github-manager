"""
settings.py
Menu Pengaturan: menyimpan dan mengubah konfigurasi aplikasi.

Konfigurasi disimpan sebagai JSON di config/config.json.
Tidak ada hardcode path - semua path dibaca dari utils.CONFIG_FILE.
"""

import json
from typing import Any, Dict

import questionary
from rich.console import Console
from rich.table import Table

from modules.utils import CONFIG_FILE, ensure_dirs, run_git
from modules.logger import log_activity, log_error

console = Console()

DEFAULT_CONFIG: Dict[str, Any] = {
    "git_name": "",
    "git_email": "",
    "remote_origin": "",
    "default_repository": "",
    "active_repository": "",
    "backup_otomatis": True,
    "konfirmasi_delete": True,
    "konfirmasi_force_push": True,
    "tema": "default",
}


def record_repo_event(repo_path: str, key: str) -> None:
    """
    PRIORITAS 4: catat timestamp event per-repo (last_push/last_pull),
    disimpan di config['repo_history'][repo_path][key], dipakai Dashboard.
    """
    from modules.utils import now_str

    config = load_config()
    history = config.setdefault("repo_history", {})
    entry = history.setdefault(repo_path, {})
    entry[key] = now_str()
    save_config(config)


def get_repo_event(repo_path: str, key: str) -> str:
    """Ambil timestamp event terakhir untuk repo ini, atau '-' kalau belum ada."""
    config = load_config()
    return config.get("repo_history", {}).get(repo_path, {}).get(key, "-")


def load_config() -> Dict[str, Any]:
    """Baca file config.json. Jika belum ada, buat dengan nilai default."""
    ensure_dirs()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError) as e:
        log_error("Gagal membaca config.json", e)
        console.print("[yellow]Konfigurasi rusak, memakai nilai default.[/yellow]")
        return dict(DEFAULT_CONFIG)


def save_config(config: Dict[str, Any]) -> bool:
    """Simpan config ke file config.json."""
    ensure_dirs()
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        log_error("Gagal menyimpan config.json", e)
        console.print("[red]Gagal menyimpan pengaturan.[/red]")
        return False


def show_settings_table(config: Dict[str, Any]) -> None:
    table = Table(title="Pengaturan Saat Ini", show_header=True, header_style="bold cyan")
    table.add_column("Pengaturan")
    table.add_column("Nilai")
    table.add_row("Nama Git", config.get("git_name") or "-")
    table.add_row("Email Git", config.get("git_email") or "-")
    table.add_row("Remote Origin", config.get("remote_origin") or "-")
    table.add_row("Default Repository", config.get("default_repository") or "-")
    table.add_row("Backup Otomatis", "ON" if config.get("backup_otomatis") else "OFF")
    table.add_row("Konfirmasi Sebelum Delete", "ON" if config.get("konfirmasi_delete") else "OFF")
    table.add_row("Konfirmasi Sebelum Force Push", "ON" if config.get("konfirmasi_force_push") else "OFF")
    table.add_row("Tema Warna", config.get("tema") or "default")
    console.print(table)


def menu() -> None:
    """Tampilkan menu Pengaturan."""
    config = load_config()
    while True:
        console.rule("[bold cyan]Pengaturan")
        show_settings_table(config)
        choice = questionary.select(
            "Pilih pengaturan yang ingin diubah:",
            choices=[
                "Nama Git",
                "Email Git",
                "Remote Origin",
                "Default Repository",
                "Toggle Backup Otomatis",
                "Toggle Konfirmasi Delete",
                "Toggle Konfirmasi Force Push",
                "Tema Warna",
                "? Help",
                "Kembali",
            ],
        ).ask()

        if choice is None or choice == "Kembali":
            return

        if choice == "? Help":
            show_help()
            continue

        if choice == "Nama Git":
            val = questionary.text("Masukkan nama Git:", default=config.get("git_name", "")).ask()
            if val is not None:
                config["git_name"] = val
                ok, _out, err = run_git(["config", "--global", "user.name", val])
                if not ok:
                    console.print(f"[red]Gagal set nama git: {err}[/red]")
                save_config(config)
                log_activity(f"Nama Git diubah menjadi {val}")

        elif choice == "Email Git":
            val = questionary.text("Masukkan email Git:", default=config.get("git_email", "")).ask()
            if val is not None:
                config["git_email"] = val
                ok, _out, err = run_git(["config", "--global", "user.email", val])
                if not ok:
                    console.print(f"[red]Gagal set email git: {err}[/red]")
                save_config(config)
                log_activity(f"Email Git diubah menjadi {val}")

        elif choice == "Remote Origin":
            val = questionary.text("Masukkan URL remote origin:", default=config.get("remote_origin", "")).ask()
            if val is not None:
                config["remote_origin"] = val
                save_config(config)
                log_activity("Remote origin diubah di pengaturan")

        elif choice == "Default Repository":
            val = questionary.text("Masukkan path default repository:",
                                    default=config.get("default_repository", "")).ask()
            if val is not None:
                config["default_repository"] = val
                save_config(config)
                log_activity("Default repository diubah")

        elif choice == "Toggle Backup Otomatis":
            config["backup_otomatis"] = not config.get("backup_otomatis", True)
            save_config(config)
            log_activity(f"Backup Otomatis diset {'ON' if config['backup_otomatis'] else 'OFF'}")

        elif choice == "Toggle Konfirmasi Delete":
            config["konfirmasi_delete"] = not config.get("konfirmasi_delete", True)
            save_config(config)
            log_activity(f"Konfirmasi Delete diset {'ON' if config['konfirmasi_delete'] else 'OFF'}")

        elif choice == "Toggle Konfirmasi Force Push":
            config["konfirmasi_force_push"] = not config.get("konfirmasi_force_push", True)
            save_config(config)
            log_activity(f"Konfirmasi Force Push diset {'ON' if config['konfirmasi_force_push'] else 'OFF'}")

        elif choice == "Tema Warna":
            tema = questionary.select("Pilih tema warna:", choices=["default", "gelap", "terang"]).ask()
            if tema:
                config["tema"] = tema
                save_config(config)
                log_activity(f"Tema warna diubah menjadi {tema}")


def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Pengaturan[/bold cyan]\n"
        "Menu ini dipakai untuk mengatur identitas Git kamu (nama & email),\n"
        "alamat remote default, repository default, serta beberapa\n"
        "pengaturan keamanan seperti konfirmasi sebelum aksi berbahaya.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()
