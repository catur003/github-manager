"""
settings.py
Menu Pengaturan: menyimpan dan mengubah konfigurasi aplikasi.

Konfigurasi disimpan sebagai JSON di config/config.json.
Tidak ada hardcode path - semua path dibaca dari utils.CONFIG_FILE.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict

import questionary
from rich.console import Console
from rich.table import Table

from modules.utils import CONFIG_FILE, ensure_dirs, run_git, spinner
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


def add_to_repositories(repo_path: str) -> None:
    """Tambah atau update repo ke daftar repositories di config."""
    config = load_config()
    repos = config.setdefault("repositories", [])
    repo_path = os.path.abspath(repo_path)
    # Update existing or add new
    for r in repos:
        if r.get("path") == repo_path:
            r["last_open"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            break
    else:
        repos.append({
            "path": repo_path,
            "last_open": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "favorite": False
        })
    config["repositories"] = repos
    save_config(config)


def get_repositories() -> list:
    """Ambil daftar repositories dari config, sorted by last_open."""
    config = load_config()
    repos = config.get("repositories", [])
    # Sort by last_open desc
    return sorted(repos, key=lambda x: x.get("last_open", ""), reverse=True)


def toggle_favorite(repo_path: str) -> None:
    """Toggle favorite status."""
    config = load_config()
    repos = config.setdefault("repositories", [])
    repo_path = os.path.abspath(repo_path)
    for r in repos:
        if r.get("path") == repo_path:
            r["favorite"] = not r.get("favorite", False)
            break
    save_config(config)


def remove_from_repositories(repo_path: str) -> None:
    """Hapus dari daftar (tidak hapus folder). Kalau repo ini sedang aktif, kosongkan juga."""
    config = load_config()
    repos = config.get("repositories", [])
    repo_path = os.path.abspath(repo_path)
    config["repositories"] = [r for r in repos if r.get("path") != repo_path]
    if config.get("active_repository") == repo_path:
        config["active_repository"] = ""
    save_config(config)


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
                "GitHub Account",
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
        elif choice == "GitHub Account":
            github_account_menu()


def _gh_available() -> bool:
    import shutil
    return shutil.which("gh") is not None


def _get_gh_login_status():
    """Cek status login GitHub CLI. Return (is_logged_in, username_or_None).

    Parsing mendukung 2 format output `gh auth status`:
    - Lama : "Logged in to github.com as <user> (...)"
    - Baru : "Logged in to github.com account <user> (keyring)" (gh >= 2.40,
      kata "as" diganti "account" - ini penyebab username dulu gak
      kedeteksi/gak auto-update di versi gh yang lebih baru.
    """
    import re
    import subprocess
    if not _gh_available():
        return False, None
    try:
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=15)
        logged_in = result.returncode == 0
        username = None
        if logged_in:
            out = (result.stdout or "") + (result.stderr or "")
            m = re.search(r"Logged in to \S+ (?:as|account) (\S+)", out)
            if m:
                username = m.group(1).strip("()")
        return logged_in, username
    except Exception:
        return False, None


def _get_credential_helper() -> str:
    ok, out, _ = run_git(["config", "--global", "credential.helper"])
    return out.strip() if ok and out.strip() else ""


def github_account_menu() -> None:
    """Login Manager - status login GitHub, kelola akun, dan test koneksi."""
    while True:
        console.rule("[bold cyan]GitHub Account")
        config = load_config()
        active_repo = config.get("active_repository", "")

        logged_in, gh_user = _get_gh_login_status()
        cred_helper = _get_credential_helper()
        git_name = run_git(["config", "--get", "user.name"])[1].strip()

        console.print(f"Status Login: {'[green]Logged in[/green]' if logged_in else '[yellow]Belum login[/yellow]'}")
        console.print(f"Username: {gh_user or git_name or '-'}")
        console.print(f"Credential Helper: {cred_helper or '[yellow]Belum aktif[/yellow]'}")
        console.print(f"Repository Aktif: {active_repo or '-'}")
        if active_repo and os.path.isdir(active_repo):
            ok, branch, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=active_repo)
            console.print(f"Branch Aktif: {branch.strip() if ok and branch.strip() else '-'}")
        else:
            console.print("Branch Aktif: -")

        if not cred_helper:
            aktifkan = questionary.confirm(
                "Credential helper belum aktif. Aktifkan sekarang agar login tidak perlu diulang terus?",
                default=False,
            ).ask()
            if aktifkan:
                ok, _out, err = run_git(["config", "--global", "credential.helper", "store"])
                if ok:
                    console.print("[green]Credential helper diaktifkan.[/green]")
                    log_activity("Credential helper diaktifkan")
                else:
                    console.print(f"[red]Gagal mengaktifkan credential helper: {err}[/red]")

        choice = questionary.select(
            "Aksi:", choices=["Login", "Logout", "Ganti Akun", "Test Login", "Refresh dari GitHub", "Kembali"]
        ).ask()

        if choice is None or choice == "Kembali":
            return

        if choice == "Login":
            _do_login()
        elif choice == "Logout":
            _do_logout()
        elif choice == "Ganti Akun":
            console.print("[cyan]Logout dari akun saat ini, lalu login dengan akun baru.[/cyan]")
            _do_logout()
            _do_login()
        elif choice == "Test Login":
            _do_test_login(active_repo)
        elif choice == "Refresh dari GitHub":
            _refresh_dari_github()

        questionary.text("\nTekan Enter untuk kembali...").ask()


def _do_login() -> None:
    if _gh_available():
        console.print("[cyan]Membuka proses login GitHub CLI (gh auth login)...[/cyan]")
        exit_code = os.system("gh auth login")
        log_activity("Login GitHub via gh CLI dijalankan")
        if exit_code == 0:
            _auto_isi_identitas_dari_gh()
    else:
        console.print(
            "[yellow]GitHub CLI (gh) tidak terpasang.[/yellow]\n"
            "Login manual: saat push/pull pertama kali, git akan minta username & "
            "Personal Access Token (PAT). Aktifkan credential helper di menu ini "
            "supaya kredensial tersimpan."
        )


def _auto_isi_identitas_dari_gh() -> None:
    """Setelah gh auth login berhasil, isi otomatis user.name/user.email git
    kalau belum diatur, supaya commit gak gagal gara-gara identitas kosong.
    Login GitHub (autentikasi) dan identitas commit itu 2 hal terpisah di git,
    jadi ini menjembatani biar user gak bingung."""
    import subprocess

    current_name = run_git(["config", "--get", "user.name"])[1].strip()
    current_email = run_git(["config", "--get", "user.email"])[1].strip()
    if current_name and current_email:
        return  # sudah diatur, jangan timpa

    try:
        login = subprocess.run(["gh", "api", "user", "--jq", ".login"],
                                capture_output=True, text=True, timeout=15).stdout.strip()
        gh_name = subprocess.run(["gh", "api", "user", "--jq", ".name"],
                                  capture_output=True, text=True, timeout=15).stdout.strip()
        gh_id = subprocess.run(["gh", "api", "user", "--jq", ".id"],
                                capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception:
        return

    if not login:
        return

    if not current_name:
        nama = gh_name if gh_name and gh_name != "null" else login
        run_git(["config", "--global", "user.name", nama])
        config = load_config()
        config["git_name"] = nama
        save_config(config)
        console.print(f"[green]Nama Git otomatis diisi dari akun GitHub: {nama}[/green]")

    if not current_email and gh_id:
        # Email publik GitHub sering disembunyikan, jadi pakai noreply email
        # bawaan GitHub (aman dipakai untuk commit, gak expose email asli).
        noreply = f"{gh_id}+{login}@users.noreply.github.com"
        run_git(["config", "--global", "user.email", noreply])
        config = load_config()
        config["git_email"] = noreply
        save_config(config)
        console.print(f"[green]Email Git otomatis diisi (noreply GitHub): {noreply}[/green]")
        console.print("[dim]Mau pakai email lain? Ubah di menu Pengaturan > Email Git.[/dim]")


def _refresh_dari_github() -> None:
    """Refresh manual - ambil ulang nama & email dari akun GitHub yang lagi
    login, lalu TIMPA config lokal (beda dari _auto_isi_identitas_dari_gh
    yang cuma jalan sekali pas login & skip kalau udah keisi).
    Ini jawaban buat kasus: user udah login lama, tapi nama/email di
    aplikasi masih kosong/data lama dan gak ada cara refresh manual."""
    import subprocess

    if not _gh_available():
        console.print("[yellow]GitHub CLI (gh) tidak terpasang, tidak bisa refresh otomatis.[/yellow]")
        return
    logged_in, _ = _get_gh_login_status()
    if not logged_in:
        console.print("[yellow]Belum login ke GitHub CLI. Login dulu sebelum refresh.[/yellow]")
        return

    with spinner("Mengambil data akun dari GitHub..."):
        try:
            login = subprocess.run(["gh", "api", "user", "--jq", ".login"],
                                    capture_output=True, text=True, timeout=15).stdout.strip()
            gh_name = subprocess.run(["gh", "api", "user", "--jq", ".name"],
                                      capture_output=True, text=True, timeout=15).stdout.strip()
            gh_id = subprocess.run(["gh", "api", "user", "--jq", ".id"],
                                    capture_output=True, text=True, timeout=15).stdout.strip()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Gagal mengambil data dari GitHub.[/red]")
            log_error("Gagal refresh identitas dari GitHub", e)
            return

    if not login:
        console.print("[red]Gagal mengambil username GitHub. Coba Test Login dulu.[/red]")
        return

    nama_baru = gh_name if gh_name and gh_name != "null" else login
    email_baru = f"{gh_id}+{login}@users.noreply.github.com" if gh_id else ""

    config = load_config()
    console.print(
        f"Nama Git  : {config.get('git_name') or '-'} -> [green]{nama_baru}[/green]\n"
        f"Email Git : {config.get('git_email') or '-'} -> [green]{email_baru or '-'}[/green]"
    )
    lanjut = questionary.confirm("Timpa dengan data di atas?", default=True).ask()
    if not lanjut:
        console.print("[yellow]Refresh dibatalkan.[/yellow]")
        return

    run_git(["config", "--global", "user.name", nama_baru])
    config["git_name"] = nama_baru
    if email_baru:
        run_git(["config", "--global", "user.email", email_baru])
        config["git_email"] = email_baru
    save_config(config)
    console.print("[green]✓ Nama & Email berhasil di-refresh dari GitHub.[/green]")
    log_activity("Identitas Git di-refresh manual dari GitHub")


def _do_logout() -> None:
    if _gh_available():
        os.system("gh auth logout")
        log_activity("Logout GitHub via gh CLI dijalankan")
    else:
        console.print(
            "[yellow]GitHub CLI (gh) tidak terpasang.[/yellow]\n"
            "Untuk logout manual, hapus kredensial tersimpan, misalnya:\n"
            "git credential-store --file ~/.git-credentials erase"
        )


def _do_test_login(active_repo: str) -> None:
    if not active_repo or not os.path.isdir(active_repo):
        console.print("[yellow]Belum ada repository aktif untuk dites. Pilih repository dulu.[/yellow]")
        return
    ok, out, err = run_git(["ls-remote", "origin"], cwd=active_repo)
    if ok:
        console.print("[green]Test login berhasil, koneksi ke remote OK.[/green]")
    else:
        console.print(f"[red]Test gagal: {err or out}[/red]")

def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Pengaturan[/bold cyan]\n"
        "Menu ini dipakai untuk mengatur identitas Git kamu (nama & email),\n"
        "alamat remote default, repository default, serta beberapa\n"
        "pengaturan keamanan seperti konfirmasi sebelum aksi berbahaya.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()
