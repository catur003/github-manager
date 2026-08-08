"""
gitadd.py
Menu Git Add: Add Semua, Add File Tertentu, Unstage, Refresh.
"""

import questionary
from rich.console import Console
from rich.table import Table
from rich.markup import escape

from modules.utils import run_git
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


def _status_files(repo: str) -> list[tuple[str, str]]:
    """Ambil daftar file yang berubah dari 'git status --porcelain'."""
    ok, out, _err = run_git(["status", "--porcelain"], cwd=repo)
    if not ok or not out:
        return []
    result = []
    for line in out.splitlines():
        code = line[:2]
        path = line[3:]
        result.append((code, path))
    return result


def tampilkan_status(repo: str) -> None:
    """Tampilkan ringkasan file yang berubah di working tree."""
    files = _status_files(repo)
    if not files:
        console.print("[green]Tidak ada perubahan. Working tree bersih.[/green]")
        return
    table = Table(title="Status Perubahan", header_style="bold cyan")
    table.add_column("Status")
    table.add_column("File")
    for code, path in files:
        table.add_row(code.strip() or "?", path)
    console.print(table)


def _print_diff_content(diff_text: str) -> None:
    """Render isi 'git diff' dengan pewarnaan per baris: hijau = ditambah,
    merah = dihapus, cyan = header hunk (@@...@@), redup = metadata
    (diff --git, index ...). SEMUA baris di-escape() dulu sebelum di-print
    lewat rich - isi kode sungguhan sering mengandung karakter '[' ']'
    (array JS, generic TypeScript, dsb) yang kalau tidak di-escape bisa
    salah ditafsir rich sebagai style tag (bug class yang sama seperti
    kasus literal '[OK]' yang pernah ditemukan sebelumnya)."""
    if not diff_text.strip():
        console.print("[dim]Tidak ada perbedaan untuk ditampilkan.[/dim]")
        return
    for line in diff_text.splitlines():
        safe = escape(line)
        if line.startswith("+++") or line.startswith("---"):
            console.print(f"[bold]{safe}[/bold]")
        elif line.startswith("@@"):
            console.print(f"[cyan]{safe}[/cyan]")
        elif line.startswith("diff --git") or line.startswith("index "):
            console.print(f"[dim]{safe}[/dim]")
        elif line.startswith("+"):
            console.print(f"[green]{safe}[/green]")
        elif line.startswith("-"):
            console.print(f"[red]{safe}[/red]")
        else:
            console.print(safe)


def lihat_diff() -> None:
    """Lihat isi perubahan (diff) sebuah file dengan warna jelas - hijau
    untuk baris ditambah, merah untuk baris dihapus. Bisa lihat perubahan
    yang belum di-stage (working tree) ATAU yang sudah di-stage (siap
    commit), supaya jelas apa yang beneran akan masuk ke commit berikutnya."""
    repo = _get_active_repo()
    if not repo:
        return

    sumber = questionary.select(
        "Diff dari mana?",
        choices=["Belum di-stage (working tree)", "Sudah di-stage (siap commit)", "Batal"],
    ).ask()
    if not sumber or sumber == "Batal":
        return
    cached = sumber.startswith("Sudah")

    name_only_args = ["diff", "--cached", "--name-only"] if cached else ["diff", "--name-only"]
    ok, out, _err = run_git(name_only_args, cwd=repo)
    if not ok or not out.strip():
        label = "staging area" if cached else "working tree"
        console.print(f"[yellow]Tidak ada file dengan perubahan di {label}.[/yellow]")
        return
    files = out.splitlines()

    pilihan = questionary.select(
        "Pilih file untuk dilihat diff-nya:", choices=files + ["Semua File"]
    ).ask()
    if not pilihan:
        return

    base_args = ["diff", "--cached"] if cached else ["diff"]
    target_args = base_args if pilihan == "Semua File" else base_args + ["--", pilihan]
    ok, diff_out, err = run_git(target_args, cwd=repo)
    if not ok:
        console.print(f"[red]Gagal mengambil diff: {err}[/red]")
        return

    console.rule(f"[bold cyan]Diff - {pilihan}")
    _print_diff_content(diff_out)


def add_semua() -> None:
    """Stage semua file yang berubah (git add .)."""
    repo = _get_active_repo()
    if not repo:
        return
    tampilkan_status(repo)
    ok, _out, err = run_git(["add", "-A"], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal menambahkan file: {err}[/red]")
        log_error("Gagal git add -A", raw_detail=err)
        return
    console.print("[green]Semua perubahan berhasil ditambahkan ke staging area.[/green]")
    log_activity("Git Add berhasil (semua file)")


def add_file_tertentu() -> None:
    """Stage file tertentu yang dipilih user satu per satu."""
    repo = _get_active_repo()
    if not repo:
        return
    files = _status_files(repo)
    if not files:
        console.print("[green]Tidak ada perubahan untuk ditambahkan.[/green]")
        return
    choices = [path for _code, path in files]
    dipilih = questionary.checkbox("Pilih file yang ingin ditambahkan (spasi untuk pilih):", choices=choices).ask()
    if not dipilih:
        console.print("[yellow]Tidak ada file dipilih.[/yellow]")
        return
    ok, _out, err = run_git(["add", *dipilih], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal menambahkan file: {err}[/red]")
        log_error("Gagal git add file tertentu", raw_detail=err)
        return
    console.print(f"[green]{len(dipilih)} file berhasil ditambahkan ke staging area.[/green]")
    log_activity(f"Git Add berhasil ({len(dipilih)} file)")


def unstage() -> None:
    """Batalkan staging (git restore --staged) untuk file yang dipilih."""
    repo = _get_active_repo()
    if not repo:
        return
    ok, out, _err = run_git(["diff", "--cached", "--name-only"], cwd=repo)
    if not ok or not out:
        console.print("[yellow]Tidak ada file di staging area.[/yellow]")
        return
    staged = out.splitlines()
    dipilih = questionary.checkbox("Pilih file yang ingin di-unstage:", choices=staged + ["Unstage Semua"]).ask()
    if not dipilih:
        return
    if "Unstage Semua" in dipilih:
        ok, _out, err = run_git(["reset"], cwd=repo)
    else:
        ok, _out, err = run_git(["reset", *dipilih], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal unstage: {err}[/red]")
        return
    console.print("[green]Berhasil unstage.[/green]")
    log_activity("Unstage berhasil")


def refresh() -> None:
    """Tampilkan ulang status branch/remote terkini."""
    repo = _get_active_repo()
    if not repo:
        return
    tampilkan_status(repo)


def git_status_lengkap() -> None:
    """Tampilan lengkap untuk menu 'Git Status' di menu utama:
    Modified, Added, Deleted, Untracked (LENGKAP dengan nama filenya,
    bukan cuma jumlah), Ahead, Behind, Clean."""
    repo = _get_active_repo()
    if not repo:
        return
    files = _status_files(repo)
    kategori: dict[str, list[str]] = {"Modified": [], "Added": [], "Deleted": [], "Untracked": []}
    for code, path in files:
        if code.strip() == "??":
            kategori["Untracked"].append(path)
        elif "M" in code:
            kategori["Modified"].append(path)
        elif "A" in code:
            kategori["Added"].append(path)
        elif "D" in code:
            kategori["Deleted"].append(path)

    ok, branch, _err = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    branch = branch if ok else "-"
    ahead = behind = 0
    ok, ahead_behind, _err = run_git(
        ["rev-list", "--left-right", "--count", f"{branch}...origin/{branch}"], cwd=repo
    )
    if ok and ahead_behind:
        try:
            left, right = ahead_behind.split()
            ahead, behind = int(left), int(right)
        except ValueError:
            pass

    console.rule(f"[bold cyan]Git Status - branch '{branch}'")
    console.print(f"Ahead  : {ahead}  |  Behind : {behind}  |  Clean : {'Ya' if not files else 'Tidak'}\n")

    warna = {"Modified": "yellow", "Added": "green", "Deleted": "red", "Untracked": "dim"}
    if not files:
        console.print("[green]Tidak ada perubahan. Working tree bersih.[/green]")
        return
    for label, daftar in kategori.items():
        if not daftar:
            continue
        warna_label = warna[label]
        console.print(f"[bold {warna_label}]{label} ({len(daftar)})[/bold {warna_label}]")
        for path in daftar:
            console.print(f"  [{warna_label}]{escape(path)}[/{warna_label}]")
        console.print()


def show_help() -> None:
    """Tampilkan penjelasan singkat untuk menu ini."""
    console.print(
        "\n[bold cyan]Bantuan - Git Add[/bold cyan]\n"
        "- Add Semua: menambahkan semua perubahan ke staging area.\n"
        "- Add File Tertentu: memilih file tertentu untuk ditambahkan.\n"
        "- Lihat Diff: melihat isi perubahan per baris (hijau = ditambah,\n"
        "  merah = dihapus) sebelum di-add/commit - bisa lihat yang belum\n"
        "  di-stage atau yang sudah di-stage.\n"
        "- Unstage: membatalkan file dari staging area (belum menghapus perubahan).\n"
        "- Refresh: menampilkan ulang status perubahan terkini.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    """Tampilkan menu interaktif dan proses pilihan user."""
    while True:
        console.rule("[bold cyan]Git Add")
        choice = questionary.select(
            "Pilih aksi:",
            choices=["Add Semua", "Add File Tertentu", "Lihat Diff", "Unstage", "Refresh", "? Help", "Kembali"],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Add Semua": add_semua,
                "Add File Tertentu": add_file_tertentu,
                "Lihat Diff": lihat_diff,
                "Unstage": unstage,
                "Refresh": refresh,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Git Add", e)
