"""
help.py
Menu 'Belajar Git': penjelasan konsep-konsep dasar Git dalam bahasa
Indonesia sederhana, untuk pengguna pemula.
"""

import questionary
from rich.console import Console
from rich.panel import Panel

console = Console()

MATERI = {
    "Repository": (
        "Repository adalah 'folder proyek' yang dilacak oleh Git. Di dalamnya\n"
        "tersimpan semua file proyek beserta seluruh riwayat perubahannya."
    ),
    "Branch": (
        "Branch adalah 'cabang' dari proyek. Kamu bisa membuat branch baru untuk\n"
        "mencoba fitur baru tanpa mengganggu kode utama (biasanya branch 'main')."
    ),
    "Remote": (
        "Remote adalah alamat repository yang tersimpan di server lain,\n"
        "misalnya di GitHub. Remote memungkinkan kamu berbagi kode dengan orang lain."
    ),
    "Origin": (
        "Origin adalah nama default untuk remote utama. Saat kamu clone sebuah\n"
        "repository, Git otomatis menamai remote-nya 'origin'."
    ),
    "Git Add": (
        "Git Add memasukkan perubahan file ke 'staging area', yaitu area\n"
        "persiapan sebelum perubahan benar-benar disimpan lewat commit."
    ),
    "Commit": (
        "Commit adalah 'menyimpan' perubahan yang ada di staging area, lengkap\n"
        "dengan pesan yang menjelaskan perubahan apa yang dilakukan."
    ),
    "Push": (
        "Push mengirim commit dari komputer/HP kamu ke repository di remote\n"
        "(misalnya GitHub), agar bisa dilihat atau dipakai orang lain."
    ),
    "Pull": (
        "Pull mengambil sekaligus menggabungkan perubahan terbaru dari remote\n"
        "ke repository lokal kamu."
    ),
    "Merge": (
        "Merge menggabungkan perubahan dari satu branch ke branch lain."
    ),
    "Force Push": (
        "Force Push memaksa remote memakai riwayat commit dari lokal kamu,\n"
        "walau berbeda dengan riwayat di server. Berbahaya karena bisa\n"
        "menghapus perubahan orang lain."
    ),
    "Clone": (
        "Clone adalah proses mengunduh (download) sebuah repository dari\n"
        "remote ke komputer/HP kamu, lengkap dengan seluruh riwayatnya."
    ),
    "Checkout": (
        "Checkout dipakai untuk berpindah antar branch, atau untuk mengambil\n"
        "versi lama dari sebuah file."
    ),
    "Staging": (
        "Staging area adalah 'tempat menunggu' bagi perubahan yang sudah di-add\n"
        "tapi belum di-commit. Anggap seperti keranjang belanja sebelum checkout."
    ),
    "Conflict": (
        "Conflict terjadi saat Git tidak bisa otomatis menggabungkan dua\n"
        "perubahan pada baris yang sama. Perlu diselesaikan secara manual."
    ),
    "HEAD": (
        "HEAD adalah penunjuk ke commit/posisi yang sedang aktif saat ini,\n"
        "biasanya menunjuk ke commit terakhir dari branch yang sedang dipakai."
    ),
    "Working Tree": (
        "Working Tree adalah folder proyek yang sebenarnya kamu lihat dan edit\n"
        "sehari-hari di file manager atau text editor."
    ),
    "Diagram Alur Git": (
        "Alur kerja Git secara sederhana:\n"
        "  Working Tree --(git add)--> Staging Area --(git commit)--> Local Repo\n"
        "  Local Repo --(git push)--> Remote Repo (misal GitHub)\n"
        "  Remote Repo --(git pull/fetch)--> Local Repo"
    ),
}


def menu() -> None:
    while True:
        console.rule("[bold cyan]Belajar Git")
        topik = questionary.select(
            "Pilih topik yang ingin dipelajari:",
            choices=list(MATERI.keys()) + ["Kembali"],
        ).ask()
        if topik is None or topik == "Kembali":
            return
        console.print(Panel(MATERI[topik], title=f"[bold cyan]{topik}[/bold cyan]", expand=False))
        questionary.text("Tekan Enter untuk kembali ke daftar topik...").ask()
