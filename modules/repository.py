"""
repository.py
Menu Repository: pilih repository, cari otomatis, clone, tambah,
ganti, dan lihat repository aktif.
"""

import os
from typing import Optional, Tuple

import questionary
from rich.console import Console

from modules.utils import run_git, is_git_repo, find_git_repos, normalize_repo_url, GitError, spinner
from modules.settings import load_config, save_config, get_repositories, add_to_repositories, toggle_favorite, remove_from_repositories
from modules.logger import log_activity, log_error
from datetime import datetime

console = Console()


def _set_active_repository(path: str) -> None:
    config = load_config()
    config["active_repository"] = os.path.abspath(path)
    save_config(config)
    from modules.settings import add_to_repositories
    add_to_repositories(path)


def pilih_repository() -> None:
    """Pilih repository dari daftar hasil pencarian otomatis di home directory."""
    home = os.path.expanduser("~")
    console.print("[cyan]Mencari repository Git di sekitar home directory...[/cyan]")
    repos = find_git_repos(home)
    if not repos:
        console.print("[yellow]Tidak ditemukan repository Git. "
                       "Gunakan 'Tambah Repository' untuk memasukkan path manual.[/yellow]")
        return
    pilihan = questionary.select("Pilih repository:", choices=repos + ["Batal"]).ask()
    if pilihan and pilihan != "Batal":
        _set_active_repository(pilihan)
        console.print(f"[green]Repository aktif diubah ke: {pilihan}[/green]")
        log_activity(f"Repository dipilih: {pilihan}")


def cari_repository_otomatis() -> None:
    """Cari repository Git otomatis mulai dari path yang diberikan user."""
    start_path = questionary.text(
        "Masukkan folder awal pencarian (kosongkan untuk home):", default=""
    ).ask()
    if start_path is None:
        return
    start_path = start_path.strip() or os.path.expanduser("~")
    if not os.path.isdir(start_path):
        console.print("[red]Folder tidak ditemukan.[/red]")
        return
    console.print(f"[cyan]Mencari repository di {start_path}...[/cyan]")
    repos = find_git_repos(start_path)
    if not repos:
        console.print("[yellow]Tidak ada repository Git ditemukan di folder tersebut.[/yellow]")
        return
    pilihan = questionary.select("Repository ditemukan:", choices=repos + ["Batal"]).ask()
    if pilihan and pilihan != "Batal":
        _set_active_repository(pilihan)
        console.print(f"[green]Repository aktif diubah ke: {pilihan}[/green]")
        log_activity(f"Repository dipilih (pencarian otomatis): {pilihan}")


def _valid_repo_input(raw: str) -> bool:
    """Validasi input clone: harus URL (http/https/git@/ssh://) atau
    shorthand 'owner/repo' yang valid."""
    raw = raw.strip()
    if not raw:
        return False
    if raw.startswith(("http://", "https://", "git@", "ssh://")):
        return True
    parts = raw.split("/")
    return len(parts) == 2 and all(parts) and " " not in raw


def clone_repository() -> None:
    """Clone Repository Wizard: input URL/owner-repo (dengan validasi),
    pilih folder tujuan, cek apakah folder sudah ada + konfirmasi
    overwrite, lalu clone otomatis."""
    raw = questionary.text(
        "Masukkan URL repository atau 'owner/repo' (contoh: catur003/ZenStock):"
    ).ask()
    if not raw:
        return
    if not _valid_repo_input(raw):
        console.print(
            "[red]Format tidak valid.[/red] Gunakan URL lengkap "
            "(https://github.com/owner/repo.git) atau bentuk singkat 'owner/repo'."
        )
        return
    url = normalize_repo_url(raw)

    nama_default = url.rstrip("/").split("/")[-1].replace(".git", "")
    # PRIORITAS 2 #5: repository HARUS di-clone ke ~/<nama>, bukan ikut cwd
    # aplikasi (sebelumnya bisa jadi ~/github-manager/ZenStock kalau app
    # dijalankan dari situ). Selalu resolve ke path absolut di HOME.
    home = os.path.expanduser("~")

    while True:
        tujuan = questionary.text(
            f"Masukkan folder tujuan (kosongkan untuk ~/{nama_default}):", default=""
        ).ask()
        if tujuan is None:
            return
        if tujuan.strip():
            dest_path = tujuan.strip() if os.path.isabs(tujuan.strip()) else os.path.join(home, tujuan.strip())
        else:
            dest_path = os.path.join(home, nama_default)

        if os.path.exists(dest_path) and os.listdir(dest_path):
            console.print(f"[yellow]Folder '{dest_path}' sudah ada dan tidak kosong.[/yellow]")
            aksi = questionary.select(
                "Folder tujuan sudah terisi. Pilih aksi:",
                choices=["Timpa (hapus isi folder lalu clone ulang)", "Pilih folder lain", "Batal"],
            ).ask()
            if not aksi or aksi == "Batal":
                return
            if aksi == "Pilih folder lain":
                continue
            konfirmasi = questionary.confirm(
                f"Yakin hapus semua isi '{dest_path}' lalu clone ulang? Aksi ini tidak dapat dibatalkan.",
                default=False,
            ).ask()
            if not konfirmasi:
                continue
            try:
                import shutil as _shutil
                _shutil.rmtree(dest_path)
            except OSError as e:
                console.print(f"[red]Gagal menghapus folder lama: {e}[/red]")
                return
        break

    with spinner(f"Sedang melakukan clone ke {dest_path}..."):
        ok, out, err = run_git(["clone", url, dest_path])
    if not ok:
        console.print(f"[red]Clone gagal: {_human_git_error(err)}[/red]")
        log_error("Clone repository gagal", raw_detail=err)
        return
    console.print(f"[green]Clone berhasil ke {dest_path}.[/green]\n{out}")
    log_activity(f"Repository di-clone dari {url} ke {dest_path}")

    jadikan_aktif = questionary.confirm(
        f"Jadikan '{nama_default}' sebagai repository aktif?", default=True
    ).ask()
    if jadikan_aktif:
        _set_active_repository(dest_path)


def tambah_repository() -> None:
    """Tambah repository dengan memasukkan path secara manual."""
    path = questionary.text("Masukkan path folder repository:").ask()
    if not path:
        return
    path = os.path.expanduser(path.strip())
    if not is_git_repo(path):
        console.print("[red]Repository tidak ditemukan. Pastikan folder tersebut adalah repository Git "
                       "(mengandung folder .git).[/red]")
        return
    _set_active_repository(path)
    console.print(f"[green]Repository '{path}' berhasil ditambahkan dan dijadikan aktif.[/green]")
    log_activity(f"Repository ditambahkan: {path}")


def ganti_repository() -> None:
    """Ganti repository aktif ke path lain."""
    tambah_repository()


def _rev_list_ahead_behind(repo: str, upstream: str) -> Optional[Tuple[int, int]]:
    """Hitung (ahead, behind) HEAD relatif ke upstream lewat
    'git rev-list --left-right --count HEAD...<upstream>'.
    ahead = commit lokal yang belum ada di upstream.
    behind = commit upstream yang belum ada di lokal.
    Return None kalau perintahnya gagal (mis. upstream tidak valid)."""
    ok, out, _err = run_git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"], cwd=repo)
    if not ok or not out.strip():
        return None
    parts = out.strip().split()
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _working_tree_status(repo: str) -> Tuple[bool, int, int, int]:
    """Baca 'git status --porcelain' dan kembalikan (is_clean, modified, deleted, untracked).
    Ini SENGAJA dipisah dari status ahead/behind commit, supaya user bisa
    bedain 'perubahan Git (commit)' vs 'perubahan file lokal yang belum di-commit'."""
    ok, out, _err = run_git(["status", "--porcelain"], cwd=repo)
    if not ok:
        return True, 0, 0, 0
    modified = deleted = untracked = 0
    for line in out.splitlines():
        if not line:
            continue
        code = line[:2]
        if code == "??":
            untracked += 1
        elif "D" in code:
            deleted += 1
        else:
            modified += 1
    is_clean = (modified + deleted + untracked) == 0
    return is_clean, modified, deleted, untracked


def _print_working_tree(is_clean: bool, modified: int, deleted: int, untracked: int) -> None:
    console.print("\n[bold]Working Tree[/bold]\n")
    if is_clean:
        console.print("✓ Clean")
        return
    if modified:
        console.print(f"Modified  : {modified}")
    if deleted:
        console.print(f"Deleted   : {deleted}")
    if untracked:
        console.print(f"Untracked : {untracked}")


def _diff_counts(repo: str, range_expr: str) -> Tuple[int, int, int]:
    """Hitung (baru, berubah, hilang) dari 'git diff --name-status <range_expr>'."""
    ok, out, _e = run_git(["diff", "--name-status", range_expr], cwd=repo)
    baru = berubah = hilang = 0
    if ok and out:
        for line in out.splitlines():
            code = line.split("\t")[0].strip()
            if code.startswith("A"):
                baru += 1
            elif code.startswith("M"):
                berubah += 1
            elif code.startswith("D"):
                hilang += 1
    return baru, berubah, hilang


def compare_repository() -> None:
    """Repository Compare: bandingkan repository lokal dengan GitHub.

    Alur baru (menggantikan versi lama yang selalu langsung 'git diff
    HEAD..origin' tanpa cek arah, sehingga repo yang cuma 'ahead' pun bisa
    salah ditampilkan seolah ada banyak file berubah):

    1. Tentukan status lebih dulu lewat ahead/behind commit count
       (git rev-list --left-right --count) -> Sinkron / Lokal Lebih Baru /
       GitHub Lebih Baru / Diverged.
    2. Diff file HANYA dihitung kalau memang relevan untuk status itu
       (cuma saat GitHub Lebih Baru - karena itu satu-satunya kasus di mana
       "file apa yang bakal berubah" jelas & searah).
    3. Working Tree (perubahan file lokal yang belum di-commit) ditampilkan
       terpisah dari status commit, supaya tidak tercampur maknanya.
    """
    from modules.utils import GitError  # noqa: F401 (dipakai di except di menu())
    from modules import preflight

    repo = _get_active_repo_local()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=True, label="Compare Repository"):
        return

    branch = preflight.get_current_branch(repo) or "-"
    with spinner("Mengambil data terbaru dari GitHub (fetch)..."):
        run_git(["fetch", "origin"], cwd=repo, timeout=60)

    upstream = f"origin/{branch}"
    ok_local, local_commit, _e1 = run_git(["rev-parse", "--short", "HEAD"], cwd=repo)
    ok_remote, remote_commit, _e2 = run_git(["rev-parse", "--short", upstream], cwd=repo)

    console.print("\n[bold cyan]════════ Compare Repository ════════[/bold cyan]\n")
    console.print(f"Repository : {os.path.basename(repo)}")
    console.print(f"Branch     : {branch}")

    if not ok_remote:
        console.print(f"\n[yellow]Branch '{branch}' tidak ditemukan di GitHub (origin/{branch}).[/yellow]")
        return

    console.print(f"\nCommit Lokal  : {local_commit if ok_local else '-'}")
    console.print(f"Commit GitHub : {remote_commit}")
    console.print("\n" + "─" * 28)

    is_clean, modified, deleted, untracked = _working_tree_status(repo)
    ahead_behind = _rev_list_ahead_behind(repo, upstream)

    if ahead_behind is None:
        # Fallback kalau rev-list gagal - tetap kasih info, jangan diam saja.
        console.print("\n[yellow]Tidak bisa menentukan status ahead/behind dari Git.[/yellow]")
        _print_working_tree(is_clean, modified, deleted, untracked)
        return

    ahead, behind = ahead_behind
    console.print("\n[bold]Status[/bold]\n")

    # --- Sinkron ---
    if ahead == 0 and behind == 0:
        console.print("✅ [bold green]Repository Sinkron[/bold green]")
        _print_working_tree(is_clean, modified, deleted, untracked)
        console.print("\nTidak ada tindakan yang diperlukan.")
        return

    # --- Lokal Lebih Baru (ahead saja) ---
    if ahead > 0 and behind == 0:
        console.print("🟢 [bold green]Lokal Lebih Baru[/bold green]\n")
        console.print(f"Ahead  : {ahead} commit")
        console.print(f"Behind : {behind} commit")
        _print_working_tree(is_clean, modified, deleted, untracked)
        console.print("\nRepository lokal memiliki commit\nyang belum ada di GitHub.")
        console.print("\n[bold]Tindakan Disarankan[/bold]\n\n✓ Push Repository")
        # Sengaja TIDAK menghitung/menampilkan File Baru/Berubah/Hilang di sini -
        # commit yang beda arahnya cuma dari lokal, belum tentu relevan
        # dibandingkan terhadap remote.

        aksi = questionary.select("Pilih aksi:", choices=["Push Repository", "Batal"]).ask()
        if aksi == "Push Repository":
            from modules import push as push_module
            push_module.push()
        return

    # --- GitHub Lebih Baru (behind saja) ---
    if ahead == 0 and behind > 0:
        console.print("🔵 [bold blue]GitHub Lebih Baru[/bold blue]\n")
        console.print(f"Ahead  : {ahead}")
        console.print(f"Behind : {behind}")

        baru, berubah, hilang = _diff_counts(repo, f"HEAD..{upstream}")
        console.print("\n[bold]Perubahan dari GitHub[/bold]\n")
        console.print(f"🟢 File Baru      : {baru}")
        console.print(f"🟡 File Berubah   : {berubah}")
        console.print(f"🔴 File Hilang    : {hilang}")

        _print_working_tree(is_clean, modified, deleted, untracked)
        console.print("\n[bold]Tindakan Disarankan[/bold]\n\n✓ Pull Repository")

        aksi = questionary.select(
            "Pilih aksi:", choices=["Pull Repository", "Clone ulang repository", "Batal"]
        ).ask()
        if aksi == "Pull Repository":
            from modules import pull as pull_module
            pull_module.pull()
        elif aksi == "Clone ulang repository":
            _reclone_repository(repo)
        return

    # --- Diverged (ahead & behind sama-sama > 0) ---
    console.print("🟠 [bold dark_orange]Repository Diverged[/bold dark_orange]\n")
    console.print(f"Ahead  : {ahead}")
    console.print(f"Behind : {behind}")
    console.print("\nRepository lokal dan GitHub\nsama-sama memiliki commit baru.")
    console.print("\n[yellow]Push atau Pull langsung dapat\nmenyebabkan konflik.[/yellow]")
    # Sengaja tidak memaksa hitung diff satu arah - kedua sisi sama-sama
    # punya perubahan, jadi "File Baru/Berubah/Hilang" versi satu arah
    # cuma akan menyesatkan.
    _print_working_tree(is_clean, modified, deleted, untracked)
    console.print("\n[bold]Tindakan Disarankan[/bold]\n\n✓ Fetch\n✓ Review Commit\n✓ Merge / Rebase")

    aksi = questionary.select(
        "Pilih aksi:",
        choices=["Fetch ulang", "Lihat Log Commit (Review)", "Batal"],
    ).ask()
    if aksi == "Fetch ulang":
        with spinner("Fetch ulang dari origin..."):
            run_git(["fetch", "origin"], cwd=repo, timeout=60)
        console.print("[green]Fetch selesai.[/green]")
    elif aksi == "Lihat Log Commit (Review)":
        ok_log, log_out, _e = run_git(
            ["log", "--oneline", "--graph", "--left-right", f"HEAD...{upstream}"], cwd=repo
        )
        if ok_log and log_out:
            console.print(f"\n{log_out}")
        else:
            console.print("[yellow]Tidak ada log yang bisa ditampilkan.[/yellow]")


def _reclone_repository(repo: str) -> None:
    """Hapus folder repo lama lalu clone ulang dari remote 'origin'.
    Minta user ketik ulang path persis untuk konfirmasi, supaya tidak
    salah menghapus folder yang bukan dimaksud."""
    ok, url, _err = run_git(["remote", "get-url", "origin"], cwd=repo)
    if not ok or not url:
        console.print("[red]Tidak bisa mendapatkan URL remote 'origin'.[/red]")
        return
    console.print(
        f"[yellow]⚠ Ini akan MENGHAPUS folder berikut lalu clone ulang dari awal:[/yellow]\n{repo}\n"
    )
    ketik = questionary.text(
        "Ketik ulang path di atas PERSIS untuk konfirmasi (disarankan copy-paste):"
    ).ask()
    if ketik is None or ketik.strip() != repo:
        console.print("[yellow]Dibatalkan (path tidak cocok).[/yellow]")
        return
    try:
        import shutil as _shutil
        with spinner("Menghapus folder lama..."):
            _shutil.rmtree(repo)
        with spinner(f"Clone ulang dari {url}..."):
            ok2, out, err = run_git(["clone", url, repo])
        if not ok2:
            console.print(f"[red]Clone ulang gagal: {_human_git_error(err)}[/red]")
            log_error("Clone ulang gagal", raw_detail=err)
            return
        console.print(f"[green]✓ Clone ulang berhasil ke {repo}[/green]")
        log_activity(f"Repository di-clone ulang: {repo}")
        _set_active_repository(repo)
    except OSError as e:
        console.print(f"[red]Gagal menghapus/clone ulang: {e}[/red]")
        log_error("Gagal clone ulang", e)


def _get_active_repo_local() -> str | None:
    config = load_config()
    repo = config.get("active_repository", "")
    if not repo:
        console.print("[yellow]Repository tidak ditemukan. Silakan pilih repository terlebih dahulu.[/yellow]")
        return None
    return repo


def lihat_repository_aktif() -> None:
    """Tampilkan repository yang sedang aktif."""
    config = load_config()
    repo = config.get("active_repository", "")
    if not repo or not is_git_repo(repo):
        console.print("[yellow]Belum ada repository aktif. "
                       "Silakan pilih repository terlebih dahulu.[/yellow]")
        return
    console.print(f"[cyan]Repository aktif:[/cyan] {repo}")


def _human_git_error(stderr: str) -> str:
    """Ubah pesan error git mentah menjadi pesan ramah pengguna."""
    stderr_lower = stderr.lower()
    if "not found" in stderr_lower or "does not exist" in stderr_lower:
        return "Repository tidak ditemukan. Silakan pilih repository terlebih dahulu."
    if "already exists" in stderr_lower:
        return "Folder tujuan sudah ada dan tidak kosong."
    if "could not resolve host" in stderr_lower or "network" in stderr_lower:
        return "Tidak dapat terhubung ke internet. Periksa koneksi kamu."
    if "authentication" in stderr_lower or "permission denied" in stderr_lower:
        return "Autentikasi gagal. Periksa username/token/SSH key kamu."
    return stderr or "Terjadi kesalahan yang tidak diketahui."


def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Repository[/bold cyan]\n"
        "- Pilih Repository: memilih repository dari hasil pencarian otomatis.\n"
        "- Cari Repository Otomatis: mencari folder Git mulai dari path tertentu.\n"
        "- Clone Repository: mengunduh repository baru dari URL remote.\n"
        "- Compare Repository: membandingkan repository lokal dengan GitHub\n"
        "  (Sinkron / Lokal Lebih Baru / GitHub Lebih Baru / Diverged),\n"
        "  lalu tawarkan aksi yang relevan (Push, Pull, atau Fetch+Review).\n"
        "- Tambah Repository: menambahkan repository dengan path manual.\n"
        "- Ganti Repository: mengganti repository aktif.\n"
        "- Lihat Repository Aktif: menampilkan repository yang sedang dipakai.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def repository_manager() -> None:
    """Menu baru: Repository Manager sesuai spec update."""
    while True:
        console.rule("[bold cyan]Repository Manager")
        repos = get_repositories()  # from settings
        if not repos:
            console.print("[yellow]Belum ada repository tersimpan. Gunakan scan atau clone.[/yellow]")
            choice = questionary.select(
                "Pilih aksi:", choices=["Scan Repositories", "Clone Repository", "Kembali"]
            ).ask()
            if choice == "Scan Repositories":
                scan_repositories()
            elif choice == "Clone Repository":
                clone_repository()
            elif choice == "Kembali":
                return
            continue

        # Favorit selalu tampil paling atas, sisanya ikut urutan last_open (get_repositories sudah sort).
        repos = sorted(repos, key=lambda r: (not r.get("favorite", False),))

        active_repo = load_config().get("active_repository")

        # Prepare choices with status
        choices = []
        for r in repos:
            path = r["path"]
            name = os.path.basename(path)
            branch = "?"
            status = "?"
            if is_git_repo(path):
                ok, branch_out, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
                branch = branch_out.strip() if ok and branch_out.strip() else "?"
                ok2, status_out, _ = run_git(["status", "--porcelain"], cwd=path)
                status = "Clean" if ok2 and not status_out.strip() else ("Modified" if ok2 else "?")
            else:
                status = "Hilang"  # folder/repo tidak ditemukan lagi di disk
            last_open = r.get("last_open", "-")
            mark = "⭐ " if r.get("favorite", False) else ""
            active_mark = " ✓" if path == active_repo else ""
            choices.append(f"{mark}{name} ({branch}, {status}) - {last_open}{active_mark} | {path}")
        choices += ["Scan Repositories", "Clone Repository", "Compare Repository", "Refresh", "? Search", "Favorite", "Kembali"]

        pilihan = questionary.select("Pilih repository atau aksi:", choices=choices).ask()
        if not pilihan or pilihan == "Kembali":
            return
        if pilihan == "Scan Repositories":
            scan_repositories()
            continue
        if pilihan == "Clone Repository":
            clone_repository()
            continue
        if pilihan == "Compare Repository":
            compare_repository()
            continue
        if pilihan == "Refresh":
            continue
        if pilihan == "? Search":
            search_repository()
            continue
        if pilihan == "Favorite":
            toggle_favorite_menu()
            continue

        # Select repo
        selected_path = None
        for r in repos:
            if pilihan.endswith(f"| {r['path']}"):
                selected_path = r['path']
                break
        if selected_path:
            repo_action_menu(selected_path)


def repo_action_menu(path: str) -> None:
    """Sub-menu aksi untuk satu repository terpilih: Gunakan / Hapus dari daftar / Buka lokasi / Batal."""
    name = os.path.basename(path)
    aksi = questionary.select(
        f"Aksi untuk '{name}':",
        choices=["Gunakan Repository", "Buka Lokasi", "Hapus dari Daftar", "Batal"],
    ).ask()
    if aksi is None or aksi == "Batal":
        return
    if aksi == "Gunakan Repository":
        use_repo(path)
    elif aksi == "Buka Lokasi":
        open_location(path)
    elif aksi == "Hapus dari Daftar":
        konfirmasi = questionary.confirm(
            f"Hapus '{name}' dari daftar? (Folder di disk TIDAK akan dihapus)", default=False
        ).ask()
        if konfirmasi:
            remove_from_repositories(path)
            console.print(f"[green]'{name}' dihapus dari daftar Repository Manager.[/green]")
            log_activity(f"Repository dihapus dari daftar: {path}")


def scan_repositories() -> None:
    """Scan HOME for .git folders and add to list."""
    home = os.path.expanduser("~")
    console.print("[cyan]Scanning for Git repositories in HOME...[/cyan]")
    found = find_git_repos(home)
    config = load_config()
    repos = config.setdefault("repositories", [])
    added = 0
    for path in found:
        if not any(r.get("path") == path for r in repos):
            repos.append({
                "path": path,
                "last_open": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "favorite": False
            })
            added += 1
    config["repositories"] = repos
    save_config(config)
    console.print(f"[green]Scan selesai. {added} repository baru ditambahkan.[/green]")


def search_repository() -> None:
    """Search repository pakai autocomplete (ketik sebagian nama, langsung muncul saran)."""
    repos = get_repositories()
    if not repos:
        console.print("[yellow]Belum ada repository tersimpan.[/yellow]")
        return

    # Hitung nama folder yang duplikat supaya key autocomplete tetap unik.
    names = [os.path.basename(r["path"]) for r in repos]
    dupes = {n for n in names if names.count(n) > 1}

    label_to_path = {}
    for r in repos:
        path = r["path"]
        name = os.path.basename(path)
        label = f"{name} ({os.path.dirname(path)})" if name in dupes else name
        label_to_path[label] = path

    pilihan = questionary.autocomplete(
        "Cari repository (ketik nama, Tab/Enter untuk pilih):",
        choices=list(label_to_path.keys()),
    ).ask()
    if not pilihan or pilihan not in label_to_path:
        return
    repo_action_menu(label_to_path[pilihan])


def toggle_favorite_menu() -> None:
    """Toggle favorite for repos."""
    repos = get_repositories()
    names = [os.path.basename(r["path"]) for r in repos]
    dupes = {n for n in names if names.count(n) > 1}
    label_to_path = {}
    for r in repos:
        name = os.path.basename(r["path"])
        label = f"{name} ({r['path']})" if name in dupes else name
        label_to_path[label] = r["path"]

    pilihan = questionary.select("Pilih repo untuk toggle favorite:", choices=list(label_to_path.keys()) + ["Batal"]).ask()
    if pilihan and pilihan != "Batal":
        toggle_favorite(label_to_path[pilihan])
        console.print(f"[green]Favorite toggled for {pilihan}[/green]")


def use_repo(path: str) -> None:
    """Gunakan repository (set active)."""
    if is_git_repo(path):
        _set_active_repository(path)
        console.print(f"[green]Repository aktif: {path}[/green]")
        log_activity(f"Repository digunakan: {path}")
    else:
        console.print("[red]Bukan repository Git valid.[/red]")


def open_location(path: str) -> None:
    """Buka lokasi di file manager (Termux), fallback tampilkan path kalau termux-open tidak ada."""
    import shutil
    if shutil.which("termux-open"):
        exit_code = os.system(f"termux-open '{path}'")
        if exit_code != 0:
            console.print(f"[yellow]Gagal membuka file manager. Lokasi: {path}[/yellow]")
    else:
        console.print(f"[cyan]termux-open tidak tersedia. Lokasi repository: {path}[/cyan]")


def menu() -> None:
    while True:
        console.rule("[bold cyan]Repository")
        choice = questionary.select(
            "Pilih aksi:",
            choices=[
                "Pilih Repository",
                "Cari Repository Git Otomatis",
                "Clone Repository",
                "Compare Repository",
                "Tambah Repository",
                "Ganti Repository",
                "Lihat Repository Aktif",
                "? Help",
                "Kembali",
            ],
        ).ask()

        if choice is None or choice == "Kembali":
            return
        try:
            if choice == "Pilih Repository":
                pilih_repository()
            elif choice == "Cari Repository Git Otomatis":
                cari_repository_otomatis()
            elif choice == "Clone Repository":
                clone_repository()
            elif choice == "Compare Repository":
                compare_repository()
            elif choice == "Tambah Repository":
                tambah_repository()
            elif choice == "Ganti Repository":
                ganti_repository()
            elif choice == "Lihat Repository Aktif":
                lihat_repository_aktif()
            elif choice == "? Help":
                show_help()
        except GitError as e:
            console.print(f"[red]{e.human_message}[/red]")
            log_error("GitError di menu Repository", raw_detail=e.raw_error)
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Repository", e)
