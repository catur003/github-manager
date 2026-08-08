#!/data/data/com.termux/files/usr/bin/bash

set -e

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
WHITE="\033[1;37m"
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

# Termux/Python versi baru menandai environment sebagai "externally managed"
# (PEP 668), jadi 'pip install' biasa ditolak dengan error
# "externally-managed-environment". Coba pakai --break-system-packages dulu;
# kalau pip-nya versi lama dan gak kenal flag itu, fallback ke cara biasa.
pip_install() {
    if python -m pip install --break-system-packages "$@" 2>/tmp/gm_pip_err.log; then
        return 0
    fi
    if grep -qi "externally-managed-environment\|no such option" /tmp/gm_pip_err.log 2>/dev/null; then
        python -m pip install "$@"
    else
        cat /tmp/gm_pip_err.log
        return 1
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

pip_install --upgrade pip

echo
echo "== Install Library Python =="

pip_install -r requirements.txt

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
    pip_install "$MOD"
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
echo "== Membuat command 'github-manager' =="

# BUGFIX: README menjanjikan command 'github-manager' bisa dipanggil dari
# folder mana saja setelah install, tapi sebelumnya installer TIDAK PERNAH
# membuatnya - cuma 'python github-manager.py' yang jalan. Sekarang bikin
# wrapper script di $PREFIX/bin (selalu ada di PATH Termux) yang cd ke
# folder project ini lalu jalankan github-manager.py, apapun folder aktif
# user saat command dipanggil.
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${PREFIX:-/data/data/com.termux/files/usr}/bin"

if [ -d "$BIN_DIR" ]; then
    cat > "$BIN_DIR/github-manager" <<WRAPPER
#!/data/data/com.termux/files/usr/bin/bash
cd "$INSTALL_DIR" && exec python github-manager.py "\$@"
WRAPPER
    chmod +x "$BIN_DIR/github-manager"
    echo -e "${GREEN}[✓] Command 'github-manager' berhasil dibuat di $BIN_DIR${NC}"
else
    echo -e "${YELLOW}[!] $BIN_DIR tidak ditemukan - command 'github-manager' tidak dibuat.${NC}"
    echo -e "${YELLOW}    Jalankan aplikasi manual dengan: python $INSTALL_DIR/github-manager.py${NC}"
fi

echo
echo "== Permission =="
chmod +x install.sh
chmod +x github-manager.py

echo
echo -e "${WHITE}"
echo "-------------- G I T H U B --------------"
echo -e "${NC}"
echo -e "${GREEN}"
echo "#   #  ###  #   #  ###   #### ##### #### "
echo "## ## #   # ##  # #   # #     #     #   #"
echo "# # # ##### # # # ##### #  ## ####  #### "
echo "#   # #   # #  ## #   # #   # #     # #  "
echo "#   # #   # #   # #   #  #### ##### #  ##"
echo
echo "----- GitHub Repository Manager CLI -----"
echo
echo "+-----------------------------------------+"
echo "| Version : 1.3.0                         |"
echo "| Author  : catur003                      |"
echo "|                                         |"
echo "| [OK] Installation completed             |"
echo "+-----------------------------------------+"
echo
echo "          [ \$ github-manager ]           "
echo -e "${NC}"

echo "Cara menjalankan:"
echo
echo "python github-manager.py"
echo "atau github-manager (setelah setup command jika ada)"
echo