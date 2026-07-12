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

check_install() {
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
echo "== Mengecek Dependency =="

check_install python python
check_install git git
check_install unzip unzip

echo
echo "== Mengecek ZIP =="

if command -v zip >/dev/null 2>&1; then
    echo -e "${GREEN}[✓] zip sudah tersedia${NC}"
else
    echo -e "${YELLOW}[!] zip tidak tersedia${NC}"
    pkg install -y zip || \
    echo -e "${YELLOW}[!] Lewati install zip (Backup ZIP dinonaktifkan)${NC}"
fi

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
echo -e "${GREEN}"
echo "========================================="
echo " Instalasi Berhasil"
echo "========================================="
echo -e "${NC}"

echo "Jalankan dengan:"
echo
echo "python github-manager.py"
echo