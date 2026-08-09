"""
upload.py
Menu Upload: Upload File, Upload Folder, Upload ZIP (Extract),
Upload ZIP (No Extract).

Semua sumber file/folder dipilih lewat picker interaktif (Downloads/Home/
Browse Folder/Manual Path) - user tidak perlu mengetik path manual kecuali
memang memilih itu. Tujuan di dalam repository juga dipilih lewat folder
picker (bukan mengetik path).
"""

import os
import shutil
import zipfile
from typing import Optional, Tuple

import questionary
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from modules.utils import (
    run_git, count_files_in_dir, human_size, pick_folder_in_repo,
    sha1_of_file, sha1_of_bytes, spinner, safe_zip_member_path,
)
from modules.settings import load_config
from modules.logger import log_activity, log_error
from modules import backup as backup_module
from modules import preflight

console = Console()

# BUGFIX TINGGI: sebelumnya SKIP_DIRS di utils.py cuma dipakai saat scan
# repo (find_git_repos), sama sekali tidak dipakai di jalur Upload manapun -
# jadi node_modules/, .env, dist/, dan folder besar/sensitif lainnya bisa
# ikut terupload ke repo tanpa disadari. Daftar ini jadi jaring pengaman
# BAWAAN (selalu aktif), digabung (union) dengan isi .gitignore repo
# tujuan kalau ada (lihat _read_gitignore_patterns / _should_exclude_upload_entry).
_DEFAULT_EXCLUDE_NAMES = {
    "node_modules", ".env", "dist", ".next", "venv", ".venv",
    "__pycache__", ".git", "build", ".cache", ".dart_tool", ".gradle",
    ".idea", ".vscode", "vendor", "target",
}


def _read_gitignore_patterns(repo: str) -> list[str]:
    """Baca .gitignore di root repo (kalau ada). Parsing sederhana: baris
    kosong & komentar (#) diabaikan. Ini BUKAN implementasi gitignore
    lengkap - cukup dipakai sebagai lapis kedua saat Upload, bukan
    pengganti .gitignore asli project."""
    path = os.path.join(repo, ".gitignore")
    patterns: list[str] = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("!"):
                    continue
                patterns.append(line.rstrip("/"))
    except OSError:
        pass
    return patterns


def _should_exclude_upload_entry(rel_path: str, gitignore_patterns: list[str]) -> bool:
    """True kalau rel_path (dipisah '/') harus DILEWATI saat upload -
    cocok dengan salah satu nama folder/file bawaan (_DEFAULT_EXCLUDE_NAMES)
    ATAU cocok pola di .gitignore repo tujuan."""
    import fnmatch
    parts = rel_path.split("/")
    if any(p in _DEFAULT_EXCLUDE_NAMES for p in parts):
        return True
    for pattern in gitignore_patterns:
        if not pattern:
            continue
        if "/" in pattern:
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path, pattern + "/*"):
                return True
        elif any(fnmatch.fnmatch(part, pattern) for part in parts):
            return True
    return False


def _get_active_repo() -> Optional[str]:
    config = load_config()
    repo = config.get("active_repository", "")
    if not repo:
        console.print("[yellow]Repository tidak ditemukan. Silakan pilih repository terlebih dahulu.[/yellow]")
        return None
    return repo


def _downloads_dir() -> str:
    for candidate in ("~/storage/downloads", "~/Download", "~/Downloads"):
        path = os.path.expanduser(candidate)
        if os.path.isdir(path):
            return path
    return os.path.expanduser("~")


# ---------------------------------------------------------------------------
# PRIORITAS 3 #8/#9 - Picker sumber file, tidak perlu ketik path manual
# ---------------------------------------------------------------------------

def _browse_for_path(start_dir: str, want_ext: Optional[str] = None,
                      pick_folder: bool = False) -> Optional[str]:
    """
    Browser folder interaktif sederhana. Kalau pick_folder=True, user
    memilih FOLDER (bisa langsung pilih folder saat ini). Kalau False,
    user menavigasi sampai memilih sebuah FILE (opsional difilter want_ext).
    """
    current = os.path.abspath(start_dir)
    while True:
        try:
            entries = sorted(os.listdir(current))
        except OSError as e:
            console.print(f"[red]Tidak bisa membaca folder ini: {e}[/red]")
            return None

        dirs = [e for e in entries if os.path.isdir(os.path.join(current, e)) and not e.startswith(".")]
        files = []
        if not pick_folder:
            files = [e for e in entries if os.path.isfile(os.path.join(current, e)) and not e.startswith(".")]
            if want_ext:
                files = [f for f in files if f.lower().endswith(want_ext)]

        choices = []
        if pick_folder:
            choices.append("[Pilih folder ini]")
        parent = os.path.dirname(current.rstrip("/"))
        if parent and parent != current:
            choices.append(".. (naik satu folder)")
        choices += [f"[DIR] {d}/" for d in dirs]
        choices += files
        choices.append("Batal")

        pilihan = questionary.select(f"Browse: {current}", choices=choices).ask()
        if not pilihan or pilihan == "Batal":
            return None
        if pilihan == "[Pilih folder ini]":
            return current
        if pilihan.startswith(".."):
            current = parent
            continue
        if pilihan.startswith("[DIR] "):
            current = os.path.join(current, pilihan[6:].rstrip("/"))
            continue
        return os.path.join(current, pilihan)


def _pick_source_file(label: str = "file", want_ext: Optional[str] = None,
                       include_home: bool = True) -> Optional[str]:
    """
    Menu sumber standar: Downloads (default) / Home / Browse Folder / Manual Path.
    """
    choices = ["Downloads"]
    if include_home:
        choices.append("Home")
    choices += ["Browse Folder", "Manual Path", "Batal"]

    sumber = questionary.select(f"Pilih sumber {label}:", choices=choices).ask()
    if not sumber or sumber == "Batal":
        return None

    if sumber == "Downloads":
        return _browse_for_path(_downloads_dir(), want_ext=want_ext)
    if sumber == "Home":
        return _browse_for_path(os.path.expanduser("~"), want_ext=want_ext)
    if sumber == "Browse Folder":
        return _browse_for_path(os.path.expanduser("~"), want_ext=want_ext)
    if sumber == "Manual Path":
        path = questionary.text(f"Masukkan path lengkap {label}:").ask()
        if not path:
            return None
        path = os.path.expanduser(path.strip())
        if not os.path.isfile(path):
            console.print("[red]File tidak ditemukan di path tersebut.[/red]")
            return None
        return path
    return None


def _pick_source_folder(label: str = "folder") -> Optional[str]:
    choices = ["Home", "Browse Folder", "Manual Path", "Batal"]
    sumber = questionary.select(f"Pilih sumber {label}:", choices=choices).ask()
    if not sumber or sumber == "Batal":
        return None
    if sumber == "Home":
        return _browse_for_path(os.path.expanduser("~"), pick_folder=True)
    if sumber == "Browse Folder":
        return _browse_for_path(os.path.expanduser("~"), pick_folder=True)
    if sumber == "Manual Path":
        path = questionary.text(f"Masukkan path lengkap {label}:").ask()
        if not path:
            return None
        path = os.path.expanduser(path.strip())
        if not os.path.isdir(path):
            console.print("[red]Folder tidak ditemukan.[/red]")
            return None
        return path
    return None


# ---------------------------------------------------------------------------
# ZIP helpers - preview, wrapper detection, diff (PRIORITAS 3 #12/#13)
# ---------------------------------------------------------------------------

def preview_zip(zip_path: str) -> None:
    """Tampilkan isi ZIP mentah (nama & ukuran) sebelum ekstraksi."""
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            table = Table(title=f"Isi ZIP ({len(names)} entri)", header_style="bold cyan")
            table.add_column("Nama File")
            table.add_column("Ukuran")
            for info in z.infolist()[:30]:
                table.add_row(info.filename, human_size(info.file_size))
            if len(names) > 30:
                table.add_row("...", f"dan {len(names) - 30} entri lainnya")
            console.print(table)
    except zipfile.BadZipFile:
        console.print("[red]File ZIP rusak atau tidak valid.[/red]")
        raise


def _detect_zip_root(zip_path: str) -> str:
    """
    Mendeteksi root folder dalam ZIP dengan menelusuri "rantai wrapper"
    secara struktural: mulai dari root ZIP, turun satu level SELAMA level
    itu cuma berisi satu folder tunggal (tanpa file lain sejajar). Begitu
    ketemu level yang punya file, atau lebih dari satu folder, berhenti -
    level itu dianggap isi project yang sebenarnya.

    Kenapa diubah dari pendekatan lama (cari file marker di mana pun posisinya
    di dalam ZIP): pendekatan lama bisa salah nebak kalau ada file senama
    marker (mis. README.md) yang kebetulan nyempil di dalam subfolder
    (co: "app/README.md") dan urutan iterasi ZIP menemukannya duluan
    dibanding marker yang benar-benar di root - akibatnya ZIP tanpa
    wrapper (0 wrapper) bisa salah dianggap folder itu wrapper, lalu
    folder app/ (dan folder lain yang sejajar) ikut kepotong dari hasil
    ekstrak. Pendekatan baru ini murni berdasar struktur, jadi tidak akan
    nyasar ke file yang kebetulan senama di kedalaman lain.

    Return:
    - ""            -> 0 wrapper.
    - "a/b/.../"    -> wrapper (1 level atau berantai/nested) yang harus dihapus.
    - "AMBIGU:<prefix>" -> level <prefix> berisi >1 folder tanpa file penyeimbang,
      tidak bisa dipastikan otomatis mana root project-nya (kecuali marker
      cuma cocok di salah satu folder itu, maka langsung dipilih otomatis).
    """
    markers = ['package.json', 'requirements.txt', 'README.md', 'github-manager.py', 'main.py']

    # BUGFIX: nama folder umum yang lazim jadi folder TOP-LEVEL project asli
    # (bukan folder wrapper ZIP buangan) - mis. Next.js App Router pakai
    # struktur app/siswa/route.js. Sebelumnya, kalau suatu level di ZIP cuma
    # berisi satu folder tunggal tanpa file penyeimbang, folder itu SELALU
    # dianggap wrapper dan ikut dihapus/turun terus - jadi "app/siswa/
    # route.js" salah dianggap 2 level wrapper ("app/siswa/"), padahal
    # keduanya bagian sah dari struktur project. Begitu folder di level itu
    # cocok salah satu nama ini, chain wrapper dihentikan DI level itu -
    # folder ini & isinya dianggap root project apa adanya, tidak diturunkan
    # lagi sebagai wrapper.
    _COMMON_PROJECT_DIRS = {
        'app', 'src', 'pages', 'components', 'lib', 'public', 'api',
        'styles', 'assets', 'tests', 'test', '__tests__', 'docs',
        'config', 'scripts', 'server', 'client', 'modules',
    }

    with zipfile.ZipFile(zip_path, "r") as z:
        namelist = z.namelist()

    def _entries_at(prefix: str):
        """Item (folder & file) yang persis satu level di bawah prefix."""
        dirs = set()
        files = []
        plen = len(prefix)
        for name in namelist:
            if prefix and not name.startswith(prefix):
                continue
            rel = name[plen:]
            if not rel:
                continue
            parts = rel.split('/')
            if len(parts) > 1:
                if parts[0]:
                    dirs.add(parts[0])
            elif not rel.endswith('/') and parts[0]:
                files.append(parts[0])
        return dirs, files

    prefix = ""
    while True:
        dirs, files = _entries_at(prefix)

        if not dirs and not files:
            # Level kosong (folder eksplisit tanpa isi) - anggap ini root-nya.
            return prefix

        if files or len(dirs) > 1:
            if len(dirs) > 1 and not files:
                # >1 folder sejajar, tidak ada file penyeimbang di level ini.
                # Coba disambiguasi pakai marker yang PERSIS ada langsung di
                # dalam salah satu folder kandidat (bukan marker yang
                # nyasar di kedalaman lain).
                candidates = []
                for d in sorted(dirs):
                    _sub_dirs, sub_files = _entries_at(prefix + d + "/")
                    if any(f in markers for f in sub_files):
                        candidates.append(d)
                if len(candidates) == 1:
                    return prefix + candidates[0] + "/"
                return f"AMBIGU:{prefix}"
            return prefix

        # Cuma ada 1 folder tunggal & tidak ada file di level ini. Ini BISA
        # wrapper (turun satu level lagi), TAPI kalau nama foldernya cocok
        # nama folder project umum (app/, src/, dst), jangan dianggap
        # wrapper - berhenti di sini supaya folder itu tidak ikut kestrip.
        only_dir = next(iter(dirs))
        if only_dir.lower() in _COMMON_PROJECT_DIRS:
            return prefix
        prefix = prefix + only_dir + "/"


# ---------------------------------------------------------------------------
# ZIP Analyzer & Upload Preview - tree view (rich.Tree, sudah bagian dari
# package rich yang sudah jadi dependency project ini, bukan dependency baru)
# ---------------------------------------------------------------------------

def _build_zip_tree(zip_path: str) -> dict:
    """Bangun struktur nested dict dari isi ZIP: {"dirs": {nama: subtree}, "files": [(nama, size), ...]}."""
    root: dict = {"dirs": {}, "files": []}
    with zipfile.ZipFile(zip_path, "r") as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            parts = [p for p in info.filename.split("/") if p]
            if not parts:
                continue
            node = root
            for part in parts[:-1]:
                node = node["dirs"].setdefault(part, {"dirs": {}, "files": []})
            node["files"].append((parts[-1], info.file_size))
    return root


def _count_zip_items(zip_path: str) -> Tuple[int, int]:
    """Hitung total (jumlah_file, jumlah_folder) di seluruh ZIP. Folder dihitung
    dari semua prefix path unik (bukan cuma entry direktori eksplisit, karena
    banyak ZIP tidak menyertakan entry direktori eksplisit sama sekali)."""
    with zipfile.ZipFile(zip_path, "r") as z:
        namelist = z.namelist()

    files = 0
    dirs = set()
    for name in namelist:
        if name.endswith("/"):
            trimmed = name.rstrip("/")
            if trimmed:
                dirs.add(trimmed)
            continue
        files += 1
        parts = name.split("/")[:-1]
        acc = []
        for p in parts:
            if not p:
                continue
            acc.append(p)
            dirs.add("/".join(acc))
    return files, len(dirs)


def _tree_node_at(content_tree: dict, chain: list) -> dict:
    """Navigasi ke subtree sesuai daftar nama folder berantai (chain)."""
    node = content_tree
    for name in chain:
        node = node["dirs"].get(name, {"dirs": {}, "files": []})
    return node


def _attach_children(node, subtree: dict, limit: int = 20) -> None:
    """Tempel isi langsung (satu level, tidak rekursif) dari subtree ke node Tree."""
    dir_names = sorted(subtree["dirs"].keys())
    file_names = sorted(name for name, _size in subtree["files"])
    all_items = [(d, True) for d in dir_names] + [(f, False) for f in file_names]

    shown = all_items[:limit] if limit else all_items
    for name, is_dir in shown:
        node.add(f"📁 {name}" if is_dir else f"📄 {name}")

    remaining = len(all_items) - len(shown)
    if remaining > 0:
        node.add(f"[dim]... dan {remaining} item lainnya[/dim]")


def _render_zip_structure_tree(zip_path: str, wrapper_chain: list,
                                ambiguous_children: Optional[list] = None) -> None:
    """
    Render tree 'ZIP Analyzer'.
    - Kalau ambiguous_children None: root project sudah pasti - folder
      terakhir di wrapper_chain ditandai 🟢 Root Project, sisanya 🟡 Wrapper
      (akan dihapus), lalu isi langsung root project ditampilkan.
    - Kalau ambiguous_children diisi: root belum bisa dipastikan - semua
      folder di wrapper_chain masih 🟡 (belum pasti wrapper atau bukan),
      dan folder-folder kandidat sejajar di ujung chain ditampilkan sebagai
      pilihan (belum diberi label root/wrapper).
    """
    tree = Tree("📦 [bold]ZIP Analyzer[/bold]")
    node = tree
    for i, name in enumerate(wrapper_chain):
        is_last = (i == len(wrapper_chain) - 1)
        if ambiguous_children is not None:
            label = f"🟡 {name}"
        else:
            label = f"🟢 {name}" if is_last else f"🟡 {name}"
        node = node.add(label)

    if ambiguous_children is not None:
        for child in sorted(ambiguous_children):
            node.add(f"📁 {child}")
    else:
        content_tree = _build_zip_tree(zip_path)
        cur = _tree_node_at(content_tree, wrapper_chain)
        _attach_children(node, cur)

    console.print(tree)

    if ambiguous_children is None and wrapper_chain:
        console.print()
        console.print("🟢 Root Project")
        console.print("🟡 Wrapper (akan dihapus)")


def _render_upload_preview(zip_path: str, root_prefix: str) -> None:
    """Render 'Upload Preview': struktur akhir yang akan muncul di repository
    setelah ekstraksi (mengikuti root project yang sudah dipilih/terdeteksi)."""
    chain = [c for c in root_prefix.split("/") if c] if root_prefix else []
    content_tree = _build_zip_tree(zip_path)
    cur = _tree_node_at(content_tree, chain)

    tree = Tree("📤 [bold]Upload Preview[/bold]")
    _attach_children(tree, cur)
    console.print(tree)


def _print_zip_stats(zip_path: str, wrapper_chain: list) -> None:
    n_files, n_dirs = _count_zip_items(zip_path)
    zip_size = os.path.getsize(zip_path)

    stats = Table.grid(padding=(0, 2))
    stats.add_row("Jumlah wrapper", str(len(wrapper_chain)))
    stats.add_row("Jumlah folder", str(n_dirs))
    stats.add_row("Jumlah file", str(n_files))
    stats.add_row("Ukuran ZIP", human_size(zip_size))
    console.print(stats)


def _zip_target_rel(member_name: str, root_prefix: str) -> Optional[str]:
    """Path relatif tujuan dengan mempertahankan struktur di dalam root_prefix."""
    if not root_prefix:
        return member_name
        
    if member_name.startswith(root_prefix):
        rel = member_name[len(root_prefix):]
        return rel if rel else None
    return None


def _compute_zip_diff(zip_path: str, dest_dir: str, root_prefix: str,
                       gitignore_patterns: Optional[list] = None) -> Tuple[int, int, int, int, int, dict]:
    """
    Hitung berapa file akan Tambah / Update / Sama / Delete kalau ZIP ini
    diekstrak ke dest_dir. Hanya memproses file yang berada di dalam root_prefix.
    Entry yang cocok filter default/.gitignore (lihat _should_exclude_upload_entry)
    dilewati dan dihitung terpisah sebagai 'dilewati' (excluded), bukan
    ditambahkan ke target_map.
    """
    tambah = update = sama = dilewati = 0
    target_map: dict = {}
    patterns = gitignore_patterns or []

    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.infolist():
            if member.is_dir():
                continue
            rel = _zip_target_rel(member.filename, root_prefix)
            if not rel:
                continue

            if _should_exclude_upload_entry(rel, patterns):
                dilewati += 1
                continue

            # SECURITY: Zip Slip protection - tolak entry yang path-nya
            # keluar dari dest_dir (mis. lewat '../../') sebelum dihitung
            # sebagai perubahan, biar preview diff juga akurat/aman.
            target_path = safe_zip_member_path(dest_dir, rel)
            if target_path is None:
                continue
            target_map[target_path] = member.filename

            if not os.path.exists(target_path):
                tambah += 1
                continue

            local_hash = sha1_of_file(target_path)
            with z.open(member) as f:
                zip_hash = sha1_of_bytes(f.read())
            if local_hash != zip_hash:
                update += 1
            else:
                sama += 1

    delete = 0
    if os.path.isdir(dest_dir):
        for root, _dirs, files in os.walk(dest_dir):
            if os.sep + ".git" in root or root.rstrip("/").endswith(".git"):
                continue
            for fname in files:
                full = os.path.join(root, fname)
                if full not in target_map:
                    delete += 1

    return tambah, update, sama, delete, dilewati, target_map


def _confirm_zip_changes(repo: str, branch: str, total_entries: int, root_prefix: str,
                          tambah: int, update: int, sama: int, delete: int,
                          dilewati: int = 0, gitignore_found: bool = False) -> bool:
    console.print(f"\n[bold]Repository[/bold] : {os.path.basename(repo)}")
    console.print(f"[bold]Branch[/bold]     : {branch}\n")

    console.print("[bold cyan]ZIP[/bold cyan]")
    console.print("──────────────")
    console.print(f"Total File yg Diproses : {total_entries}")
    if root_prefix:
        console.print(f"Root Project           : {root_prefix} [yellow](wrapper akan dihapus)[/yellow]")
    else:
        console.print("Root Project           : (Langsung dari root ZIP)")

    # BUGFIX TINGGI: notice filter node_modules/.env/dst sebelum konfirmasi,
    # supaya user tahu ada file yang otomatis dilewati (bukan cuma diam-diam).
    if gitignore_found:
        console.print(
            f"\n[green]✓ .gitignore terdeteksi[/green] - {dilewati} file cocok pola .gitignore/aturan "
            f"bawaan (node_modules, .env, dst) dilewati otomatis."
        )
    else:
        console.print(
            f"\n[yellow]⚠ .gitignore tidak terdeteksi[/yellow] - {dilewati} file dilewati otomatis "
            f"lewat aturan bawaan (node_modules, .env, dist, dst). Disarankan buat .gitignore "
            f"di repository ini."
        )

    console.print("\n[bold cyan]Analisis Perubahan[/bold cyan]")
    console.print("──────────────────")
    console.print(f"[green]✓ Sama (tidak berubah)[/green] : {sama}")
    console.print(f"[yellow]🟡 Update             [/yellow] : {update}")
    console.print(f"[green]🟢 File Baru          [/green] : {tambah}")
    console.print(f"[red]🔴 Akan Dihapus       [/red] : {delete} [dim](info saja, tidak dihapus otomatis)[/dim]")

    return bool(questionary.confirm("\nLanjutkan ekstrak?", default=True).ask())


# ---------------------------------------------------------------------------
# Upload ZIP (Extract)
# ---------------------------------------------------------------------------

def _confirm_or_override_root(zip_path: str, root_prefix: str) -> Optional[str]:
    """Tampilkan root project yang terdeteksi OTOMATIS dan minta konfirmasi
    user, dengan opsi override manual kalau deteksinya salah.

    BUGFIX: sebelumnya, begitu _detect_zip_root() menghasilkan jawaban
    yang 'yakin' (bukan AMBIGU) - termasuk kasus folder wrapper yang
    kebetulan namanya sama dengan folder project umum (app/, src/, dst di
    _COMMON_PROJECT_DIRS, sehingga otomatis dianggap BUKAN wrapper) -
    keputusan itu langsung final dipakai tanpa user sempat lihat/koreksi.
    Kalau heuristiknya salah nebak untuk struktur ZIP yang gak biasa, user
    gak punya cara membetulkannya - ini fungsi yang mengisi celah itu:
    SELALU tampilkan hasil deteksi + tawarkan override manual, bukan cuma
    untuk kasus yang sudah "AMBIGU" secara struktural.

    Return root_prefix final (bisa "" untuk 0 wrapper), atau None kalau
    user membatalkan."""
    wrapper_chain = [c for c in root_prefix.split("/") if c] if root_prefix else []
    label = root_prefix if root_prefix else "(root ZIP, tanpa wrapper)"

    console.print(f"\n[cyan]Root project terdeteksi otomatis:[/cyan] {label}")
    _render_zip_structure_tree(zip_path, wrapper_chain, ambiguous_children=None)
    if wrapper_chain:
        console.print(f"[dim](Folder wrapper yang akan dihapus saat ekstrak: {'/'.join(wrapper_chain)}/)[/dim]")

    setuju = questionary.confirm("Gunakan deteksi otomatis ini sebagai Root Project?", default=True).ask()
    if setuju is None:
        return None
    if setuju:
        return root_prefix

    # Override manual - kumpulkan semua path folder di dalam ZIP (dibatasi
    # kedalaman 3 biar daftar pilihan gak kepanjangan/kepenuhan node_modules
    # dkk), user pilih sendiri mana yang jadi root, atau pilih "0 wrapper".
    with zipfile.ZipFile(zip_path, "r") as z:
        namelist = z.namelist()
    all_dirs = set()
    for name in namelist:
        parts = [p for p in name.split("/") if p]
        for i in range(1, min(len(parts), 4)):
            all_dirs.add("/".join(parts[:i]))

    choices = ["(0 Wrapper - gunakan root ZIP apa adanya)"] + sorted(all_dirs) + ["Batal"]
    pilihan = questionary.select("Pilih folder mana yang jadi Root Project:", choices=choices).ask()
    if not pilihan or pilihan == "Batal":
        return None
    if pilihan.startswith("(0 Wrapper"):
        return ""
    return pilihan + "/"


def upload_zip_extract() -> None:
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=False, need_clean=True, label="Upload ZIP"):
        return

    zip_path = _pick_source_file("file ZIP", want_ext=".zip")
    if not zip_path:
        return

    try:
        with zipfile.ZipFile(zip_path, "r"):
            pass
    except zipfile.BadZipFile:
        console.print("[red]File ZIP rusak atau tidak valid.[/red]")
        log_error("ZIP rusak saat analisis", raw_detail=zip_path)
        return

    # --- 1. Penentuan Root Proyek & Wrapper ---
    root_prefix = _detect_zip_root(zip_path)

    if root_prefix.startswith("AMBIGU"):
        ambiguous_prefix = root_prefix.split(":", 1)[1] if ":" in root_prefix else ""
        wrapper_chain = [c for c in ambiguous_prefix.split("/") if c]

        # Hanya kandidat yang PERSIS satu level di bawah ambiguous_prefix
        # (bukan seluruh folder di dalam ZIP, biar gak riuh dengan folder
        # nested yang gak relevan seperti node_modules/dsb).
        dirs = set()
        plen = len(ambiguous_prefix)
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                if ambiguous_prefix and not name.startswith(ambiguous_prefix):
                    continue
                rel = name[plen:]
                if not rel:
                    continue
                first = rel.split('/')[0]
                if first:
                    dirs.add(first)

        # 2. Tampilkan dulu STRUKTUR ZIP, baru pilihan root (bukan langsung
        #    daftar folder telanjang).
        console.print("\n[yellow]⚠ Root proyek tidak dapat ditentukan secara otomatis.[/yellow]")
        _render_zip_structure_tree(zip_path, wrapper_chain, ambiguous_children=dirs)
        console.print()

        label_root = ambiguous_prefix if ambiguous_prefix else "(root ZIP)"
        choices = sorted(dirs) + [f"(0 Wrapper - jadikan {label_root} sebagai root apa adanya)", "Batal"]
        pilihan = questionary.select(
            "Pilih folder mana yang menjadi Root Project:",
            choices=choices
        ).ask()

        if not pilihan or pilihan == "Batal":
            return
        if pilihan.startswith("(0 Wrapper"):
            root_prefix = ambiguous_prefix
        else:
            root_prefix = ambiguous_prefix + pilihan + "/"
    else:
        # Deteksi 'yakin' (bukan AMBIGU) - BUGFIX: dulu langsung dipakai
        # tanpa user sempat lihat/koreksi. Sekarang selalu dikonfirmasi
        # dulu, dengan opsi override manual kalau heuristiknya salah nebak
        # (mis. folder wrapper kebetulan namanya 'app'/'src' dst, jadi
        # otomatis dianggap bukan wrapper padahal di kasus ini memang wrapper).
        confirmed = _confirm_or_override_root(zip_path, root_prefix)
        if confirmed is None:
            return
        root_prefix = confirmed

    wrapper_chain = [c for c in root_prefix.split("/") if c] if root_prefix else []

    # --- 2. Ringkasan ZIP (tree sudah ditampilkan di langkah konfirmasi
    # root di atas - baik lewat jalur AMBIGU maupun _confirm_or_override_root,
    # jadi di sini cukup statistiknya saja, tidak perlu render tree lagi). ---
    console.print()
    _print_zip_stats(zip_path, wrapper_chain)

    # --- 3. Upload Preview (struktur akhir sesuai root yang dipilih) ---
    console.print()
    _render_upload_preview(zip_path, root_prefix)
    console.print()

    dest_dir = pick_folder_in_repo(repo, "Pilih folder tujuan ekstrak di dalam repository:")
    if dest_dir is None:
        return

    # BUGFIX TINGGI: baca .gitignore repo (kalau ada) sebagai filter tambahan,
    # digabung dengan daftar exclude bawaan (node_modules, .env, dst) -
    # sebelumnya tidak ada filter apa pun di jalur Upload, jadi folder besar/
    # sensitif bisa ikut terupload tanpa sadar.
    gitignore_patterns = _read_gitignore_patterns(repo)
    gitignore_found = os.path.isfile(os.path.join(repo, ".gitignore"))

    # Menghitung diff dengan root yang sudah pasti
    with spinner("Menghitung perubahan..."):
        tambah, update, sama, delete, dilewati, target_map = _compute_zip_diff(
            zip_path, dest_dir, root_prefix, gitignore_patterns
        )
        total_entries = len(target_map) # Hanya hitung file yang valid diekstrak

    ok_b, branch_now, _e = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    branch_now = branch_now if ok_b else "-"

    if not _confirm_zip_changes(repo, branch_now, total_entries, root_prefix, tambah, update, sama, delete,
                                 dilewati=dilewati, gitignore_found=gitignore_found):
        console.print("[yellow]Dibatalkan.[/yellow]")
        return

    timpa = questionary.confirm(
        "Timpa (overwrite) file yang sudah ada di repository jika bentrok?", default=True
    ).ask()

    config = load_config()
    if config.get("backup_otomatis", True) and timpa:
        console.print("[cyan]Membuat backup otomatis sebelum overwrite...[/cyan]")
        backup_module.buat_backup_zip(repo, silent_label="auto-before-upload")

    files_before = count_files_in_dir(repo)

    try:
        from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn
        with Progress(
            TextColumn("[cyan]Mengekstrak...[/cyan]"), BarColumn(), TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("extract", total=total_entries)
            with zipfile.ZipFile(zip_path, "r") as z:
                for member in z.infolist():
                    if member.is_dir():
                        continue
                    
                    rel = _zip_target_rel(member.filename, root_prefix)
                    if not rel:
                        continue

                    # Filter node_modules/.env/dst + pola .gitignore -
                    # konsisten dengan _compute_zip_diff() di atas supaya
                    # angka preview cocok dengan yang benar-benar ditulis.
                    if _should_exclude_upload_entry(rel, gitignore_patterns):
                        continue

                    # SECURITY: Zip Slip protection - entry yang mencoba
                    # keluar dari dest_dir ditolak dan di-skip, bukan ditulis.
                    target_path = safe_zip_member_path(dest_dir, rel)
                    if target_path is None:
                        log_error("Zip Slip diblokir", raw_detail=f"entry ditolak: {member.filename}")
                        progress.advance(task)
                        continue

                    if os.path.exists(target_path) and not timpa:
                        progress.advance(task)
                        continue
                        
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with z.open(member) as src, open(target_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    progress.advance(task)
    except zipfile.BadZipFile as e:
        console.print("[red]Gagal mengekstrak: file ZIP rusak.[/red]")
        log_error("Gagal ekstrak ZIP", e, raw_detail=zip_path)
        return
    except OSError as e:
        console.print(f"[red]Gagal menulis file ke repository: {e}[/red]")
        log_error("Gagal menulis file hasil ekstrak ZIP", e)
        return

    files_after = count_files_in_dir(repo)
    _tampilkan_ringkasan_upload(
        repo, files_before, files_after, extra_label="Upload ZIP (Extract)",
        override_counts=(tambah, update, 0),
    )
    log_activity("Upload ZIP (Extract) berhasil")


def upload_zip_no_extract() -> None:
    """PRIORITAS 3 #10 - salin file ZIP apa adanya ke repository, tanpa ekstrak."""
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=False, need_clean=True, label="Upload ZIP (No Extract)"):
        return

    zip_path = _pick_source_file("file ZIP", want_ext=".zip")
    if not zip_path:
        return

    dest_dir = pick_folder_in_repo(repo, "Pilih folder tujuan (ZIP disalin apa adanya):")
    if dest_dir is None:
        return

    files_before = count_files_in_dir(repo)
    try:
        os.makedirs(dest_dir, exist_ok=True)
        target_path = os.path.join(dest_dir, os.path.basename(zip_path))
        shutil.copy2(zip_path, target_path)
    except OSError as e:
        console.print(f"[red]Gagal menyalin ZIP: {e}[/red]")
        log_error("Gagal upload ZIP (no extract)", e)
        return

    files_after = count_files_in_dir(repo)
    console.print(f"[green]ZIP berhasil disalin ke {target_path} (tanpa ekstrak).[/green]")
    _tampilkan_ringkasan_upload(repo, files_before, files_after, extra_label="Upload ZIP (No Extract)")
    log_activity("Upload ZIP (No Extract) berhasil")


# ---------------------------------------------------------------------------
# Upload File / Folder
# ---------------------------------------------------------------------------

def upload_file() -> None:
    """PRIORITAS 3 #8 - Upload satu file lewat picker, bukan ketik path manual."""
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=False, need_clean=True, label="Upload File"):
        return

    path = _pick_source_file("file")
    if not path:
        return

    dest_dir = pick_folder_in_repo(repo, "Pilih folder tujuan di dalam repository:")
    if dest_dir is None:
        return

    try:
        os.makedirs(dest_dir, exist_ok=True)
        tujuan_path = os.path.join(dest_dir, os.path.basename(path))
        shutil.copy2(path, tujuan_path)
    except OSError as e:
        console.print(f"[red]Gagal meng-copy file: {e}[/red]")
        log_error("Gagal upload file", e)
        return
    console.print(f"[green]✓ Upload Berhasil[/green]\n\n"
                  f"Repository : {os.path.basename(repo)}\n"
                  f"File       : {os.path.basename(path)}\n"
                  f"Tujuan     : {tujuan_path}\n")
    console.print("[dim]Catatan: file belum di-commit. Gunakan menu 'Git Add' dan 'Commit' selanjutnya.[/dim]")
    log_activity("Upload File berhasil")


def upload_folder() -> None:
    """Upload folder tertentu ke repository (copy, tidak commit otomatis)."""
    repo = _get_active_repo()
    if not repo:
        return
    if not preflight.preflight(repo, need_remote=False, need_clean=True, label="Upload Folder"):
        return

    path = _pick_source_folder("folder")
    if not path:
        return

    dest_parent = pick_folder_in_repo(repo, "Pilih folder tujuan di dalam repository:")
    if dest_parent is None:
        return

    nama_folder = os.path.basename(path.rstrip("/"))
    tujuan_path = os.path.join(dest_parent, nama_folder)

    # BUGFIX SEDANG: sebelumnya copytree(..., dirs_exist_ok=True) langsung
    # jalan tanpa konfirmasi eksplisit kalau folder tujuan sudah berisi -
    # beda perlakuan dengan Upload ZIP yang selalu tanya "Timpa?" dulu.
    # File lama di folder tujuan bisa ketimpa diam-diam tanpa opsi batal.
    if os.path.isdir(tujuan_path) and os.listdir(tujuan_path):
        timpa = questionary.confirm(
            f"Folder tujuan '{tujuan_path}' sudah berisi file. File yang namanya sama akan "
            f"DITIMPA (file lain yang tidak ada di sumber TIDAK ikut dihapus). Lanjutkan?",
            default=False,
        ).ask()
        if not timpa:
            console.print("[yellow]Dibatalkan.[/yellow]")
            return

    # Filter node_modules/.env/dst + pola .gitignore repo, sama seperti
    # Upload ZIP - sebelumnya tidak ada filter apa pun di jalur ini.
    gitignore_patterns = _read_gitignore_patterns(repo)

    def _ignore(current_dir: str, names: list) -> set:
        rel_base = os.path.relpath(current_dir, path)
        skip = set()
        for name in names:
            rel = name if rel_base in ("", ".") else f"{rel_base}/{name}"
            rel = rel.replace(os.sep, "/")
            if _should_exclude_upload_entry(rel, gitignore_patterns):
                skip.add(name)
        return skip

    try:
        shutil.copytree(path, tujuan_path, dirs_exist_ok=True, ignore=_ignore)
    except OSError as e:
        console.print(f"[red]Gagal meng-copy folder: {e}[/red]")
        log_error("Gagal upload folder", e)
        return
    console.print(f"[green]✓ Upload Berhasil[/green]\n\nFolder berhasil di-copy ke {tujuan_path}\n")
    console.print("[dim]Catatan: folder belum di-commit. Gunakan menu 'Git Add' dan 'Commit' selanjutnya.[/dim]")
    log_activity("Upload Folder berhasil")


def _tampilkan_ringkasan_upload(repo: str, files_before: int, files_after: int,
                                 extra_label: str = "Upload",
                                 override_counts: Optional[Tuple[int, int, int]] = None) -> None:
    """override_counts, kalau diisi (added, modified, deleted), dipakai
    langsung tanpa hitung ulang dari 'git status' - dipakai Upload ZIP
    (Extract) supaya angkanya konsisten dengan tabel Preview Perubahan ZIP,
    dan gak ketimpa status git lain yang gak terkait aksi ini."""
    ok, branch, _err = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    branch = branch if ok else "-"

    if override_counts is not None:
        added, modified, deleted = override_counts
    else:
        ok, status_out, _err = run_git(["status", "--porcelain"], cwd=repo)
        added = modified = deleted = 0
        if ok:
            for line in status_out.splitlines():
                code = line[:2]
                if "A" in code or "?" in code:
                    added += 1
                elif "M" in code:
                    modified += 1
                elif "D" in code:
                    deleted += 1

    table = Table(title=f"Ringkasan Setelah {extra_label}", header_style="bold cyan")
    table.add_column("Info")
    table.add_column("Nilai")
    table.add_row("Repository", os.path.basename(repo))
    table.add_row("Branch", branch)
    table.add_row("Jumlah file baru", str(added))
    table.add_row("Jumlah file berubah", str(modified))
    table.add_row("Jumlah file dihapus", str(deleted))
    table.add_row("Total file sebelum", str(files_before))
    table.add_row("Total file sesudah", str(files_after))
    console.print(table)
    console.print("[bold]Langkah berikutnya:[/bold] gunakan menu 'Git Add' lalu 'Commit' untuk menyimpan perubahan.")

    # PRIORITAS 1 #3: refresh info repo (branch/remote/status) abis upload
    run_git(["status", "--short"], cwd=repo)
    run_git(["branch", "-vv"], cwd=repo)
    run_git(["remote", "-v"], cwd=repo)


def show_help() -> None:
    console.print(
        "\n[bold cyan]Bantuan - Upload[/bold cyan]\n"
        "- Upload File: menyalin satu file ke repository lewat picker (Downloads/Home/Browse/Manual).\n"
        "- Upload Folder: menyalin satu folder utuh ke repository.\n"
        "- Upload ZIP (Extract): mengekstrak isi ZIP ke repository, dengan\n"
        "  deteksi cerdas folder pembungkus dan preview perubahan (Tambah/Update/Delete).\n"
        "- Upload ZIP (No Extract): menyalin file ZIP apa adanya, tanpa dibongkar.\n"
    )
    questionary.text("Tekan Enter untuk kembali...").ask()


def menu() -> None:
    while True:
        console.rule("[bold cyan]Upload")
        choice = questionary.select(
            "Pilih aksi:",
            choices=[
                "Upload File",
                "Upload Folder",
                "Upload ZIP (Extract)",
                "Upload ZIP (No Extract)",
                "? Help",
                "Kembali",
            ],
        ).ask()
        if choice is None or choice == "Kembali":
            return
        try:
            {
                "Upload File": upload_file,
                "Upload Folder": upload_folder,
                "Upload ZIP (Extract)": upload_zip_extract,
                "Upload ZIP (No Extract)": upload_zip_no_extract,
                "? Help": show_help,
            }[choice]()
        except Exception as e:  # noqa: BLE001
            console.print("[red]Terjadi kesalahan tak terduga. Detail sudah dicatat ke log.[/red]")
            log_error("Exception di menu Upload", e)
