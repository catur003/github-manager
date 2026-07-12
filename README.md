# GitHub Manager Termux v1.0

Aplikasi CLI (Command Line Interface) berbasis Python 3 untuk mengelola
Git & GitHub lewat menu interaktif — cocok untuk pemula yang belum hafal
perintah Git. Dibuat khusus agar nyaman dipakai di **Termux Android**
(tidak butuh root, tidak ada GUI).

## Fitur Utama

- Dashboard ringkasan repository saat aplikasi dibuka
- Kelola Repository (pilih, cari otomatis, clone, tambah, ganti)
- Kelola Branch (lihat, checkout, buat, rename, delete)
- Upload ZIP / File / Folder ke repository, lengkap dengan preview isi ZIP
  dan backup otomatis sebelum overwrite
- Git Add, Commit (termasuk amend & riwayat), Push (dengan proteksi Force
  Push), Pull/Fetch, Merge lokal dengan deteksi conflict
- Backup & Restore repository dalam bentuk ZIP
- Menu "Belajar Git" — penjelasan konsep Git dalam bahasa Indonesia sederhana
- Log aktivitas & log error terpisah, tanpa traceback yang membingungkan
  ditampilkan ke pengguna

## Cara Install

1. Pastikan Termux sudah terpasang dari F-Droid (disarankan, bukan Play Store).
2. Download / clone folder project ini ke penyimpanan Termux.
3. Beri izin eksekusi dan jalankan installer:

   ```bash
   cd github-manager
   chmod +x install.sh
   ./install.sh
   ```

   Installer akan otomatis memasang `python`, `git`, `unzip`, `zip`,
   dependency Python, serta membuat command `github-manager` yang bisa
   dipanggil dari folder mana saja.

## Cara Menjalankan

Setelah instalasi selesai, cukup jalankan:

```bash
github-manager
```

Atau, tanpa install command, jalankan langsung dengan:

```bash
python github-manager.py
```

## Dependency

Dependency dijaga seminimal mungkin:

- `rich` — tampilan terminal yang rapi (tabel, warna, panel)
- `colorama` — kompatibilitas warna terminal
- `questionary` — menu interaktif (pilih, teks, konfirmasi)

Sisanya menggunakan library bawaan Python (`subprocess`, `zipfile`,
`shutil`, `json`, `pathlib`, dll).

## Struktur Project

```
github-manager/
├── install.sh
├── github-manager.py
├── requirements.txt
├── README.md
├── config/          # konfigurasi aplikasi (config.json)
├── logs/            # activity.log & error.log
├── backup/          # hasil backup ZIP repository
└── modules/
    ├── dashboard.py
    ├── repository.py
    ├── branch.py
    ├── upload.py
    ├── gitadd.py
    ├── commit.py
    ├── push.py
    ├── pull.py
    ├── merge.py
    ├── backup.py
    ├── settings.py
    ├── help.py
    ├── logger.py
    └── utils.py
```

## Cara Update

Jika project diambil dari repository Git:

```bash
cd github-manager
git pull
pip install -r requirements.txt --upgrade
```

Jika hanya menyalin file secara manual, cukup timpa file yang berubah,
lalu jalankan ulang `pip install -r requirements.txt` untuk memastikan
dependency tetap sesuai.

## Contoh Penggunaan Singkat

1. Buka aplikasi dengan mengetik `github-manager`.
2. Pilih menu **1. Repository** → **Clone Repository**, masukkan URL repo.
3. Setelah repository aktif, edit/upload file lewat menu **3. Upload**.
4. Gunakan **4. Git Add** untuk staging, lalu **5. Commit** untuk menyimpan
   perubahan dengan pesan commit.
5. Gunakan **6. Push** untuk mengirim perubahan ke GitHub.
6. Bila baru belajar Git, buka menu **11. Belajar Git** untuk penjelasan
   istilah-istilah dasar.

## Catatan Keamanan

- Semua aksi berbahaya (Delete Branch, Overwrite ZIP, Force Push, Restore
  Backup, Hapus Backup) selalu meminta konfirmasi.
- Force Push mengharuskan pengguna mengetik `YA` secara eksplisit.
- Traceback Python tidak pernah ditampilkan ke pengguna; semua tersimpan
  di `logs/error.log` untuk keperluan debugging.

---

Dikembangkan agar mudah diperluas ke v1.1, v2, dan seterusnya — setiap
fitur dipisah rapi per module agar penambahan fitur baru tidak
mengganggu fitur yang sudah ada.
