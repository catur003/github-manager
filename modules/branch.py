"""
branch.py
Menu Branch: lihat, checkout, buat, rename, delete, refresh.
"""

import questionary
from rich.console import Console
from rich.table import Table

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


def _list_branches(repo: str) -> list[str]:
    """Ambil daftar nama branch lokal di repository."""
    ok, out, _err = run_git(["branch", "--list"], cwd=repo)
    if not ok or not out:
        return []
    branches = []
    for line in out.splitlines():
        name = line.replace("*", "").strip()
        if name:
            branches.append(name)
    return branches


def lihat_branch() -> None:
    """Tampilkan daftar branch lokal beserta penanda branch aktif."""
    repo = _get_active_repo()
    if not repo:
        return
    ok, out, err = run_git(["branch", "-vv"], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal mengambil daftar branch: {err}[/red]")
        return
    table = Table(title="Daftar Branch", header_style="bold cyan")
    table.add_column("Branch")
    table.add_column("Info")
    for line in out.splitlines():
        aktif = line.startswith("*")
        clean = line.replace("*", "").strip()
        parts = clean.split(None, 1)
        name = parts[0] if parts else clean
        info = parts[1] if len(parts) > 1 else ""
        table.add_row(f"[green]{name} (aktif)[/green]" if aktif else name, info)
    console.print(table)


def checkout_branch() -> None:
    """Pindah (checkout) ke branch lain yang dipilih user."""
    repo = _get_active_repo()
    if not repo:
        return
    branches = _list_branches(repo)
    if not branches:
        console.print("[yellow]Tidak ada branch ditemukan.[/yellow]")
        return
    pilihan = questionary.select("Pilih branch untuk checkout:", choices=branches + ["Batal"]).ask()
    if not pilihan or pilihan == "Batal":
        return
    ok, out, err = run_git(["checkout", pilihan], cwd=repo)
    if not ok:
        if "would be overwritten by checkout" in err:
            console.print(
                "[red]Checkout gagal:[/red] ada file yang belum di-commit dan bakal ketimpa "
                "(biasanya config/config.json atau logs/*.log - file runtime yang berubah "
                "tiap app jalan).\n"
                "[yellow]Solusi: commit dulu perubahan itu (menu Commit), atau kalau memang "
                "gak penting, jalankan manual: git checkout -- <nama file>[/yellow]"
            )
        else:
            console.print(f"[red]Checkout gagal: {_friendly(err)}[/red]")
        log_error("Checkout branch gagal", raw_detail=err)
        return
    console.print(f"[green]Berhasil pindah ke branch '{pilihan}'.[/green]")
    log_activity(f"Branch {pilihan} aktif")


def buat_branch_baru() -> None:
    """Buat branch baru dari branch aktif saat ini."""
    repo = _get_active_repo()
    if not repo:
        return
    nama = questionary.text("Masukkan nama branch baru:").ask()
    if not nama:
        return
    ok, out, err = run_git(["checkout", "-b", nama], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal membuat branch: {_friendly(err)}[/red]")
        log_error("Gagal membuat branch", raw_detail=err)
        return
    console.print(f"[green]Branch '{nama}' berhasil dibuat dan aktif.[/green]")
    log_activity(f"Branch baru dibuat: {nama}")


def rename_branch() -> None:
    """Ganti nama branch yang dipilih user."""
    repo = _get_active_repo()
    if not repo:
        return
    branches = _list_branches(repo)
    lama = questionary.select("Pilih branch yang ingin di-rename:", choices=branches + ["Batal"]).ask()
    if not lama or lama == "Batal":
        return
    baru = questionary.text(f"Nama baru untuk '{lama}':").ask()
    if not baru:
        return
    ok, out, err = run_git(["branch", "-m", lama, baru], cwd=repo)
    if not ok:
        console.print(f"[red]Gagal rename branch: {_friendly(err)}[/red]")
        return
    console.print(f"[green]Branch '{lama}' berhasil diganti nama menjadi '{baru}'.[/green]")
    log_activity(f"Branch {lama} diubah nama menjadi {baru}")


def delete_branch() -> None:
    """Hapus branch lokal (dengan konfirmasi kalau belum ter-merge)."""
    repo = _get_active_repo()
    if not repo:
        return
    branches = _list_branches(repo)
    if not branches:
        console.print("[yellow]Tidak ada branch untuk dihapus.[/yellow]")
        return
    target = questionary.select("Pilih branch yang ingin dihapus:", choices=branches + ["Batal"]).ask()
    if not target or target == "Batal":
        return
    config = load_config()
    if config.get("konfirmasi_delete", True):
        yakin = questionary.confirm(f"Yakin ingin menghapus branch '{target}'? Aksi ini tidak dapat dibatalkan.",
                                     default=False).ask()
        if not yakin:
            console.print("[yellow]Dibatalkan.[/yellow]")
            return
    ok, out, err = run_git(["branch", "-d", target], cwd=repo)
    if not ok:
        console.print(f"[yellow]Branch belum sepenuhnya di-merge. {_friendly(err)}[/yellow]")
        paksa = questionary.confirm("Hapus paksa branch ini? (perubahan yang belum di-merge akan hilang)",
                                     default=False).ask()
        if paksa:
            ok, out, err = run_git(["branch", "-D", target], cwd=repo)
            if not ok:
                console.print(f"[red]Gagal menghapus branch: {_friendly(err)}[/red]")
                return
        else:
            return
    console.print(f"[green]Branch '{target}' berhasil dihapus.[/green]")
    log_activity(f"Branch {target} dihapus")


def refresh() -> None:
    """Tampilkan ulang status branch/remote terkini."""
    lihat_branch()


def _list_remote_branches(repo: str, remote: str = "origin") -> list[str]:
    """Ambil daftar nama branch di remote (tanpa prefix 'origin/')."""
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


def sync_branch() -> None:
    """Branch Synchronization: bandingkan branch lokal vs remote, tampilkan
    ahead/behind, branch yang hanya ada di satu sisi, lalu tawarkan aksi
    Fetch / Pull / Push / Hapus branch lokal / Hapus branch remote."""
    repo = _get_active_repo()
    if not repo:
        return

    with spinner("Fetch dari GitHub (sinkronisasi daftar branch)..."):
        run_git(["fetch", "--prune", "origin"], cwd=repo, timeout=60)

    local = _list_branches(repo)
    remote = _list_remote_branches(repo)
    ok, cur_out, _err = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    current = cur_out.strip() if ok else None

    both = [b for b in local if b in remote]
    only_local = [b for b in local if b not in remote]
    only_remote = [b for b in remote if b not in local]

    table = Table(title="Branch Synchronization", header_style="bold cyan")
    table.add_column("Branch")
    table.add_column("Status")
    table.add_column("Ahead/Behind")

    for b in both:
        ok_c, counts, _e = run_git(["rev-list", "--left-right", "--count", f"{b}...origin/{b}"], cwd=repo)
        ahead_behind = "-"
        if ok_c and counts:
            parts = counts.split()
            if len(parts) == 2:
                ahead_behind = f"↑{parts[0]} ↓{parts[1]}"
        label = f"{b} (aktif)" if b == current else b
        table.add_row(label, "Lokal + Remote", ahead_behind)
    for b in only_local:
        label = f"{b} (aktif)" if b == current else b
        table.add_row(label, "[yellow]Hanya Lokal[/yellow]", "-")
    for b in only_remote:
        table.add_row(b, "[cyan]Hanya di GitHub[/cyan]", "-")

    console.print(table)

    aksi = questionary.select(
        "Pilih aksi:",
        choices=["Fetch", "Pull", "Push", "Hapus Branch Lokal", "Hapus Branch Remote", "Kembali"],
    ).ask()
    if not aksi or aksi == "Kembali":
        return

    if aksi == "Fetch":
        with spinner("Fetch dari GitHub..."):
            ok2, _out, err = run_git(["fetch", "--prune", "origin"], cwd=repo, timeout=60)
        if ok2:
            console.print("[green]Fetch selesai.[/green]")
        else:
            console.print(f"[red]Fetch gagal: {err}[/red]")

    elif aksi == "Pull":
        from modules import pull as pull_module
        pull_module.pull()

    elif aksi == "Push":
        from modules import push as push_module
        push_module.push()

    elif aksi == "Hapus Branch Lokal":
        if not local:
            console.print("[yellow]Tidak ada branch lokal.[/yellow]")
            return
        target = questionary.select("Pilih branch lokal untuk dihapus:", choices=local + ["Batal"]).ask()
        if not target or target == "Batal":
            return
        if target == current:
            console.print("[red]Tidak bisa menghapus branch yang sedang aktif. Checkout ke branch lain dulu.[/red]")
            return
        yakin = questionary.confirm(f"Yakin hapus branch lokal '{target}'?", default=False).ask()
        if not yakin:
            return
        ok2, _out, err = run_git(["branch", "-d", target], cwd=repo)
        if not ok2:
            paksa = questionary.confirm(
                f"Branch belum sepenuhnya di-merge. {_friendly(err)} Hapus paksa?", default=False
            ).ask()
            if paksa:
                ok2, _out, err = run_git(["branch", "-D", target], cwd=repo)
        if ok2:
            console.print(f"[green]Branch lokal '{target}' berhasil dihapus.[/green]")
            log_activity(f"Sync Branch: branch lokal {target} dihapus")
        else:
            console.print(f"[red]Gagal menghapus branch lokal: {_friendly(err)}[/red]")

    elif aksi == "Hapus Branch Remote":
        if not remote:
            console.print("[yellow]Tidak ada branch di remote.[/yellow]")
            return
        target = questionary.select("Pilih branch remote untuk dihapus:", choices=remote + ["Batal"]).ask()
        if not target or target == "Batal":
            return
        yakin = questionary.confirm(
            f"Yakin hapus branch '{target}' dari GitHub? Ini memengaruhi semua orang yang pakai repo ini.",
            default=False,
        ).ask()
        if not yakin:
            return
        with spinner(f"Menghapus branch remote '{target}'..."):
            ok2, _out, err = run_git(["push", "origin", "--delete", target], cwd=repo, timeout=60)
        if ok2:
            console.print(f"[green]Branch remote '{target}' berhasil dihapus.[/green]")
            log_activity(f"Sync Branch: branch remote {target} dihapus")
        else:
            console.print(f"[red]Gagal menghapus branch remote: {_friendly(err)}[/red]")


def _friendly(err: str) -> str:
    """Ubah pesan error git mentah jadi pesan yang mudah dipahami user."""
    low = err.lower()
    if "not fully merged" in low:
        return "Branch belum sepenuhnya digabung (merge) ke branch lain."
    if "already exists" in low:
        return "Nama branch sudah digunakan."
    if "did not match any" in low or "not found" in low:
        return "Branch tidak ditemukan."
    return err or "Terjadi kesalahan yang tidak diketahui."


def show_help() -> None:
    """Tampilkan penjelasan singkat untuk menu ini."""
    console.print(
        "\n[bold cyan]Bantuan - Branch[/bold cyan]\n"
        "- Lihat Branch: menampilkan semua branch dan branch aktif saat ini.\n"
        "- Checkout Branch: berpindah ke branch lain.\n"
        "- Buat Branch Baru: membuat branch baru dari posisi saat ini.\n"
        "- Rename Branch: mengganti nama sebuah branch.\n"
        "- Delete Branch: menghapus branch (butuh konfirmasi).\n"
        "- Refresh: memuat ulang daftar branch.\n"
        "- Sync Branch: bandingkan branch lokal vs GitHub (ahead/behind,\n"
        "  branch yang cuma ada di satu sisi), lalu Fetch/Pull/Push atau\n"
        "  hapus branch lokal/remote dari sana.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    """Tampilkan menu interaktif dan proses pilihan user."""
    while True:
        console.rule("[bold cyan]Branch")
        choice = questionary.select(
            "Pilih aksi:",
            choices=[
                "Lihat Branch",
                "Checkout Branch",
                "Buat Branch Baru",
                "Rename Branch",
                "Delete Branch",
                "Sync Branch",
                "Refresh",
                "? Help",
                "Kembali",
            ],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Lihat Branch": lihat_branch,
                "Checkout Branch": checkout_branch,
                "Buat Branch Baru": buat_branch_baru,
                "Rename Branch": rename_branch,
                "Delete Branch": delete_branch,
                "Sync Branch": sync_branch,
                "Refresh": refresh,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Branch", e)
