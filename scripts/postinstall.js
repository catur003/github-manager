#!/usr/bin/env node
/**
 * scripts/postinstall.js
 * Dijalankan otomatis oleh npm lifecycle hook "postinstall" setelah
 * `npm install -g github-manager` (kecuali user pakai --ignore-scripts
 * atau ignore-scripts=true di .npmrc mereka - lihat catatan di README).
 *
 * Tugasnya cuma dua:
 *  1. Tampilkan banner ASCII (versi Node, sama persis gaya-nya dengan
 *     yang ada di install.sh buat instalasi lewat Termux/git clone).
 *  2. Cek Python 3 & Git ada di PATH atau enggak - npm CUMA ngurus
 *     distribusi file & command 'github-manager', bukan environment
 *     Python/Git-nya. Kalau belum ada, kasih tahu jelas, jangan cuma
 *     diam lalu 'github-manager' gagal aneh pas dipanggil pertama kali.
 */

'use strict';

const { execSync } = require('child_process');
const pkg = require('../package.json');

const GREEN = '\x1b[0;32m';
const WHITE = '\x1b[1;37m';
const YELLOW = '\x1b[1;33m';
const RED = '\x1b[0;31m';
const NC = '\x1b[0m';

const BOX_WIDTH = 41; // sama dengan lebar blok huruf MANAGER di bawah

function boxLine(text) {
  const content = ` ${text}`.padEnd(BOX_WIDTH);
  return `|${content}|`;
}

function hasCommand(cmd) {
  try {
    const probe = process.platform === 'win32' ? `where ${cmd}` : `command -v ${cmd}`;
    execSync(probe, { stdio: 'ignore', shell: process.platform === 'win32' ? undefined : '/bin/bash' });
    return true;
  } catch {
    return false;
  }
}

function printBanner() {
  const lines = [
    `${WHITE}-------------- G I T H U B --------------${NC}`,
    '',
    `${GREEN}`,
    '#   #  ###  #   #  ###   #### ##### #### ',
    '## ## #   # ##  # #   # #     #     #   #',
    '# # # ##### # # # ##### #  ## ####  #### ',
    '#   # #   # #  ## #   # #   # #     # #  ',
    '#   # #   # #   # #   #  #### ##### #  ##',
    '',
    '----- GitHub Repository Manager CLI -----',
    '',
    '+' + '-'.repeat(BOX_WIDTH) + '+',
    boxLine(`Version : ${pkg.version}`),
    boxLine(`Author  : catur003`),
    boxLine(''),
    boxLine('[OK] Installed via npm'),
    '+' + '-'.repeat(BOX_WIDTH) + '+',
    `${NC}`,
  ];
  console.log(lines.join('\n'));
}

function main() {
  printBanner();

  const hasPython = hasCommand('python3') || hasCommand('python');
  const hasGit = hasCommand('git');
  const hasGh = hasCommand('gh'); // opsional, cuma dipakai fitur Pull Request

  if (!hasPython || !hasGit) {
    console.log(`${YELLOW}Perhatian: ada dependency yang belum terpasang.${NC}`);
    if (!hasPython) {
      console.log(`${RED}  ✗ Python 3 tidak ditemukan.${NC}`);
      console.log('    Termux : pkg install python');
      console.log('    Linux  : sudo apt install python3 python3-pip');
    }
    if (!hasGit) {
      console.log(`${RED}  ✗ Git tidak ditemukan.${NC}`);
      console.log('    Termux : pkg install git');
      console.log('    Linux  : sudo apt install git');
    }
    console.log(`${YELLOW}Command 'github-manager' baru bisa dipakai setelah ini terpasang.${NC}\n`);
  } else {
    console.log(`${GREEN}✓ Python 3 & Git terdeteksi.${NC}`);
    if (!hasGh) {
      console.log('  (opsional) gh CLI belum ada - fitur Pull Request di menu Merge butuh ini.');
    }
    console.log('\nJalankan dengan:  github-manager\n');
  }
}

main();
