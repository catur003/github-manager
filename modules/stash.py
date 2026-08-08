"""
stash.py
Menu Stash: menyimpan perubahan yang belum di-commit secara sementara,
supaya working tree bisa dikosongkan tanpa harus commit dulu (mis. sebelum
checkout branch lain atau pull). Melengkapi alur yang sebelumnya cuma
dipakai otomatis-internal oleh Pull (auto-stash) - sekarang user bisa
kelola stash-nya sendiri secara penuh.
"""

import questionary
from rich.console import Console
from rich.table import Table

from modules.utils import run_git, confirm_text
from modules.settings import load_config
from modules.logger import log_activity, log_error

console = Console()


def _get_active_repo() -> str | None:
    """Ambil path repository aktif dari config, atau None + pesan kalau belum dipilih."""
    config = load_config()
    repo = config.get("active_repository", "")
    if not repo:
        console.print("[yellow]Repository tidak ditemukan. Silakan pilih repository terlebih dahulu.[/yellow]")
        return None
    return repo


def _parse_stash_entry(line: str) -> tuple[str, str]:
    """Pecah satu baris 'git stash list' (format 'ref|deskripsi') menjadi
    tuple (ref, deskripsi). Fungsi murni (tidak butuh git/network) supaya
    gampang diuji lewat unit test."""
    if not line:
        return "", ""
    if "|" not in line:
        return line.strip(), ""
    ref, _, desc = line.partition("|")
    return ref.strip(), desc.strip()


def _list_stash(repo: str) -> list[tuple[str, str]]:
    """Ambil daftar stash tersimpan sebagai list (ref, deskripsi)."""
    ok, out, _err = run_git(["stash", "list", "--pretty=format:%gd|%gs"], cwd=repo)
    if not ok or not out:
        return []
    return [_parse_stash_entry(line) for line in out.splitlines() if line.strip()]


def _pick_stash(repo: str, prompt_text: str = "Pilih stash:") -> str | None:
    """Tampilkan daftar stash untuk dipilih user, kembalikan ref-nya
    (mis. 'stash@{0}'), atau None kalau kosong/dibatalkan."""
    entries = _list_stash(repo)
    if not entries:
        console.print("[yellow]Tidak ada stash tersimpan.[/yellow]")
        return None
    choices = [f"{ref} - {desc}" if desc else ref for ref, desc in entries] + ["Batal"]
    pilihan = questionary.select(prompt_text, choices=choices).ask()
    if not pilihan or pilihan == "Batal":
        return None
    idx = choices.index(pilihan)
    return entries[idx][0]


def lihat_daftar_stash() -> None:
    """Tampilkan semua stash tersimpan dalam bentuk tabel."""
    repo = _get_active_repo()
    if not repo:
        return
    entries = _list_stash(repo)
    if not entries:
        console.print("[green]Tidak ada stash tersimpan.[/green]")
        return
    table = Table(title="Daftar Stash", header_style="bold cyan")
    table.add_column("Ref")
    table.add_column("Deskripsi")
    for ref, desc in entries:
        table.add_row(ref, desc)
    console.print(table)


def simpan_stash() -> None:
    """Simpan perubahan working tree saat ini ke stash (tidak menghapus
    riwayat commit apa pun, cuma menyimpan perubahan yang belum di-commit)."""
    repo = _get_active_repo()
    if not repo:
        return
    ok, status_out, _err = run_git(["status", "--porcelain"], cwd=repo)
    if not ok or not status_out.strip():
        console.print("[yellow]Tidak ada perubahan untuk di-stash. Working tree bersih.[/yellow]")
        return
    pesan = questionary.text("Pesan stash (opsional, kosongkan untuk pesan default):").ask()
    sertakan_untracked = questionary.confirm(
        "Sertakan file baru yang belum pernah di-add (untracked)?", default=True
    ).ask()
    args = ["stash", "push"]
    if sertakan_untracked:
        args.append("-u")
    if pesan and pesan.strip():
        args += ["-m", pesan.strip()]
    ok, out, err = run_git(args, cwd=repo)
    if not ok:
        console.print(f"[red]Gagal menyimpan stash: {_friendly(err)}[/red]")
        log_error("Gagal stash push", raw_detail=err)
        return
    console.print(f"[green]✓ Perubahan berhasil disimpan ke stash.[/green]\n{out}")
    log_activity("Stash disimpan" + (f": {pesan.strip()}" if pesan and pesan.strip() else ""))


def _report_stash_conflict(repo: str, aksi: str, ref: str, err: str) -> None:
    """Tangani hasil gagal dari 'stash apply'/'stash pop' secara konsisten:
    kalau penyebabnya conflict, stash TETAP ada (khusus utk pop, git sendiri
    tidak menghapusnya kalau gagal) - user diarahkan menyelesaikan manual."""
    low = err.lower()
    if "conflict" in low:
        console.print(
            f"[red]Terjadi CONFLICT saat {aksi} stash '{ref}'.[/red]\n"
            "[yellow]Stash TETAP tersimpan (tidak hilang) sampai conflict diselesaikan.[/yellow]"
        )
        ok2, status_out, _e = run_git(["status", "--short"], cwd=repo)
        if ok2 and status_out:
            console.print(status_out)
        console.print(
            "[yellow]Selesaikan conflict pada file di atas secara manual, lalu Git Add. "
            "Kalau stash ini sudah tidak dibutuhkan lagi, hapus manual lewat 'Hapus Stash'.[/yellow]"
        )
        log_activity(f"Stash {ref} gagal {aksi} - conflict")
        log_error(f"Stash {aksi} conflict", raw_detail=err)
        return
    console.print(f"[red]Gagal {aksi} stash: {_friendly(err)}[/red]")
    log_error(f"Gagal stash {aksi}", raw_detail=err)


def terapkan_stash() -> None:
    """Terapkan (apply) isi stash ke working tree TANPA menghapusnya dari daftar."""
    repo = _get_active_repo()
    if not repo:
        return
    ref = _pick_stash(repo, "Pilih stash untuk diterapkan (Apply):")
    if not ref:
        return
    ok, _out, err = run_git(["stash", "apply", ref], cwd=repo)
    if not ok:
        _report_stash_conflict(repo, "apply", ref, err)
        return
    console.print(f"[green]✓ Stash '{ref}' berhasil diterapkan (stash tetap tersimpan).[/green]")
    log_activity(f"Stash {ref} diterapkan (apply)")


def pop_stash() -> None:
    """Terapkan isi stash ke working tree LALU hapus dari daftar (kalau berhasil)."""
    repo = _get_active_repo()
    if not repo:
        return
    ref = _pick_stash(repo, "Pilih stash untuk di-Pop:")
    if not ref:
        return
    ok, _out, err = run_git(["stash", "pop", ref], cwd=repo)
    if not ok:
        _report_stash_conflict(repo, "pop", ref, err)
        return
    console.print(f"[green]✓ Stash '{ref}' berhasil di-pop (diterapkan & dihapus dari daftar).[/green]")
    log_activity(f"Stash {ref} di-pop")


def lihat_isi_stash() -> None:
    """Tampilkan isi (diff) sebuah stash tanpa menerapkannya ke working tree."""
    repo = _get_active_repo()
    if not repo:
        return
    ref = _pick_stash(repo, "Pilih stash untuk dilihat isinya:")
    if not ref:
        return
    ok, out, err = run_git(["stash", "show", "-p", ref], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal menampilkan isi stash: {_friendly(err)}[/red]")
        return
    if not out:
        console.print("[yellow]Stash ini tidak memiliki perubahan yang bisa ditampilkan.[/yellow]")
        return
    console.print(out)


def stash_ke_branch() -> None:
    """Buat branch baru langsung dari sebuah stash - berguna kalau ternyata
    perubahan di stash lebih cocok jadi branch sendiri, apalagi kalau
    apply/pop biasa gagal karena konteks branch aktif sudah berubah jauh."""
    repo = _get_active_repo()
    if not repo:
        return
    ref = _pick_stash(repo, "Pilih stash untuk dijadikan branch baru:")
    if not ref:
        return
    nama = questionary.text("Nama branch baru dari stash ini:").ask()
    if not nama or not nama.strip():
        console.print("[yellow]Nama branch tidak boleh kosong. Dibatalkan.[/yellow]")
        return
    ok, _out, err = run_git(["stash", "branch", nama.strip(), ref], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal membuat branch dari stash: {_friendly(err)}[/red]")
        log_error("Gagal stash branch", raw_detail=err)
        return
    console.print(f"[green]✓ Branch '{nama.strip()}' berhasil dibuat dari stash '{ref}' dan langsung aktif.[/green]")
    log_activity(f"Branch {nama.strip()} dibuat dari stash {ref}")


def hapus_stash() -> None:
    """Hapus satu stash tertentu (butuh konfirmasi, ikut setting konfirmasi_delete)."""
    repo = _get_active_repo()
    if not repo:
        return
    ref = _pick_stash(repo, "Pilih stash untuk dihapus:")
    if not ref:
        return
    config = load_config()
    if config.get("konfirmasi_delete", True):
        yakin = questionary.confirm(
            f"Yakin ingin menghapus stash '{ref}'? Aksi ini tidak dapat dibatalkan.", default=False
        ).ask()
        if not yakin:
            console.print("[yellow]Dibatalkan.[/yellow]")
            return
    ok, _out, err = run_git(["stash", "drop", ref], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal menghapus stash: {_friendly(err)}[/red]")
        log_error("Gagal stash drop", raw_detail=err)
        return
    console.print(f"[green]✓ Stash '{ref}' berhasil dihapus.[/green]")
    log_activity(f"Stash {ref} dihapus")


def hapus_semua_stash() -> None:
    """Hapus SEMUA stash sekaligus - destruktif, konsisten dengan Force Push
    (butuh ketik 'YA' persis, bukan cuma konfirmasi Ya/Tidak biasa)."""
    repo = _get_active_repo()
    if not repo:
        return
    entries = _list_stash(repo)
    if not entries:
        console.print("[yellow]Tidak ada stash untuk dihapus.[/yellow]")
        return
    console.print(f"[yellow]Akan menghapus SEMUA {len(entries)} stash. Aksi ini tidak dapat dibatalkan.[/yellow]")
    setuju = confirm_text("YA", "Ketik 'YA' untuk menghapus semua stash:")
    if not setuju:
        console.print("[yellow]Dibatalkan.[/yellow]")
        return
    ok, _out, err = run_git(["stash", "clear"], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal menghapus semua stash: {_friendly(err)}[/red]")
        log_error("Gagal stash clear", raw_detail=err)
        return
    console.print("[green]✓ Semua stash berhasil dihapus.[/green]")
    log_activity(f"Semua stash dihapus ({len(entries)} stash)")


def refresh() -> None:
    """Tampilkan ulang daftar stash terkini."""
    lihat_daftar_stash()


def _friendly(err: str) -> str:
    """Ubah pesan error git mentah jadi pesan yang mudah dipahami user."""
    low = err.lower()
    if "no stash entries" in low:
        return "Tidak ada stash tersimpan."
    if "conflict" in low:
        return "Terjadi conflict saat menerapkan stash."
    if "unknown revision" in low or "no such stash" in low or "unknown stash" in low:
        return "Stash yang dipilih tidak ditemukan (mungkin sudah dihapus di tempat lain)."
    return err or "Terjadi kesalahan yang tidak diketahui."


def show_help() -> None:
    """Tampilkan penjelasan singkat untuk menu ini."""
    console.print(
        "\n[bold cyan]Bantuan - Stash[/bold cyan]\n"
        "Stash menyimpan perubahan yang belum di-commit secara sementara,\n"
        "supaya working tree bisa dikosongkan tanpa harus commit dulu.\n"
        "Berguna saat mau pindah branch atau pull padahal masih ada\n"
        "perubahan yang belum siap di-commit.\n\n"
        "- Simpan Stash: simpan perubahan saat ini ke stash.\n"
        "- Lihat Daftar Stash: menampilkan semua stash tersimpan.\n"
        "- Terapkan Stash (Apply): terapkan isi stash, stash TETAP tersimpan.\n"
        "- Pop Stash: terapkan isi stash lalu hapus dari daftar (kalau sukses).\n"
        "- Lihat Isi Stash: melihat diff sebuah stash tanpa menerapkannya.\n"
        "- Stash ke Branch Baru: buat branch baru langsung dari sebuah stash.\n"
        "- Hapus Stash: menghapus satu stash tertentu.\n"
        "- Hapus Semua Stash: menghapus seluruh stash (butuh ketik 'YA').\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    """Tampilkan menu interaktif dan proses pilihan user."""
    while True:
        console.rule("[bold cyan]Stash")
        choice = questionary.select(
            "Pilih aksi:",
            choices=[
                "Simpan Stash",
                "Lihat Daftar Stash",
                "Terapkan Stash (Apply)",
                "Pop Stash",
                "Lihat Isi Stash",
                "Stash ke Branch Baru",
                "Hapus Stash",
                "Hapus Semua Stash",
                "Refresh",
                "? Help",
                "Kembali",
            ],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Simpan Stash": simpan_stash,
                "Lihat Daftar Stash": lihat_daftar_stash,
                "Terapkan Stash (Apply)": terapkan_stash,
                "Pop Stash": pop_stash,
                "Lihat Isi Stash": lihat_isi_stash,
                "Stash ke Branch Baru": stash_ke_branch,
                "Hapus Stash": hapus_stash,
                "Hapus Semua Stash": hapus_semua_stash,
                "Refresh": refresh,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Stash", e)
