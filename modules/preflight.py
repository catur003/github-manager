"""
preflight.py
Pengecekan otomatis sebelum menjalankan operasi Git berisiko
(Upload, Commit, Push, Pull, Merge, Fetch):

- Repository terpilih & valid
- Koneksi internet ke remote
- Branch & remote terdeteksi
- Upstream terhubung (auto-detect + tawarkan perbaikan)
- Working tree (bersih/kotor, informasi saja - tidak selalu blocking)

Semua pesan ke user dalam bahasa manusia biasa, tidak ada error Git
mentah yang tampil langsung ke layar.
"""

from __future__ import annotations

import os
from typing import Optional

import questionary
from rich.console import Console

from modules.utils import run_git, is_git_repo
from modules.logger import log_activity, log_error

console = Console()


def get_current_branch(repo: str) -> Optional[str]:
    ok, out, _err = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    return out if ok and out else None


def get_upstream(repo: str, branch: str) -> Optional[str]:
    """Kembalikan nama upstream (mis. 'origin/main') atau None kalau belum ada."""
    ok, out, _err = run_git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", f"{branch}@{{u}}"], cwd=repo
    )
    return out if ok and out else None


def has_remote(repo: str, name: str = "origin") -> bool:
    ok, out, _err = run_git(["remote"], cwd=repo)
    return ok and name in out.splitlines()


def remote_branch_exists(repo: str, branch: str, remote: str = "origin") -> bool:
    ok, out, _err = run_git(["ls-remote", "--heads", remote, branch], cwd=repo, timeout=20)
    return ok and bool(out.strip())


def check_internet(repo: str, remote: str = "origin") -> bool:
    """Cek konektivitas ke remote (bukan internet secara umum) - lebih relevan
    karena yang dibutuhkan aplikasi adalah bisa/tidaknya bicara ke remote itu."""
    ok, _out, _err = run_git(["ls-remote", "--exit-code", remote], cwd=repo, timeout=15)
    return ok


def ensure_upstream(repo: str, branch: str, auto_yes: bool = False) -> bool:
    """
    PRIORITAS 1 #1 - Auto Upstream Detection.
    Cek apakah branch aktif sudah punya upstream. Kalau belum, tawarkan
    untuk menghubungkan otomatis (set-upstream kalau remote branch sudah
    ada, atau push -u kalau belum). User tidak pernah melihat pesan Git
    mentah semacam "no tracking information".
    Return True kalau upstream OK/berhasil dibuat, False kalau user
    menolak atau gagal.
    """
    upstream = get_upstream(repo, branch)
    if upstream:
        return True

    console.print("[yellow]⚠ Branch belum memiliki upstream.[/yellow]")
    if not auto_yes:
        lanjut = questionary.confirm("Hubungkan sekarang?", default=True).ask()
        if not lanjut:
            console.print("[yellow]Dibatalkan. Beberapa operasi (Pull/Fetch banding) butuh upstream.[/yellow]")
            return False

    if remote_branch_exists(repo, branch):
        ok, _out, err = run_git(
            ["branch", f"--set-upstream-to=origin/{branch}", branch], cwd=repo
        )
    else:
        console.print(f"[cyan]Mengirim branch '{branch}' ke remote (pertama kali)...[/cyan]")
        ok, _out, err = run_git(["push", "-u", "origin", branch], cwd=repo, timeout=120)

    if not ok:
        console.print(f"[red]Gagal menghubungkan upstream: {_friendly_upstream_error(err)}[/red]")
        log_error("Gagal set upstream", raw_detail=err)
        return False

    console.print(
        f"[green]✓ Upstream berhasil dibuat[/green]\n\n"
        f"Branch : {branch}\n"
        f"Remote : origin/{branch}\n"
    )
    log_activity(f"Upstream dibuat untuk branch {branch} -> origin/{branch}")
    return True


def _friendly_upstream_error(err: str) -> str:
    low = err.lower()
    if "could not resolve host" in low or "network" in low:
        return "Tidak dapat terhubung ke internet. Periksa koneksi kamu."
    if "authentication" in low or "permission denied" in low:
        return "Autentikasi gagal. Periksa username/token/SSH key kamu."
    return "Terjadi kesalahan saat menghubungkan upstream."


def is_rebase_in_progress(repo: str) -> bool:
    """Cek apakah repository sedang berada di tengah proses rebase yang
    belum selesai (folder .git/rebase-merge atau .git/rebase-apply ada).
    Dipakai bareng oleh Dashboard (peringatan) dan menu Rebase (supaya
    tidak bisa mulai rebase baru kalau rebase lama belum kelar) - satu
    sumber kebenaran, tidak diduplikasi di masing-masing tempat."""
    if not repo or not os.path.isdir(repo):
        return False
    git_dir = os.path.join(repo, ".git")
    # .git bisa berupa FILE (worktree/submodule) berisi 'gitdir: <path>',
    # bukan folder - baca isinya kalau begitu supaya deteksi tetap benar.
    if os.path.isfile(git_dir):
        try:
            with open(git_dir, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except OSError:
            return False
        if not content.startswith("gitdir:"):
            return False
        target = content.split(":", 1)[1].strip()
        git_dir = target if os.path.isabs(target) else os.path.join(repo, target)
    if not os.path.isdir(git_dir):
        return False
    return (
        os.path.isdir(os.path.join(git_dir, "rebase-merge"))
        or os.path.isdir(os.path.join(git_dir, "rebase-apply"))
    )


def preflight(
    repo: Optional[str],
    need_remote: bool = True,
    need_upstream: bool = False,
    need_clean: bool = False,
    label: str = "operasi ini",
) -> bool:
    """
    PRIORITAS 1 #2 - Pre Flight Check.
    Jalankan urutan pengecekan sebelum Upload/Commit/Push/Pull/Merge/Fetch.
    Mengembalikan True kalau semua syarat terpenuhi (atau berhasil
    diperbaiki lewat konfirmasi user), False kalau harus dibatalkan.
    Setiap langkah dicetak sebagai progress supaya user tahu aplikasi
    sedang bekerja, bukan diam.
    """
    console.print(f"[dim]Memeriksa kesiapan sebelum {label}...[/dim]")

    # 1. Repository
    console.print("[dim]  ✓ Repository...[/dim]", end="\r")
    if not repo or not is_git_repo(repo):
        console.print("[red]✗ Repository belum dipilih atau tidak valid.[/red]")
        console.print("[yellow]Silakan pilih repository terlebih dahulu lewat menu 'Repository'.[/yellow]")
        return False
    console.print("[green]  ✓ Repository[/green]")

    # 2. Branch
    branch = get_current_branch(repo)
    if not branch:
        console.print("[red]✗ Branch tidak terdeteksi (repository mungkin kosong/belum ada commit).[/red]")
        return False
    console.print(f"[green]  ✓ Branch[/green] ({branch})")

    # 3-5. Remote / Internet / Upstream - hanya relevan kalau operasi ini
    # memang butuh bicara ke remote (need_remote=True).
    #
    # BUGFIX KRITIS: sebelumnya ada `if not need_remote: return True` di
    # sini, yang bikin operasi dengan need_remote=False (Merge lokal,
    # semua Upload) langsung keluar dari preflight() SEBELUM sempat sampai
    # ke langkah 6 (Permission) dan 7 (Working Tree) di bawah. Akibatnya
    # checkout branch untuk merge, atau overwrite file lewat Upload, bisa
    # terjadi dengan perubahan belum ter-commit TANPA peringatan apa pun -
    # padahal justru di titik itu warning paling dibutuhkan. Sekarang,
    # apapun nilai need_remote, alur selalu diteruskan ke langkah 6 & 7.
    if need_remote:
        # 3. Remote
        if not has_remote(repo):
            console.print("[red]✗ Remote 'origin' belum diatur.[/red]")
            console.print("[yellow]Hubungkan repository ini ke GitHub dulu (Clone ulang atau atur remote manual).[/yellow]")
            return False
        console.print("[green]  ✓ Remote[/green] (origin)")

        # 4. Internet (ke remote)
        if not check_internet(repo):
            console.print("[red]✗ Internet tidak tersedia / tidak bisa menghubungi remote.[/red]")
            return False
        console.print("[green]  ✓ Internet[/green]")

        # 5. Upstream
        if need_upstream:
            if not ensure_upstream(repo, branch):
                return False
            console.print("[green]  ✓ Upstream[/green]")

    # 6. Permission (folder repo bisa ditulis)
    if not os.access(repo, os.W_OK):
        console.print("[red]✗ Tidak ada izin menulis ke folder repository ini.[/red]")
        return False
    console.print("[green]  ✓ Permission[/green]")

    # 7. Working Tree
    ok, status_out, _err = run_git(["status", "--porcelain"], cwd=repo)
    dirty = ok and bool(status_out.strip())
    if need_clean and dirty:
        console.print("[yellow]⚠ Working tree tidak bersih (ada perubahan belum di-commit).[/yellow]")
        lanjut = questionary.confirm("Tetap lanjutkan?", default=False).ask()
        if not lanjut:
            return False
    console.print(f"[green]  ✓ Working Tree[/green] ({'ada perubahan' if dirty else 'bersih'})")

    return True
