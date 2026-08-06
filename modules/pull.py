"""
pull.py
Menu Pull: Pull, Fetch, Refresh.
"""

import questionary
from rich.console import Console

from modules.utils import run_git, spinner
from modules.settings import load_config, record_repo_event
from modules.logger import log_activity, log_error
from modules import preflight

console = Console()


def _get_active_repo() -> str | None:
    config = load_config()
    repo = config.get("active_repository", "")
    if not repo:
        console.print("[yellow]Repository tidak ditemukan. Silakan pilih repository terlebih dahulu.[/yellow]")
        return None
    return repo


def pull() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    # PRIORITAS 1 #2/#1: pre-flight check + auto upstream sebelum pull,
    # supaya user gak pernah lihat "no tracking information" mentah.
    # need_clean=False sengaja - working tree kotor BUKAN alasan blocking,
    # tapi kalau nanti pull gagal karena itu, kita tawarkan jalan keluar
    # (bukan cuma dead-end error) lewat _handle_pull_failure di bawah.
    if not preflight.preflight(repo, need_remote=True, need_upstream=True, label="Pull"):
        return
    with spinner("Mengambil (pull) perubahan terbaru dari remote..."):
        ok, out, err = run_git(["pull"], cwd=repo, timeout=120)
    if not ok:
        _handle_pull_failure(repo, err)
        return
    n_commit = out.count("\n") if out else 0
    console.print(f"[green]✓ Pull Berhasil[/green]\n\n{out or 'Sudah paling baru (tidak ada perubahan).'}")
    log_activity("Pull berhasil")
    record_repo_event(repo, "last_pull")
    # PRIORITAS 1 #3: refresh info repo abis pull (branch/remote sinkron lagi)
    run_git(["status", "--short"], cwd=repo)
    run_git(["branch", "-vv"], cwd=repo)
    run_git(["remote", "-v"], cwd=repo)


def _handle_pull_failure(repo: str, err: str) -> None:
    """
    BUGFIX: dulu kalau Pull gagal (working tree kotor / conflict), user cuma
    dikasih pesan lalu mentok - gak ada jalan lanjut dari dalam menu, harus
    keluar aplikasi dan benerin manual. Sekarang: deteksi jenis kegagalan
    dan tawarkan aksi konkret langsung dari sini.
    """
    low = err.lower()
    console.print(f"[red]Pull gagal: {_friendly(err)}[/red]")
    log_error("Pull gagal", raw_detail=err)

    if "would be overwritten" in low or "local changes" in low:
        console.print(
            "[yellow]Ada perubahan lokal yang belum di-commit dan bentrok "
            "dengan perubahan dari remote.[/yellow]"
        )
        aksi = questionary.select(
            "Pilih aksi:",
            choices=[
                "Stash perubahan lokal lalu Pull (bisa dikembalikan nanti)",
                "Batalkan Pull (commit dulu manual lewat menu Git Add/Commit)",
                "Kembali",
            ],
        ).ask()
        if aksi and aksi.startswith("Stash"):
            ok_s, out_s, err_s = run_git(["stash", "push", "-u", "-m", "auto-stash-before-pull"], cwd=repo)
            if not ok_s:
                console.print(f"[red]Gagal stash: {err_s}[/red]")
                log_error("Gagal stash sebelum pull", raw_detail=err_s)
                return
            console.print("[green]✓ Perubahan lokal di-stash.[/green]")
            with spinner("Mengambil (pull) perubahan terbaru dari remote..."):
                ok2, out2, err2 = run_git(["pull"], cwd=repo, timeout=120)
            if not ok2:
                console.print(f"[red]Pull masih gagal: {_friendly(err2)}[/red]")
                console.print("[yellow]Perubahan kamu masih aman di stash. Jalankan 'git stash pop' manual setelah masalah selesai.[/yellow]")
                log_error("Pull gagal setelah stash", raw_detail=err2)
                return
            console.print(f"[green]✓ Pull Berhasil[/green]\n\n{out2 or '-'}")
            log_activity("Pull berhasil (setelah auto-stash)")
            record_repo_event(repo, "last_pull")
            ok_p, out_p, err_p = run_git(["stash", "pop"], cwd=repo)
            if ok_p:
                console.print("[green]✓ Perubahan lokal dikembalikan (stash pop).[/green]")
            else:
                console.print(
                    "[yellow]⚠ Gagal auto stash-pop (kemungkinan conflict). "
                    "Perubahan kamu tetap aman di stash - selesaikan manual "
                    "dengan 'git stash pop' lalu beresin conflict-nya.[/yellow]"
                )
                log_error("Gagal stash pop setelah pull", raw_detail=err_p)
        return

    if "conflict" in low:
        console.print(
            "[yellow]Terjadi conflict saat pull. File yang bentrok:[/yellow]"
        )
        ok_s, status_out, _e = run_git(["status", "--short"], cwd=repo)
        if ok_s and status_out:
            console.print(status_out)
        aksi = questionary.select(
            "Pilih aksi:",
            choices=[
                "Batalkan Pull ini (git merge --abort, kembali ke kondisi sebelum pull)",
                "Selesaikan manual (biarkan, saya edit file lalu Add & Commit sendiri)",
                "Kembali",
            ],
        ).ask()
        if aksi and aksi.startswith("Batalkan"):
            ok_a, _out_a, err_a = run_git(["merge", "--abort"], cwd=repo)
            if ok_a:
                console.print("[green]✓ Pull dibatalkan, repository kembali ke kondisi sebelum pull.[/green]")
                log_activity("Pull dibatalkan (merge --abort)")
            else:
                console.print(f"[red]Gagal membatalkan: {err_a}[/red]")
                log_error("Gagal merge --abort setelah pull conflict", raw_detail=err_a)


def fetch() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=True, need_upstream=False, label="Fetch"):
        return
    with spinner("Mengecek (fetch) info terbaru dari remote..."):
        ok, out, err = run_git(["fetch"], cwd=repo, timeout=120)
    if not ok:
        console.print(f"[red]Fetch gagal: {_friendly(err)}[/red]")
        log_error("Fetch gagal", raw_detail=err)
        return
    console.print("[green]✓ Fetch Berhasil.[/green] Info remote sudah diperbarui.")
    log_activity("Fetch berhasil")
    run_git(["status", "--short"], cwd=repo)
    run_git(["branch", "-vv"], cwd=repo)
    run_git(["remote", "-v"], cwd=repo)


def refresh() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    ok, out, err = run_git(["status", "-sb"], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal mengambil status: {err}[/red]")
        return
    console.print(out)


def _friendly(err: str) -> str:
    low = err.lower()
    if "could not resolve host" in low or "network" in low:
        return "Tidak dapat terhubung ke internet. Periksa koneksi kamu."
    if "would be overwritten" in low or "local changes" in low:
        return "Ada perubahan lokal belum di-commit yang bentrok dengan perubahan dari remote."
    if "conflict" in low:
        return "Terjadi conflict saat pull. Selesaikan conflict terlebih dahulu."
    if "authentication" in low or "permission denied" in low:
        return "Autentikasi gagal. Periksa username/token/SSH key kamu."
    if "no tracking information" in low or "no upstream" in low:
        return "Branch belum memiliki upstream. Coba lagi - seharusnya sudah otomatis dihubungkan."
    return err or "Terjadi kesalahan yang tidak diketahui."


def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Pull[/bold cyan]\n"
        "- Pull: mengambil sekaligus menggabungkan perubahan terbaru dari remote.\n"
        "- Fetch: hanya mengecek perubahan di remote tanpa menggabungkannya.\n"
        "- Refresh: menampilkan status terbaru branch dibanding remote.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    while True:
        console.rule("[bold cyan]Pull")
        choice = questionary.select(
            "Pilih aksi:",
            choices=["Pull", "Fetch", "Refresh", "? Help", "Kembali"],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Pull": pull,
                "Fetch": fetch,
                "Refresh": refresh,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Pull", e)
