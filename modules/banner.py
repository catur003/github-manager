"""
banner.py
Banner ASCII "GITHUB MANAGER" - gaya sama persis dengan yang ada di
install.sh (Termux/git clone) dan scripts/postinstall.js (npm), cuma versi
Python ini yang PASTI kebaca user, apapun cara install-nya:

- install.sh -> banner tampil langsung di terminal saat install selesai.
- npm install -g -> postinstall JALAN tapi npm v7+ SEMBUNYIIN outputnya
  secara default (baru kelihatan kalau user pakai --foreground-scripts,
  yang hampir gak pernah dipakai orang). Jadi banner scripts/postinstall.js
  gak bisa diandalkan sebagai satu-satunya tempat.
- Makanya banner ini juga ditampilkan sekali di run pertama app (lewat
  config['banner_shown'], lihat show_banner_once()) dan lewat
  'github-manager --version' - dua-duanya jalan lepas dari perilaku
  silent-nya npm postinstall.
"""

from rich.console import Console

from modules.utils import APP_VERSION

console = Console()

_TITLE = "-------------- G I T H U B --------------"

_MANAGER_BLOCK = [
    "#   #  ###  #   #  ###   #### ##### #### ",
    "## ## #   # ##  # #   # #     #     #   #",
    "# # # ##### # # # ##### #  ## ####  #### ",
    "#   # #   # #  ## #   # #   # #     # #  ",
    "#   # #   # #   # #   #  #### ##### #  ##",
]

_TAGLINE = "----- GitHub Repository Manager CLI -----"

_BOX_WIDTH = 41


def _box_line(text: str) -> str:
    content = f" {text}".ljust(_BOX_WIDTH)
    return f"|{content}|"


def render() -> str:
    """Bangun teks banner lengkap (dengan markup warna [white]/[green] ala
    rich) sebagai satu string, siap di-print lewat Console."""
    border = "+" + "-" * _BOX_WIDTH + "+"
    lines = [
        f"[bold white]{_TITLE}[/bold white]",
        "",
        "[green]" + "\n".join(_MANAGER_BLOCK) + "[/green]",
        "",
        f"[green]{_TAGLINE}[/green]",
        "",
        f"[green]{border}[/green]",
        f"[green]{_box_line(f'Version : {APP_VERSION}')}[/green]",
        f"[green]{_box_line('Author  : catur003')}[/green]",
        f"[green]{_box_line('')}[/green]",
        f"[green]{_box_line('✓ Siap dipakai')}[/green]",
        f"[green]{border}[/green]",
    ]
    return "\n".join(lines)


def show_banner() -> None:
    """Tampilkan banner ke terminal."""
    console.print(render())


def show_banner_once() -> None:
    """Tampilkan banner HANYA sekali sepanjang umur instalasi ini (dicatat
    lewat config['banner_shown']). Dipanggil dari github-manager.py sebelum
    masuk ke loop menu utama, supaya user yang install lewat npm (yang
    postinstall-nya silent) tetap kelihatan banner-nya minimal sekali."""
    # Lazy import supaya modul ini tidak ikut menarik dependency settings.py
    # (dan rantai import-nya) buat pemanggil yang cuma butuh render()/
    # show_banner() saja, misal dari --version.
    from modules.settings import load_config, save_config

    config = load_config()
    if config.get("banner_shown"):
        return
    show_banner()
    config["banner_shown"] = True
    save_config(config)
