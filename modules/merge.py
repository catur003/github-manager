"""
merge.py
Menu Merge: Merge Lokal (pilih source & target branch, konfirmasi,
tampilkan conflict, jika berhasil tawarkan hapus branch source).
"""

import json
import subprocess

import questionary
from rich.console import Console

from modules.utils import run_git, spinner
from modules.settings import load_config, _gh_available, _get_gh_login_status
from modules.logger import log_activity, log_error
from modules import preflight

console = Console()


def _gh_ready() -> bool:
    """Cek gh CLI terpasang & sudah login. Kalau belum, kasih pesan jelas
    (bukan wajib install - sesuai spec, fitur PR cuma nyala kalau siap)."""
    if not _gh_available():
        console.print(
            "[yellow]GitHub CLI (gh) tidak terpasang.[/yellow]\n"
            "Fitur Pull Request butuh 'gh'. Install dulu, lalu login lewat "
            "menu Pengaturan > GitHub Account."
        )
        return False
    logged_in, _ = _get_gh_login_status()
    if not logged_in:
        console.print(
            "[yellow]Belum login ke GitHub CLI.[/yellow]\n"
            "Login dulu lewat menu Pengaturan > GitHub Account."
        )
        return False
    return True


def _detect_base_branch(repo: str, branches: list[str]) -> str:
    """Deteksi default base branch (main/master), fallback ke branch pertama."""
    ok, out, _err = run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=repo)
    if ok and out:
        candidate = out.rsplit("/", 1)[-1].strip()
        if candidate in branches:
            return candidate
    for candidate in ("main", "master"):
        if candidate in branches:
            return candidate
    return branches[0]


def _get_active_repo() -> str | None:
    config = load_config()
    repo = config.get("active_repository", "")
    if not repo:
        console.print("[yellow]Repository tidak ditemukan. Silakan pilih repository terlebih dahulu.[/yellow]")
        return None
    return repo


def _list_branches(repo: str) -> list[str]:
    ok, out, _err = run_git(["branch", "--list"], cwd=repo)
    if not ok or not out:
        return []
    return [line.replace("*", "").strip() for line in out.splitlines() if line.strip()]


def _list_remote_branches(repo: str, remote: str = "origin") -> list[str]:
    """Daftar branch yang ada di remote (mis. GitHub), tanpa prefix 'origin/'."""
    ok, out, _err = run_git(["branch", "-r"], cwd=repo)
    if not ok or not out:
        return []
    branches = []
    prefix = f"{remote}/"
    for line in out.splitlines():
        name = line.strip()
        if not name or "->" in name:
            continue
        if name.startswith(prefix):
            name = name[len(prefix):]
        branches.append(name)
    return branches


def _list_branches_for_pr(repo: str) -> tuple[list[str], set[str]]:
    """FIX BUG: sebelumnya cuma pakai branch lokal, jadi PR gagal dibuat kalau
    branch lokal sudah dihapus padahal branch itu masih ada di GitHub.
    Sekarang gabungkan branch lokal + remote (dedup), dan kembalikan juga
    set nama branch yang cuma ada di remote (untuk penanda di pilihan)."""
    local = _list_branches(repo)
    remote = _list_remote_branches(repo)
    remote_only = set(remote) - set(local)
    combined = local + [b for b in remote if b not in local]
    return combined, remote_only


def merge_lokal() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    # Merge lokal gak butuh remote/internet, tapi tetap cek repo valid +
    # working tree (warning kalau ada perubahan belum di-commit).
    if not preflight.preflight(repo, need_remote=False, label="Merge"):
        return
    branches = _list_branches(repo)
    if len(branches) < 2:
        console.print("[yellow]Minimal harus ada 2 branch untuk melakukan merge.[/yellow]")
        return

    source = questionary.select("Pilih Source Branch (yang akan digabung):", choices=branches + ["Batal"]).ask()
    if not source or source == "Batal":
        return
    target_choices = [b for b in branches if b != source] + ["Batal"]
    target = questionary.select("Pilih Target Branch (tujuan penggabungan):", choices=target_choices).ask()
    if not target or target == "Batal":
        return

    console.print(f"[cyan]Akan menggabungkan '{source}' ke dalam '{target}'.[/cyan]")
    yakin = questionary.confirm("Lanjutkan merge?", default=True).ask()
    if not yakin:
        console.print("[yellow]Dibatalkan.[/yellow]")
        return

    ok, _out, err = run_git(["checkout", target], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal pindah ke branch target: {err}[/red]")
        return

    with spinner(f"Menggabungkan '{source}' ke dalam '{target}'..."):
        ok, out, err = run_git(["merge", source], cwd=repo)
    if not ok:
        if "conflict" in (out + err).lower():
            console.print("[red]Terjadi CONFLICT saat merge. Merge dihentikan.[/red]")
            ok2, status_out, _err2 = run_git(["status"], cwd=repo)
            if ok2:
                console.print(status_out)
            console.print("[yellow]Selesaikan conflict secara manual, lalu lakukan Git Add dan Commit.[/yellow]")
            log_activity(f"Merge {source} ke {target} gagal - conflict")
            log_error("Merge conflict", raw_detail=err)
            return
        console.print(f"[red]Merge gagal: {err}[/red]")
        log_error("Merge gagal", raw_detail=err)
        return

    console.print(f"[green]Merge berhasil.[/green]\n{out}")
    log_activity(f"Merge {source} ke {target} berhasil")
    run_git(["status", "--short"], cwd=repo)
    run_git(["branch", "-vv"], cwd=repo)
    run_git(["remote", "-v"], cwd=repo)

    hapus = questionary.confirm(f"Merge berhasil. Hapus branch '{source}' sekarang?", default=False).ask()
    if hapus:
        ok, _out, err = run_git(["branch", "-d", source], cwd=repo)
        if not ok:
            console.print(f"[red]Gagal menghapus branch: {err}[/red]")
            return
        console.print(f"[green]Branch '{source}' berhasil dihapus.[/green]")
        log_activity(f"Branch {source} dihapus setelah merge")


def buat_pull_request() -> None:
    """Compare & Pull Request -> Create Pull Request (title bisa diedit),
    setara fitur 'Compare & pull request' di web GitHub."""
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=True, label="Buat Pull Request"):
        return
    if not _gh_ready():
        return

    # Tawarkan Fetch dulu supaya daftar branch (termasuk yang baru dibuat/
    # dihapus orang lain di GitHub) sinkron sebelum dipilih.
    sinkron = questionary.confirm(
        "Fetch Branch dari GitHub dulu? (disarankan supaya daftar branch sinkron)",
        default=True,
    ).ask()
    if sinkron:
        with spinner("Fetch branch dari GitHub..."):
            run_git(["fetch", "--prune", "origin"], cwd=repo, timeout=60)

    branches, remote_only = _list_branches_for_pr(repo)
    if len(branches) < 2:
        console.print("[yellow]Minimal harus ada 2 branch untuk membuat Pull Request.[/yellow]")
        return

    current = preflight.get_current_branch(repo) or branches[0]

    def _label(b: str) -> str:
        if b == current:
            return f"{b} (branch aktif)"
        if b in remote_only:
            return f"{b} (hanya di GitHub)"
        return b

    source_choices = [_label(b) for b in branches] + ["Batal"]
    default_idx = branches.index(current) if current in branches else 0
    source_pick = questionary.select("Pilih Source Branch (Compare):", choices=source_choices, default=source_choices[default_idx]).ask()
    if not source_pick or source_pick == "Batal":
        return
    source = source_pick.replace(" (branch aktif)", "").replace(" (hanya di GitHub)", "")

    target_choices = [_label(b) for b in branches if b != source] + ["Batal"]
    default_target = _detect_base_branch(repo, [b for b in branches if b != source])
    target_pick = questionary.select("Pilih Target/Base Branch:", choices=target_choices, default=_label(default_target)).ask()
    if not target_pick or target_pick == "Batal":
        return
    target = target_pick.replace(" (branch aktif)", "").replace(" (hanya di GitHub)", "")

    # Pastikan source branch sudah ada di remote, gh pr create butuh itu.
    if source == current:
        if not preflight.ensure_upstream(repo, source, auto_yes=False):
            console.print("[yellow]Pull Request butuh branch source sudah ada di remote.[/yellow]")
            return
    elif not preflight.remote_branch_exists(repo, source):
        console.print(f"[red]Branch '{source}' belum ada di remote. Push branch itu dulu (checkout ke sana, lalu Push).[/red]")
        return

    ok, last_msg, _err = run_git(["log", "-1", "--pretty=%s"], cwd=repo)
    default_title = last_msg.strip() if ok and last_msg.strip() else f"{source} -> {target}"
    title = questionary.text("Judul Pull Request (bisa diedit):", default=default_title).ask()
    if not title:
        console.print("[yellow]Dibatalkan, judul tidak boleh kosong.[/yellow]")
        return
    body = questionary.text("Deskripsi (opsional, boleh dikosongkan):", default="").ask() or ""

    console.print(f"[cyan]Akan membuat PR: '{source}' -> '{target}' dengan judul '{title}'[/cyan]")
    yakin = questionary.confirm("Lanjutkan buat Pull Request?", default=True).ask()
    if not yakin:
        console.print("[yellow]Dibatalkan.[/yellow]")
        return

    args = ["pr", "create", "--base", target, "--head", source, "--title", title]
    args += ["--body", body] if body else ["--body", ""]
    with spinner("Membuat Pull Request di GitHub..."):
        result = subprocess.run(["gh"] + args, cwd=repo, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        console.print(f"[red]Gagal membuat Pull Request: {(result.stderr or result.stdout).strip()}[/red]")
        log_error("Gagal membuat Pull Request", raw_detail=result.stderr)
        return

    pr_url = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
    console.print(f"[green]✓ Pull Request berhasil dibuat.[/green]\n{pr_url}")
    log_activity(f"Pull Request dibuat: {source} -> {target} ({title})")


def _list_open_pr(repo: str) -> list[dict]:
    result = subprocess.run(
        ["gh", "pr", "list", "--state", "open", "--json", "number,title,headRefName,baseRefName,url"],
        cwd=repo, capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []


def merge_pull_request() -> None:
    """List PR yang open lalu merge - setara tombol 'Merge pull request' di web GitHub."""
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=True, label="Merge Pull Request"):
        return
    if not _gh_ready():
        return

    with spinner("Mengambil daftar Pull Request..."):
        prs = _list_open_pr(repo)
    if not prs:
        console.print("[yellow]Tidak ada Pull Request yang open untuk repository ini.[/yellow]")
        return

    labels = [f"#{pr['number']} {pr['title']} ({pr['headRefName']} -> {pr['baseRefName']})" for pr in prs]
    pick = questionary.select("Pilih Pull Request yang akan di-merge:", choices=labels + ["Batal"]).ask()
    if not pick or pick == "Batal":
        return
    pr = prs[labels.index(pick)]

    metode = questionary.select(
        "Metode merge:",
        choices=["Merge commit", "Squash", "Rebase", "Batal"],
    ).ask()
    if not metode or metode == "Batal":
        return
    flag = {"Merge commit": "--merge", "Squash": "--squash", "Rebase": "--rebase"}[metode]

    hapus_branch = questionary.confirm(f"Hapus branch '{pr['headRefName']}' setelah merge?", default=True).ask()

    console.print(f"[cyan]Akan merge PR #{pr['number']} ({pr['headRefName']} -> {pr['baseRefName']}) via {metode}.[/cyan]")
    yakin = questionary.confirm("Lanjutkan merge Pull Request?", default=True).ask()
    if not yakin:
        console.print("[yellow]Dibatalkan.[/yellow]")
        return

    args = ["pr", "merge", str(pr["number"]), flag]
    if hapus_branch:
        args.append("--delete-branch")

    with spinner(f"Merge PR #{pr['number']}..."):
        result = subprocess.run(["gh"] + args, cwd=repo, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        console.print(f"[red]Gagal merge Pull Request: {(result.stderr or result.stdout).strip()}[/red]")
        log_error("Gagal merge Pull Request", raw_detail=result.stderr)
        return

    console.print(f"[green]✓ Pull Request #{pr['number']} berhasil di-merge.[/green]")
    log_activity(f"Pull Request #{pr['number']} di-merge ({metode})")


def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Merge[/bold cyan]\n"
        "Merge Lokal menggabungkan isi Source Branch ke dalam Target Branch\n"
        "secara lokal. Jika terjadi conflict, proses akan dihentikan agar kamu\n"
        "bisa menyelesaikannya secara manual.\n\n"
        "Buat Pull Request: setara 'Compare & pull request' di GitHub - membuat\n"
        "PR dari source branch ke base branch, judul bisa diedit.\n\n"
        "Merge Pull Request: menampilkan daftar PR yang open lalu merge langsung\n"
        "dari sini (Merge commit / Squash / Rebase), opsional hapus branch.\n"
        "Kedua fitur PR butuh GitHub CLI (gh) terpasang & sudah login.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    while True:
        console.rule("[bold cyan]Merge")
        choice = questionary.select(
            "Pilih aksi:",
            choices=["Merge Lokal", "Buat Pull Request (GitHub)", "Merge Pull Request (GitHub)", "? Help", "Kembali"],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            if choice == "Merge Lokal":
                merge_lokal()
            elif choice == "Buat Pull Request (GitHub)":
                buat_pull_request()
            elif choice == "Merge Pull Request (GitHub)":
                merge_pull_request()
            elif choice == "? Help":
                show_help()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Merge", e)
