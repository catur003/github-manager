# GitHub Manager Termux v1.0

Aplikasi CLI (Command Line Interface) berbasis Python 3 untuk mengelola
Git & GitHub lewat menu interaktif — cocok untuk pemula yang belum hafal
perintah Git. Dibuat khusus agar nyaman dipakai di **Termux Android**
(tidak butuh root, tidak ada GUI).

## Fitur Utama

- Dashboard ringkasan repository saat aplikasi dibuka
- Kelola Repository (pilih, cari otomatis, clone, tambah, ganti)
- Buat Repository Baru di GitHub (nama, deskripsi, Public/Private, opsi
  README.md & template `.gitignore` otomatis, langsung clone)
- Hapus Repository dari GitHub & Ubah Visibilitas (Public/Private)
- Kelola Branch (lihat, checkout, buat, rename, delete)
- Upload ZIP / File / Folder ke repository, lengkap dengan preview isi ZIP
  dan backup otomatis sebelum overwrite
- Git Add, Commit (termasuk amend & riwayat), Push (dengan proteksi Force
  Push), Pull/Fetch, Merge lokal dengan deteksi conflict, Cherry-pick commit
- Stash (simpan, terapkan, pop, lihat isi, jadikan branch, hapus)
- Rebase (rebase ke branch lain, update dari upstream, lanjut/lewati/batalkan
  saat conflict)
- Backup & Restore repository dalam bentuk ZIP
- Menu "Belajar Git" — penjelasan konsep Git dalam bahasa Indonesia sederhana
- Log aktivitas & log error terpisah, tanpa traceback yang membingungkan
  ditampilkan ke pengguna

## Cara Install

### Opsi A: Lewat pip (`pip install`)

```bash
pip install github-manager
```

Ini beda mekanisme sama npm - pip **gak punya konsep "postinstall hook"**
resmi sama sekali. Yang terjadi:
- pip/setuptools bikinin script kecil bernama `github-manager` di folder
  `bin` environment Python kamu (venv atau `~/.local/bin`), isinya
  langsung `from modules.cli import main` - bukan lewat installer/shell
  script tambahan, jadi gak ada "kebaca apa enggak" karena memang gak ada
  hook yang dipanggil.
- Gak ada script lain yang otomatis jalan pas instalasi. Banner ASCII-nya
  (lihat bagian "Splash Banner" di bawah) tetap tampil - tapi itu bukan
  dari proses install, melainkan otomatis muncul pas kamu **pertama kali
  menjalankan** command `github-manager`.

Python 3.9+ tetap harus sudah terpasang duluan (`pkg install python` di
Termux / sudah bawaan di kebanyakan distro Linux); `pip install` gak bisa
masangin Python itu sendiri.

### Opsi B: Lewat npm (`npm install -g`)

```bash
npm install -g github-manager
```

Ini bakal:
- Pasang command `github-manager` ke PATH (lewat field `bin` di `package.json`).
- Jalanin `scripts/postinstall.js` otomatis, yang cek Python 3 & Git ada
  atau enggak, dan (kalau kelihatan) nampilin banner ASCII.

> **Catatan penting:** npm (v7 ke atas) itu **nyembunyiin output
> postinstall secara default** kecuali kamu pakai
> `npm install -g --foreground-scripts github-manager`. Jadi jangan kaget
> kalau abis `npm install -g` biasa cuma muncul `added 1 package in Xms`
> tanpa banner - itu normal, postinstall-nya tetap jalan (cuma diem).
> Banner-nya tetap dijamin muncul minimal sekali di run pertama
> `github-manager` (lihat bagian "Splash Banner" di bawah), gak
> bergantung sama perilaku silent npm itu.
>
> npm juga **cuma ngurus command & distribusi file**, bukan environment
> Python/Git. Python 3 dan Git tetap harus sudah terpasang duluan di
> sistem kamu (`pkg install python git` di Termux, atau
> `apt install python3 git` di Linux).

### Opsi C: Lewat Termux (clone + install.sh) - disarankan buat Termux

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

## Splash Banner

Banner ASCII "GITHUB MANAGER" tampil di dua tempat:
- Otomatis di akhir `install.sh` (Opsi C).
- Otomatis SEKALI di run pertama `github-manager` (dicatat lewat
  `config['banner_shown']`) - ini jaring pengaman yang berlaku SAMA buat
  semua cara install (pip, npm, git clone), karena dipicu oleh
  menjalankan aplikasinya, bukan oleh proses instalasinya. Khusus buat
  npm ini penting karena postinstall-nya sering silent (lihat Opsi B);
  buat pip malah satu-satunya cara, karena pip memang tidak punya hook
  setelah-install sama sekali.

Bisa juga dipanggil manual kapan saja:

```bash
github-manager --version
```

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
├── github-manager.py      # shim tipis, logic sebenarnya di modules/cli.py
├── pyproject.toml        # buat distribusi via pip (console_scripts)
├── package.json           # buat distribusi via npm (bin + postinstall)
├── bin/
│   └── github-manager    # shim dipanggil npm sebagai command global
├── scripts/
│   └── postinstall.js    # banner + cek dependency saat npm install -g
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
    ├── stash.py
    ├── rebase.py
    ├── banner.py
    ├── cli.py            # logic menu utama (dipakai github-manager.py & pip entry point)
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
6. Perlu simpan perubahan sementara tanpa commit? Pakai menu **9. Stash**.
   Perlu riwayat commit yang lurus? Pakai menu **10. Rebase**.
7. Bila baru belajar Git, buka menu **13. Belajar Git** untuk penjelasan
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
