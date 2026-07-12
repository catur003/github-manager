#!/data/data/com.termux/files/usr/bin/bash
#
# install.sh
# Script instalasi GitHub Manager Termux v1.0
# Hanya dipakai untuk proses install (bukan logic utama aplikasi).
# Semua logic aplikasi ada di github-manager.py (Python).

set -e

echo "=== GitHub Manager Termux - Instalasi ==="

# 1. Update paket Termux
echo "[1/5] Memperbarui daftar paket..."
pkg update -y

# 2. Install dependency sistem: python, git, unzip, zip
echo "[2/5] Menginstall python, git, unzip, zip..."
pkg install -y python git unzip zip

# 3. Pastikan pip tersedia dan terupdate
echo "[3/5] Menyiapkan pip..."
python -m ensurepip --upgrade 2>/dev/null || true
pip install --upgrade pip

# 4. Install dependency python
echo "[4/5] Menginstall dependency Python (rich, colorama, questionary)..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pip install -r "$SCRIPT_DIR/requirements.txt"

# 5. Buat command 'github-manager' agar bisa dipanggil dari mana saja
echo "[5/5] Membuat command 'github-manager'..."
BIN_DIR="$PREFIX/bin"
LAUNCHER="$BIN_DIR/github-manager"

cat > "$LAUNCHER" << EOF
#!/data/data/com.termux/files/usr/bin/bash
python "$SCRIPT_DIR/github-manager.py" "\$@"
EOF

chmod +x "$LAUNCHER"

# Pastikan folder yang dibutuhkan aplikasi sudah ada
mkdir -p "$SCRIPT_DIR/config" "$SCRIPT_DIR/logs" "$SCRIPT_DIR/backup"

echo ""
echo "=== Instalasi selesai! ==="
echo "Jalankan aplikasi dengan mengetik: github-manager"
