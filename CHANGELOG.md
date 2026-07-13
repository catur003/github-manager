# Changelog GitHub Manager

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
