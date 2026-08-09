# Changelog GitHub Manager

## v1.5.1 (Bugfix: Upload ZIP - wrapper detection tanpa opsi koreksi)

### Diperbaiki (bug nyata, dilaporkan user)
- **Upload ZIP: deteksi root project/wrapper yang "yakin" (bukan AMBIGU)
  langsung final dipakai, TANPA user sempat lihat/koreksi.** Kasus
  konkret yang salah: `_detect_zip_root()` punya daftar nama folder umum
  (`app`, `src`, `pages`, dst di `_COMMON_PROJECT_DIRS`) yang otomatis
  DIANGGAP BUKAN wrapper karena lazimnya itu struktur project asli (mis.
  Next.js App Router). Tapi kalau folder wrapper ZIP-nya KEBETULAN
  namanya sama (mis. `app/myrealproject/package.json` di mana `app/`
  cuma wrapper biasa, bukan Next.js), heuristik ini salah nebak dan
  sebelumnya user gak punya cara membetulkannya - `app/` ikut terekstrak
  sebagai bagian dari repo, bukan cuma `myrealproject/`nya.
- **Fix**: tambah `_confirm_or_override_root()` - SELALU tampilkan hasil
  deteksi otomatis + tawarkan override manual (pilih folder mana pun di
  dalam ZIP, sampai kedalaman 3 level, sebagai root), bukan cuma untuk
  kasus yang sudah terdeteksi "AMBIGU" secara struktural seperti
  sebelumnya. Default-nya tetap "pakai deteksi otomatis" (Enter langsung
  lanjut) - jadi ZIP yang deteksinya sudah benar tidak nambah friksi
  sama sekali, cuma nambah 1 konfirmasi.
- Diuji dengan ZIP asli yang reproduksi persis kasusnya: `app/myrealproject/
  package.json` di mana `app/` adalah wrapper murni (bukan Next.js) -
  dikonfirmasi deteksi otomatis salah nebak `''` (0 wrapper), lalu
  dikonfirmasi opsi override manual menyediakan `app/myrealproject`
  (root yang benar) sebagai pilihan. Juga diuji ZIP tanpa wrapper sama
  sekali untuk pastikan tidak ada regresi pada kasus normal.
- Render tree ZIP Analyzer yang sebelumnya dobel-tampil (sekali di
  langkah konfirmasi baru, sekali lagi setelahnya) dirapikan jadi
  sekali saja.

## v1.5.0 (Fitur: Lihat Diff, Git Status per-file, Bugfix parsing)

### Ditambahkan
- **Lihat Diff (menu Git Add)** - fitur baru, belum pernah ada sebelumnya.
  Nunjukin isi perubahan per baris dengan warna jelas: hijau = ditambah,
  merah = dihapus, cyan = header hunk (`@@...@@`). Bisa pilih diff dari
  working tree (belum di-stage) atau staging area (sudah di-stage), per
  file atau semua sekaligus. Semua baris di-`escape()` sebelum di-print
  lewat `rich` - isi kode asli sering mengandung karakter `[` `]` (array
  JS, generic TypeScript, dst) yang kalau tidak di-escape bisa salah
  ditafsir sebagai style tag rich (bug class yang sama seperti kasus
  literal `[OK]` yang pernah ditemukan sebelumnya - diverifikasi lewat
  diff sungguhan yang mengandung `[1, 2, 3]` dan `[VIP]`).
- **Git Status (menu utama) sekarang nampilin NAMA FILE per kategori**,
  bukan cuma jumlah - dikelompokkan per status (Modified/Added/Deleted/
  Untracked) dengan warna berbeda.

### Diperbaiki (bug nyata, bukan yang direncanakan)
- **`run_git()` di `utils.py` motong 1 karakter pertama nama file** pada
  entri PERTAMA dari `git status --porcelain` kapan pun kode statusnya
  diawali spasi (mis. ` M`, ` D` untuk perubahan belum di-stage) - `a.txt`
  terbaca jadi `.txt`. Akar masalahnya: `run_git()` pakai `.strip()` pada
  seluruh stdout gabungan, yang menghapus spasi bermakna di awal baris
  pertama porcelain output. Fix: ganti ke `.rstrip()` (cuma buang
  whitespace di akhir), diverifikasi tidak merusak 140+ caller lain (yang
  sudah re-`.strip()` hasilnya sendiri tetap sama perilakunya; yang
  parsing posisional seperti `git branch --list` sudah `.strip()` per
  baris, bukan bergantung ke .strip() global). Ini kemungkinan alasan
  fitur Git Status sebelumnya sengaja cuma nampilin ANGKA, bukan nama
  file - begitu nama file ditampilkan (perubahan di atas), bug ini baru
  kelihatan nyata.
- Diuji pakai repo git asli (bukan cuma unit test): `_status_files()`
  sekarang mengembalikan `a.txt` utuh, bukan `.txt`.

## v1.4.0 (Fitur: Buat/Hapus Repository & Ubah Visibilitas di GitHub)

### Ditambahkan
- **Buat Repository Baru (GitHub)** di menu Repository: setara tombol
  "New repository" di web GitHub - nama, deskripsi, Public/Private,
  centang "Add README.md" otomatis, pilih template `.gitignore` (Node,
  Python, Java, dst), lalu opsional langsung di-clone ke perangkat &
  dijadikan repository aktif. Pakai `gh repo create`, butuh GitHub CLI
  sudah login (dicek lewat `gh_ready()`, sama seperti fitur Pull Request).
- **Hapus Repository dari GitHub** (bukan cuma dari daftar lokal) - di
  sub-menu aksi per-repository. Destruktif & gak bisa dibatalkan di sisi
  GitHub, jadi wajib ketik ulang nama repo persis buat konfirmasi (pola
  sama seperti Force Push / Hapus Semua Stash). Folder lokal di disk
  TIDAK ikut terhapus.
- **Ubah Visibilitas Repository** (Public <-> Private) - di sub-menu aksi
  per-repository. Nunjukin visibilitas saat ini dulu, kasih peringatan
  konsekuensi (Public: kode & riwayat jadi terlihat publik; Private:
  kolaborator yang belum ditambahkan manual bisa kehilangan akses)
  sebelum konfirmasi.
- **`extract_owner_repo()` (fungsi murni baru di `utils.py`)**: dari URL
  remote (https/ssh/scp-like), ambil `(owner, repo)` - dipakai fitur
  Hapus & Ubah Visibilitas supaya otomatis tahu nama repo GitHub dari
  remote origin repo lokal, user gak perlu ketik ulang manual. Diuji unit
  test (7 kasus: https, tanpa .git, scp-like, ssh://, host bukan GitHub,
  string kosong, input sembarangan) + diuji fungsional pakai repo git
  asli dengan remote sungguhan.

### Perubahan
- `_gh_ready()` yang tadinya cuma ada lokal di `merge.py` dipindah jadi
  `gh_ready()` shared di `settings.py`, dipakai bareng oleh `merge.py`
  (fitur PR) dan `repository.py` (fitur GitHub baru di atas) - satu
  sumber kebenaran, gak diduplikasi ulang.
- Folder tujuan clone (dulu logic-nya nyatu di `clone_repository()`)
  diextract jadi `_pick_clone_destination()` + `_do_clone()` yang dipakai
  bareng oleh `clone_repository()` dan `create_repository()`.
- Materi baru di menu "Belajar Git": Visibilitas Repository.

## v1.3.0 (Fitur: Stash, Rebase, Cherry-pick)

### Ditambahkan
- **Menu Stash (baru, menu utama #9)**: Simpan Stash (pesan opsional,
  opsi sertakan file untracked), Lihat Daftar Stash, Terapkan Stash
  (apply, tidak menghapus stash), Pop Stash, Lihat Isi Stash (diff),
  Stash ke Branch Baru (`stash branch`), Hapus Stash (per-item), Hapus
  Semua Stash (destruktif, wajib ketik `YA` seperti Force Push).
  Konflik saat apply/pop ditangani eksplisit: stash TIDAK hilang kalau
  gagal, user diarahkan menyelesaikan manual.
- **Menu Rebase (baru, menu utama #10)**: Rebase Branch Aktif (pilih
  target, replay commit di atasnya), Update dari Upstream (Rebase) -
  alternatif Pull yang menghasilkan riwayat lurus tanpa merge commit,
  Lanjutkan/Lewati/Batalkan Rebase saat conflict, Status Rebase. Ada
  guard supaya tidak bisa mulai rebase baru kalau rebase sebelumnya
  belum selesai (deteksi lewat `.git/rebase-merge` atau
  `.git/rebase-apply`, fungsi `preflight.is_rebase_in_progress()`).
- **Cherry-pick Commit (menu Merge)**: ambil satu commit tertentu dari
  branch lain dan terapkan ke branch aktif tanpa menggabungkan seluruh
  branch. Termasuk "Lanjutkan Cherry-pick" untuk melanjutkan setelah
  conflict diselesaikan manual, plus opsi Abort/Skip langsung saat
  conflict terjadi.
- **Dashboard**: baris baru "Stash Tersimpan" (jumlah stash aktif) dan
  peringatan "Status Rebase" kalau ada rebase yang belum selesai -
  supaya user langsung sadar dari layar utama, bukan baru ketahuan
  kalau kebetulan buka menu Stash/Rebase.
- Materi baru di menu "Belajar Git": Stash, Rebase, Cherry-pick.
- `tests/test_stash.py`: unit test untuk parser murni `_parse_stash_entry()`.

### Ditambahkan (lanjutan)
- **Distribusi via pip**: `pyproject.toml` (PEP 621, build-backend
  setuptools) dengan `[project.scripts]` -> `github-manager =
  modules.cli:main`. Ini mekanisme RESMI pip buat bikin CLI command -
  beda total dari "postinstall hook" ala npm: pip generate script kecil
  langsung `import` fungsi `main()` Python (bukan subprocess/shell),
  shebang-nya otomatis dirapikan ke python venv yang benar. **pip TIDAK
  PUNYA hook setelah-install sama sekali** (khususnya buat install dari
  wheel, cara pip biasa fetch dari PyPI) - jadi gak ada versi
  "postinstall.py" di sini, splash banner (lihat poin berikutnya) yang
  jadi jaring pengamannya.
- **Refactor `modules/cli.py`**: logic menu utama (dulu di
  `github-manager.py`) dipindah ke sini supaya jadi SATU sumber
  kebenaran yang dipakai baik oleh `python github-manager.py` (Termux/git
  clone, sekarang cuma shim tipis) maupun entry point pip - gak ada
  logic yang perlu disinkronkan manual di dua tempat. Diuji ulang
  end-to-end: build wheel lokal, install ke venv bersih, command
  `github-manager` jalan dan resolve `modules.cli:main` dengan benar.

### Ditambahkan (lanjutan)
- **Distribusi via npm**: `package.json` + `bin/github-manager` (shim yang
  exec Python) + `scripts/postinstall.js`, jadi bisa `npm install -g
  github-manager`. `.npmignore` ditambahkan supaya `__pycache__`/file
  runtime gak ikut ke-publish.
- **Splash banner sekali di run pertama (`modules/banner.py`)**: PENTING
  - ini nutupin celah nyata yang saya temukan pas ngetes: npm (v7+)
  **menyembunyikan output `postinstall` secara default** kecuali user
  pakai `--foreground-scripts` (dites langsung: `npm install -g` biasa =
  banner TIDAK muncul, cuma `--foreground-scripts` yang nampilinnya).
  Karena hampir gak ada user yang pakai flag itu, banner scripts/postinstall.js
  gak bisa diandalkan sendirian. Solusinya: `github-manager` sekarang
  nampilin banner yang sama otomatis SEKALI di run pertama (state
  `config['banner_shown']`), independen dari perilaku silent npm itu.
  Juga bisa dipanggil manual: `github-manager --version` / `--help`.
- **Bugfix kecil di banner**: teks `[OK]` yang direncanakan buat versi
  Python awalnya bakal ditafsir `rich` sebagai style-tag (bukan teks
  biasa) dan berisiko error render - diganti ke `✓` yang sudah jadi
  konvensi konsisten di semua modul lain, ketahuan & diperbaiki sebelum
  sempat dipakai.

### Ditambahkan (lanjutan)
- **Banner ASCII di akhir `install.sh`, gaya "poster"**: judul "GITHUB"
  (putih) terpisah dari blok huruf besar "MANAGER" (hijau), tagline,
  kotak info Version/Author + status "Installation completed", dan
  command hint `[ $ github-manager ]` - meniru struktur referensi desain
  yang diberikan user, dalam bentuk ASCII murni (kompatibel semua
  terminal Termux, tidak butuh font/emoji khusus).

### Perubahan
- Nomor menu utama bergeser karena ada 2 menu baru: Backup sekarang
  #11 (dulu #9), Git Status #12 (dulu #10), Belajar Git #13 (dulu
  #11), Pengaturan #14, Log Aktivitas #15, Cek Update #16, Log Debug
  #17 (mengikuti pergeseran yang sama).

## v1.2.4 (Security & Bugfix pass)

### Fixed - Security
- **Zip Slip / Path Traversal saat Upload ZIP (Extract)**: entry ZIP dengan
  path seperti `../../.ssh/authorized_keys` bisa menulis file di LUAR folder
  repository (mis. menimpa file sistem/config di HP). Sekarang setiap entry
  divalidasi lewat `safe_zip_member_path()` sebelum ditulis; entry mencurigakan
  ditolak & dicatat ke log.
- **Zip Slip saat Restore Backup**: `restore_zip()` sebelumnya pakai
  `zipfile.extractall()` mentah tanpa validasi path. Sekarang ekstraksi manual
  per-entry dengan validasi yang sama seperti di atas.
- **Token/PAT bocor plaintext ke log**: kalau clone pakai URL berkredensial
  (`https://user:TOKEN@github.com/...`), token sebelumnya ke-tulis apa adanya
  ke `logs/debug.log` (tiap command git) dan `logs/activity.log` (pesan
  clone). Ditambahkan `redact_secrets()` yang otomatis mask token jadi `***`
  sebelum ditulis ke log atau ditampilkan di Dashboard (remote URL).
- **Command Injection di "Buka Lokasi" (Repository Manager)**: path folder
  di-interpolate langsung ke `os.system(f"termux-open '{path}'")` - nama
  folder dengan karakter khusus (`'`, `;`) bisa keluar dari konteks argumen
  dan mengeksekusi command lain. Diganti ke `subprocess.run(["termux-open",
  path])` (list args, tidak lewat shell).

### Fixed - Bugs
- **"Sync Branch" selalu crash (`NameError`)**: fungsi `sync_branch()` di
  `branch.py` memakai `spinner()` tapi modulnya tidak pernah di-import.
  Fitur ini 100% gagal setiap kali dipanggil sebelum fix ini.
- **Push/Pull/Merge conflict = jalan buntu**: sebelumnya kalau kena conflict
  atau push rejected, user cuma dikasih pesan error lalu mentok - tidak ada
  opsi lanjutan dari dalam aplikasi. Sekarang:
  - Pull yang gagal karena working tree kotor: ditawarkan Stash & Pull
    otomatis (dengan auto stash-pop setelahnya).
  - Pull yang gagal karena conflict: ditawarkan Abort (`merge --abort`) atau
    lanjut manual.
  - Push yang ditolak (rejected): ditawarkan langsung Pull dari situ juga.
  - Merge conflict: ditawarkan Abort merge langsung, bukan cuma disuruh
    "selesaikan manual".
- **`count_files_in_dir()` salah hitung file hidden**: fungsi ini ikut
  menghitung file/folder yang diawali titik (`.env`, dll), tidak konsisten
  dengan `list_top_level_dirs()`/`find_git_repos()` yang mengecualikannya.
  Menyebabkan angka "X file berubah" di ringkasan Upload bisa salah. Sudah
  konsisten sekarang - `tests/test_utils.py` yang sebelumnya FAIL di test
  ini sekarang PASS.
- **`install.sh` tidak membuat command `github-manager`**: README menjanjikan
  installer membuat command `github-manager` yang bisa dipanggil dari folder
  mana saja, tapi installer sebelumnya tidak pernah melakukan itu - cuma
  `python github-manager.py` yang jalan. Ditambahkan step yang membuat
  wrapper script di `$PREFIX/bin/github-manager`.

### Testing
- Semua 18 file `.py` dicek `python3 -m py_compile` - tidak ada syntax error.
- `tests/test_utils.py` dijalankan dengan stub `rich`/`questionary` (sandbox
  tanpa akses internet buat install dependency asli) - 18/18 test PASS
  (1 test tadinya FAIL sebelum fix `count_files_in_dir`).
- Static scan custom (AST-based) ke semua fungsi untuk cari nama yang dipakai
  tapi tidak pernah di-import/didefinisikan (pola yang sama dengan bug
  `spinner`) - bersih, tidak ada kasus lain.
- `safe_zip_member_path()` dan `redact_secrets()` ditest manual dengan kasus
  path traversal (`../../etc/passwd`, absolute path) dan URL bertoken -
  semuanya berperilaku sesuai ekspektasi.
- `bash -n install.sh` - syntax valid.
- **Belum** dijalankan end-to-end di Termux asli (sandbox ini tidak punya
  akses internet untuk install `rich`/`questionary`/`colorama`, dan tidak
  ada real Git remote untuk test skenario network/conflict sungguhan) -
  mohon divalidasi manual di Termux sebelum dianggap final.

---

## v1.2.0


### Fixed
- **Bug Pull Request**: sebelumnya gagal membuat PR jika branch lokal
  sudah dihapus walau branch masih ada di GitHub, karena daftar branch
  cuma diambil dari `git branch --list` (lokal saja). Sekarang daftar
  source/target digabung dari lokal + remote, ada penanda "(hanya di
  GitHub)", dan ditambahkan opsi Fetch Branch di awal alur buat PR.

### Added
- **Clone Repository Wizard** (`Repository > Clone Repository`): validasi
  format URL/`owner-repo`, cek folder tujuan sudah ada, dan opsi
  Timpa/Pilih folder lain/Batal sebelum clone.
- **Compare Repository** (`Repository > Compare Repository`): bandingkan
  repository lokal vs GitHub - branch aktif, commit terbaru, jumlah file
  baru/berubah/hilang. Kalau beda, tawarkan Pull, Clone Ulang (dengan
  konfirmasi ketik ulang path supaya gak salah hapus folder), atau Batal.
- **Branch Synchronization** (`Branch > Sync Branch`): tabel branch lokal
  vs remote, ahead/behind per branch, branch yang cuma ada di lokal atau
  cuma di GitHub, plus aksi Fetch/Pull/Push/Hapus Branch Lokal/Hapus
  Branch Remote.
- **Preview ZIP diperkaya**: sekarang menampilkan Repository, Branch,
  Total File di ZIP, info folder pembungkus, dan analisis perubahan
  lengkap (Sama/Update/File Baru/Akan Dihapus), plus progress bar saat
  proses ekstraksi (bukan spinner statis).

## v1.1.1 (Bugfix pass setelah review)

### Fixed (bug kritis dari v1.1)
- **install.sh crash total**: fungsi dipanggil sebagai `install_if_missing` tapi
  didefinisikan sebagai `check_install` → installer selalu gagal di step
  dependency check. Fungsi sudah diganti nama jadi `install_if_missing`.
- **install.sh CRLF**: file tersimpan dengan line ending Windows (CRLF), bisa
  menyebabkan error `bad interpreter` di Termux/bash. Sudah dikonversi ke LF.
- **Repository Manager - "Hapus dari daftar" & "Buka lokasi"**: fungsinya
  sudah ada sejak v1.1 tapi tidak pernah dipanggil dari menu manapun. Sekarang
  memilih sebuah repository membuka sub-menu aksi (Gunakan / Buka Lokasi /
  Hapus dari Daftar).
- **Status Git palsu**: sebelumnya selalu menampilkan "Clean" tanpa
  benar-benar mengecek. Sekarang menjalankan `git status --porcelain` per
  repo dan menampilkan Clean/Modified/Hilang (kalau folder tidak ada lagi).
- **Favorite tidak naik ke atas**: sekarang daftar repository di-sort supaya
  yang favorit (⭐) selalu tampil paling atas, sesuai spec.
- **Recent Repository - jawab "Tidak" tidak ada efek**: sekarang kalau user
  memilih tidak memakai repo terakhir, `active_repository` dikosongkan dan
  Repository Manager langsung dibuka supaya user bisa pilih yang lain.
  Dashboard juga tidak lagi dirender dobel di awal.
- **Login Manager tidak fungsional**: menu "GitHub Account" sebelumnya cuma
  status statis + "Test Login" yang salah cek (pakai `git config user.name`,
  bukan status login GitHub). Sekarang:
  - Status login dicek lewat `gh auth status` (kalau `gh` terpasang).
  - "Login", "Logout", "Ganti Akun" sudah punya aksi nyata (lewat `gh auth
    login` / `gh auth logout`, dengan fallback instruksi manual kalau `gh`
    tidak ada).
  - "Ganti Akun" yang sebelumnya hilang dari sub-menu, sudah ditambahkan.
  - "Test Login" sekarang jalan di direktori repository aktif, bukan di
    direktori kerja aplikasi (sebelumnya hampir selalu gagal).
  - Menawarkan aktivasi `git config --global credential.helper store` kalau
    belum aktif.

### Testing
- Semua file dicek dengan `python3 -m py_compile` dan `ast.parse` — tidak ada
  syntax error.
- `bash -n install.sh` — syntax valid setelah perbaikan.
- Belum dijalankan end-to-end di Termux asli (butuh device Android) — mohon
  divalidasi manual di Termux sebelum dianggap final.

---

## v1.1 (Next Update)

### Added
- **Repository Manager**: Menu baru untuk daftar repo, scan otomatis, refresh, use, delete from list, open location, status Git.
- **Repository Search**: Search di Repository Manager.
- **Favorite Repository**: Tandai repo favorit (⭐), simpan di config.
- **Recent Repository**: Saat buka app, tanya gunakan repo terakhir.
- **Login Manager**: Menu GitHub Account di Pengaturan dengan status, login/logout, test.
- Installer improvements: Termux detect, install_if_missing, optional gh, pkg update, permissions, finish message.

### Changed
- Main menu tetap dimulai dari Repository Manager.
- Enhanced config dengan repositories list.
- Updated `_set_active_repository` untuk melacak repo.
- Refactored install.sh.

Semua fitur lama (branch, upload, commit, push, pull, merge, backup, dll) dipertahankan — tidak ada perubahan di modul-modul tersebut.
