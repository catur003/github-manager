"""
rebase.py
Menu Rebase: menerapkan ulang (replay) commit branch aktif di atas branch
lain, supaya riwayat commit jadi lurus tanpa merge commit tambahan.
Termasuk penanganan saat rebase berhenti karena conflict (Lanjutkan,
Lewati, Batalkan) dan Update Branch dari Upstream lewat rebase (alternatif
Pull yang menghasilkan riwayat lebih rapi).
"""

import questionary
from rich.console import Console

from modules.utils import run_git, spinner
from modules.settings import load_config
from modules.logger import log_activity, log_error
from modules import preflight

console = Console()


def _get_active_repo() -> str | None:
    """Ambil path repository aktif dari config, atau None + pesan kalau belum dipilih."""
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


def _guard_no_active_rebase(repo: str) -> bool:
    """Cegah mulai rebase/update baru kalau ada rebase lain yang belum
    selesai - kembalikan True kalau AMAN untuk lanjut."""
    if preflight.is_rebase_in_progress(repo):
        console.print(
            "[yellow]Ada rebase yang belum selesai. Selesaikan dulu lewat "
            "'Lanjutkan Rebase', 'Lewati Commit', atau 'Batalkan Rebase'.[/yellow]"
        )
        return False
    return True


def _handle_rebase_result(repo: str, ok: bool, out: str, err: str, label: str) -> None:
    """Interpretasi hasil git rebase/--continue/--skip secara konsisten.
    Kalau masih berhenti karena conflict, tawarkan aksi lanjutan langsung
    dari sini (dipakai bareng oleh semua fungsi yang menjalankan rebase)."""
    if ok:
        console.print(f"[green]✓ {label} berhasil.[/green]\n{out or ''}")
        log_activity(f"{label} berhasil")
        return

    combined = f"{out}\n{err}".lower()
    if "conflict" in combined or preflight.is_rebase_in_progress(repo):
        console.print(f"[red]Terjadi CONFLICT saat {label.lower()}.[/red]")
        ok_s, status_out, _e = run_git(["status", "--short"], cwd=repo)
        if ok_s and status_out:
            console.print(status_out)
        log_activity(f"{label} berhenti - conflict")
        log_error(f"{label} conflict", raw_detail=err)

        aksi = questionary.select(
            "Rebase berhenti karena conflict. Pilih aksi:",
            choices=[
                "Selesaikan manual dulu (edit file, Git Add, lalu Lanjutkan dari menu Rebase)",
                "Lewati commit ini (skip)",
                "Batalkan rebase (abort, kembali ke kondisi sebelum rebase)",
                "Kembali",
            ],
        ).ask()
        if aksi and aksi.startswith("Lewati"):
            lewati_rebase()
        elif aksi and aksi.startswith("Batalkan"):
            batalkan_rebase()
        elif aksi and aksi.startswith("Selesaikan"):
            console.print(
                "[yellow]Selesaikan conflict pada file di atas, Git Add filenya, lalu pilih "
                "'Lanjutkan Rebase' dari menu Rebase.[/yellow]"
            )
        return

    console.print(f"[red]{label} gagal: {_friendly(err)}[/red]")
    log_error(f"{label} gagal", raw_detail=err)


def rebase_branch() -> None:
    """Rebase branch aktif di atas branch lain yang dipilih user."""
    repo = _get_active_repo()
    if not repo:
        return
    if not _guard_no_active_rebase(repo):
        return
    if not preflight.preflight(repo, need_remote=False, need_clean=True, label="Rebase"):
        return

    current = preflight.get_current_branch(repo)
    target_choices = [b for b in _list_branches(repo) if b != current]
    if not target_choices:
        console.print("[yellow]Tidak ada branch lain untuk dijadikan target rebase.[/yellow]")
        return
    target = questionary.select(
        f"Rebase branch '{current}' di atas branch:", choices=target_choices + ["Batal"]
    ).ask()
    if not target or target == "Batal":
        return

    console.print(f"[cyan]Akan menerapkan ulang commit di '{current}' di atas '{target}'.[/cyan]")
    console.print(
        "[yellow]Catatan: Rebase mengubah riwayat commit branch ini. Jangan rebase branch "
        "yang sudah di-push dan dipakai orang lain, kecuali kamu siap Force Push setelahnya.[/yellow]"
    )
    yakin = questionary.confirm("Lanjutkan rebase?", default=True).ask()
    if not yakin:
        console.print("[yellow]Dibatalkan.[/yellow]")
        return

    with spinner(f"Rebase '{current}' di atas '{target}'..."):
        ok, out, err = run_git(["rebase", target], cwd=repo)
    _handle_rebase_result(repo, ok, out, err, "Rebase")


def update_dari_upstream() -> None:
    """Tarik perubahan terbaru dari remote lalu rebase branch aktif di
    atasnya - alternatif Pull yang menghasilkan riwayat lurus (tanpa
    merge commit tambahan tiap kali sinkron dengan remote)."""
    repo = _get_active_repo()
    if not repo:
        return
    if not _guard_no_active_rebase(repo):
        return
    if not preflight.preflight(
        repo, need_remote=True, need_upstream=True, need_clean=True, label="Update dari Upstream (Rebase)"
    ):
        return

    branch = preflight.get_current_branch(repo) or "HEAD"
    with spinner("Fetch dari remote..."):
        run_git(["fetch", "origin"], cwd=repo, timeout=60)
    with spinner(f"Rebase '{branch}' di atas upstream-nya..."):
        ok, out, err = run_git(["rebase"], cwd=repo, timeout=120)
    _handle_rebase_result(repo, ok, out, err, "Update dari Upstream (Rebase)")


def lanjutkan_rebase() -> None:
    """Lanjutkan rebase yang sempat berhenti, setelah conflict diselesaikan
    manual dan file yang bentrok sudah di-Git Add."""
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.is_rebase_in_progress(repo):
        console.print("[yellow]Tidak ada rebase yang sedang berjalan.[/yellow]")
        return
    ok, out, err = run_git(["rebase", "--continue"], cwd=repo)
    _handle_rebase_result(repo, ok, out, err, "Lanjutkan Rebase")


def lewati_rebase() -> None:
    """Lewati commit yang lagi bermasalah, lanjutkan ke commit berikutnya."""
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.is_rebase_in_progress(repo):
        console.print("[yellow]Tidak ada rebase yang sedang berjalan.[/yellow]")
        return
    ok, out, err = run_git(["rebase", "--skip"], cwd=repo)
    _handle_rebase_result(repo, ok, out, err, "Lewati Commit (Rebase)")


def batalkan_rebase() -> None:
    """Batalkan rebase, kembali ke kondisi persis sebelum rebase dimulai."""
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.is_rebase_in_progress(repo):
        console.print("[yellow]Tidak ada rebase yang sedang berjalan.[/yellow]")
        return
    yakin = questionary.confirm("Batalkan rebase dan kembali ke kondisi sebelum rebase?", default=True).ask()
    if not yakin:
        console.print("[yellow]Dibatalkan.[/yellow]")
        return
    ok, _out, err = run_git(["rebase", "--abort"], cwd=repo)
    if ok:
        console.print("[green]✓ Rebase dibatalkan, repository kembali ke kondisi sebelum rebase.[/green]")
        log_activity("Rebase dibatalkan (abort)")
    else:
        console.print(f"[red]Gagal membatalkan rebase: {_friendly(err)}[/red]")
        log_error("Gagal rebase --abort", raw_detail=err)


def status_rebase() -> None:
    """Cek apakah ada rebase yang belum selesai, tampilkan file yang bentrok."""
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.is_rebase_in_progress(repo):
        console.print("[green]Tidak ada rebase yang sedang berjalan.[/green]")
        return
    console.print("[yellow]Rebase sedang berjalan, ada conflict yang perlu diselesaikan:[/yellow]")
    ok, status_out, _err = run_git(["status", "--short"], cwd=repo)
    if ok and status_out:
        console.print(status_out)


def _friendly(err: str) -> str:
    """Ubah pesan error git mentah jadi pesan yang mudah dipahami user."""
    low = err.lower()
    if "no rebase in progress" in low:
        return "Tidak ada rebase yang sedang berjalan."
    if "you have unstaged changes" in low or "please commit or stash" in low or "cannot rebase" in low:
        return "Ada perubahan belum di-commit. Commit atau simpan ke Stash dulu sebelum rebase."
    if "could not resolve host" in low or "network" in low:
        return "Tidak dapat terhubung ke internet. Periksa koneksi kamu."
    return err or "Terjadi kesalahan yang tidak diketahui."


def show_help() -> None:
    """Tampilkan penjelasan singkat untuk menu ini."""
    console.print(
        "\n[bold cyan]Bantuan - Rebase[/bold cyan]\n"
        "Rebase menerapkan ulang commit branch aktif di atas branch lain,\n"
        "menghasilkan riwayat commit yang lurus (tanpa merge commit). Beda\n"
        "dengan Merge Lokal, yang membuat satu commit gabungan baru.\n\n"
        "- Rebase Branch Aktif: pilih branch target, commit branch aktif\n"
        "  ditata ulang di atasnya.\n"
        "- Update dari Upstream (Rebase): tarik perubahan terbaru dari\n"
        "  remote lalu rebase branch aktif di atasnya (alternatif Pull).\n"
        "- Lanjutkan Rebase: lanjutkan setelah conflict diselesaikan &\n"
        "  file sudah di-Git Add.\n"
        "- Lewati Commit: lewati commit yang lagi bermasalah saat rebase.\n"
        "- Batalkan Rebase: kembali ke kondisi sebelum rebase dimulai.\n"
        "- Status Rebase: cek apakah ada rebase yang belum selesai.\n\n"
        "[yellow]Peringatan: jangan rebase branch yang sudah di-push dan dipakai\n"
        "orang lain, kecuali kamu siap Force Push setelahnya.[/yellow]\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    """Tampilkan menu interaktif dan proses pilihan user."""
    while True:
        console.rule("[bold cyan]Rebase")
        repo = load_config().get("active_repository", "")
        sedang_rebase = bool(repo) and preflight.is_rebase_in_progress(repo)
        label_lanjut = "Lanjutkan Rebase (sedang berjalan!)" if sedang_rebase else "Lanjutkan Rebase"

        choice = questionary.select(
            "Pilih aksi:",
            choices=[
                "Rebase Branch Aktif",
                "Update dari Upstream (Rebase)",
                label_lanjut,
                "Lewati Commit",
                "Batalkan Rebase",
                "Status Rebase",
                "? Help",
                "Kembali",
            ],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            if choice == "Rebase Branch Aktif":
                rebase_branch()
            elif choice == "Update dari Upstream (Rebase)":
                update_dari_upstream()
            elif choice == label_lanjut:
                lanjutkan_rebase()
            elif choice == "Lewati Commit":
                lewati_rebase()
            elif choice == "Batalkan Rebase":
                batalkan_rebase()
            elif choice == "Status Rebase":
                status_rebase()
            elif choice == "? Help":
                show_help()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Rebase", e)
