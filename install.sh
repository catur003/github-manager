#!/data/data/com.termux/files/usr/bin/bash

set -e

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
NC="\033[0m"

echo -e "${BLUE}"
echo "========================================="
echo "     GitHub Manager Installer v1.0"
echo "========================================="
echo -e "${NC}"

install_if_missing() {
    local CMD=$1
    local PKG=$2

    if command -v "$CMD" >/dev/null 2>&1; then
        echo -e "${GREEN}[✓] $PKG sudah terinstall${NC}"
    else
        echo -e "${YELLOW}[...] Menginstall $PKG${NC}"
        pkg install -y "$PKG" || {
            echo -e "${RED}[✗] Gagal menginstall $PKG${NC}"
        }
    fi
}

echo
echo "== Detect Termux =="

if [[ -n "$TERMUX_VERSION" && "$TERMUX_VERSION" == *"googleplay"* ]]; then
    echo -e "${YELLOW}WARNING"
    echo "Anda menggunakan Termux Google Play."
    echo "Disarankan menggunakan Termux GitHub/F-Droid."
    echo "Installer tetap lanjut.${NC}"
fi

echo
echo "== Mengecek Dependency =="

install_if_missing python python
install_if_missing git git
install_if_missing unzip unzip

install_if_missing zip zip

echo
echo "== GitHub CLI (opsional) =="
if command -v gh >/dev/null 2>&1; then
    echo -e "${GREEN}[✓] gh sudah terinstall${NC}"
else
    read -p "Install GitHub CLI? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        pkg install -y gh || echo -e "${YELLOW}[!] GitHub CLI dilewati${NC}"
    else
        echo -e "${YELLOW}[!] GitHub CLI dilewati${NC}"
    fi
fi

echo
echo "== Update Packages =="
pkg update -y || true
pkg upgrade -y || true

echo
echo "== Upgrade PIP =="

python -m pip install --upgrade pip

echo
echo "== Install Library Python =="

python -m pip install -r requirements.txt

echo
echo "== Verifikasi Module =="

MODULES=("rich" "questionary" "colorama")

for MOD in "${MODULES[@]}"
do

python - <<EOF
import importlib,sys
try:
    importlib.import_module("$MOD")
    print("OK")
except:
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}[✓] $MOD${NC}"
else
    echo -e "${YELLOW}[!] Menginstall $MOD${NC}"
    python -m pip install "$MOD"
fi

done

echo
echo "== Membuat Folder =="

mkdir -p backup
mkdir -p logs
mkdir -p config

echo
echo "== Mengecek Git =="

git --version

echo
echo "== Mengecek Python =="

python --version

echo
echo "== Permission =="
chmod +x install.sh
chmod +x github-manager.py

echo
echo -e "${GREEN}"
echo "========================================="
echo " ✓ Install selesai"
echo "========================================="
echo -e "${NC}"

echo "Cara menjalankan:"
echo
echo "python github-manager.py"
echo "atau github-manager (setelah setup command jika ada)"
echo