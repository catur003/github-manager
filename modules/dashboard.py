"""
dashboard.py
Menampilkan dashboard ringkasan saat aplikasi dibuka:
repository aktif, lokasi, branch, remote, status git, ahead/behind,
commit terakhir, jumlah file berubah, tanggal & jam.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from modules.utils import run_git, is_git_repo, now_str
from modules.settings import load_config, get_repo_event

console = Console()


def get_status_summary(repo_path: str) -> dict:
    """Kumpulkan semua info status git untuk ditampilkan di dashboard."""
    info = {
        "branch": "-",
        "remote": "-",
        "upstream": "-",
        "connected": "-",
        "status": "Tidak diketahui",
        "ahead": 0,
        "behind": 0,
        "last_commit": "-",
        "changed_files": 0,
        "last_push": "-",
        "last_pull": "-",
    }
    if not is_git_repo(repo_path):
        return info

    ok, branch, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
    if ok:
        info["branch"] = branch or "-"

    ok, remotes, _ = run_git(["remote", "-v"], cwd=repo_path)
    if ok and remotes:
        first_line = remotes.splitlines()[0]
        parts = first_line.split()
        if len(parts) >= 2:
            info["remote"] = parts[1]
    # PRIORITAS 4: field "Connected" - terhubung ke remote atau enggak
    info["connected"] = "Ya" if info["remote"] != "-" else "Tidak (belum ada remote)"

    ok, upstream, _ = run_git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=repo_path
    )
    if ok and upstream:
        # PRIORITAS 4: field "Upstream" terpisah dari ahead/behind
        info["upstream"] = upstream
        ok, ahead_behind, _ = run_git(
            ["rev-list", "--left-right", "--count", f"HEAD...{upstream}"],
            cwd=repo_path,
        )
        if ok and ahead_behind:
            try:
                left, right = ahead_behind.split()
                info["ahead"], info["behind"] = int(left), int(right)
            except ValueError:
                pass
    else:
        info["upstream"] = "-"
        info["ahead"] = info["behind"] = "-"  # belum ada upstream, bukan 0

    ok, last_commit, _ = run_git(["log", "-1", "--pretty=%h %s"], cwd=repo_path)
    if ok and last_commit:
        info["last_commit"] = last_commit

    ok, status_out, _ = run_git(["status", "--porcelain"], cwd=repo_path)
    if ok:
        lines = [l for l in status_out.splitlines() if l.strip()]
        info["changed_files"] = len(lines)
        info["status"] = "Bersih (tidak ada perubahan)" if not lines else f"{len(lines)} file berubah"

    # PRIORITAS 4: Last Pull / Last Push - dicatat manual tiap kali sukses
    # (bukan dari git, karena git gak nyimpen waktu pull/push lokal)
    info["last_push"] = get_repo_event(repo_path, "last_push")
    info["last_pull"] = get_repo_event(repo_path, "last_pull")

    return info


def show_dashboard() -> None:
    """Render panel dashboard di terminal."""
    config = load_config()
    repo_path = config.get("active_repository", "")

    table = Table.grid(padding=(0, 1))
    table.add_column(justify="left", style="bold")
    table.add_column(justify="left")

    if not repo_path or not is_git_repo(repo_path):
        table.add_row("Repository aktif:", "[yellow]Belum dipilih[/yellow]")
        table.add_row("Tanggal & Jam:", now_str())
        console.print(Panel(table, title="[bold cyan]Dashboard[/bold cyan]", expand=False))
        console.print("[dim]Gunakan menu 'Repository' untuk memilih repository terlebih dahulu.[/dim]\n")
        return

    info = get_status_summary(repo_path)

    table.add_row("Repository aktif:", repo_path.split("/")[-1])
    table.add_row("Lokasi Repository:", repo_path)
    table.add_row("Branch aktif:", info["branch"])
    table.add_row("Remote:", info["remote"])
    table.add_row("Terhubung (Connected):", info["connected"])
    table.add_row("Upstream:", info["upstream"])
    table.add_row("Status Git:", info["status"])
    table.add_row("Ahead / Behind:", f"{info['ahead']} ahead / {info['behind']} behind")
    table.add_row("Commit terakhir:", info["last_commit"])
    table.add_row("Jumlah file berubah:", str(info["changed_files"]))
    table.add_row("Terakhir Push:", info["last_push"])
    table.add_row("Terakhir Pull:", info["last_pull"])
    table.add_row("Tanggal & Jam:", now_str())

    console.print(Panel(table, title="[bold cyan]Dashboard[/bold cyan]", expand=False))
