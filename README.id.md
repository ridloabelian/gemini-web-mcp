<p align="center">
  <img src="assets/hero-banner.svg" alt="gemini-web-mcp hero banner" width="100%" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/Protocol-MCP-6366F1?style=flat-square" alt="Model Context Protocol" />
  <img src="https://img.shields.io/badge/Engine-Patchright%20%2F%20Playwright-2EAD33?style=flat-square&logo=playwright&logoColor=white" alt="Patchright / Playwright" />
  <img src="https://img.shields.io/badge/Docker-Xvfb%20%2B%20noVNC-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker Xvfb + noVNC" />
  <img src="https://img.shields.io/badge/License-MIT-0EA5E9?style=flat-square" alt="MIT License" />
</p>

<p align="center">
  <a href="README.md">English</a> | <strong>Bahasa Indonesia</strong>
</p>

# gemini-web-mcp (Dokumentasi Bahasa Indonesia)

Server **Model Context Protocol (MCP)** *plug-and-play* berbasis **Playwright / Patchright** yang membungkus antarmuka web [`gemini.google.com/app`](https://gemini.google.com/app) menggunakan **persistent browser profile**.

Cocok dihubungkan ke **Antigravity (`agy`)**, **Claude Code / Desktop**, **Cursor**, maupun orchestrator agent mandiri seperti **Hermes Agent**—baik secara lokal (`stdio`) maupun sebagai remote server (`streamable-http`) di VPS/Homelab dengan dukungan **Xvfb + noVNC** dan proteksi **Bearer Token**.

## Arsitektur Sistem

<p align="center">
  <img src="assets/architecture.svg" alt="gemini-web-mcp system architecture" width="100%" />
</p>

## Fitur Utama

- **Persistent Google Session**: Login akun Google cukup satu kali (`--setup-auth`); cookies & IndexedDB tersimpan aman di profil lokal atau Docker volume.
- **Anti-Bot / Stealth Ready**: Mengutamakan `patchright` + argumen anti-otomasi Chrome agar tidak terblokir layar *"This browser or app may not be secure"* saat login Google, serta mendukung koneksi ke instance Chrome aktif via `--cdp-url`.
- **Multi-Turn & Single-Turn Chat (`gemini_chat`)**: Mendukung percakapan berkelanjutan via `conversation_url`, injeksi prompt multi-baris secara atomik, deteksi selesai streaming berbasis stabilitas DOM, dan konversi HTML ke Markdown bersih (menjaga blok kode dan tabel).
- **Pergantian Model Dinamis (`gemini_select_model`)**: Pindah antara model *Fast / Flash*, *Thinking*, *Pro*, dan model lain yang aktif di akun Google.
- **Multi-File Upload (`gemini_upload_files`)**: Unggah PDF, gambar, source code, dokumen, atau video lokal langsung ke percakapan Gemini.
- **Manajemen Percakapan & Diagnostik (`gemini_list_recent_chats`, `gemini_new_chat`, `gemini_status`)**: Baca riwayat percakapan dari sidebar dan pantau kesehatan selector DOM.
- **Bundled Agent Skill (`skills/gemini-web-mcp/`)**: Dilengkapi `SKILL.md` siap pasang (default Bahasa Inggris + [versi Bahasa Indonesia](skills/gemini-web-mcp/SKILL.id.md)) untuk Claude Code, Antigravity, Cursor, dan Hermes Agent.

## Quick Start 1: Lokal (Laptop / Desktop - Plug & Play)

Pastikan Python 3.11+ terpasang, lalu jalankan skrip bootstrap satu perintah:

```bash
git clone https://github.com/ridloabelian/gemini-web-mcp.git
cd gemini-web-mcp
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
```

Skrip di atas otomatis:
1. Menginstal `uv` (jika belum ada) dan seluruh dependensi `pyproject.toml`.
2. Mengunduh Chromium untuk Patchright.
3. Membuka jendela browser ke `https://gemini.google.com/app` agar kamu bisa login akun Google satu kali.
4. Mencetak konfigurasi JSON MCP siap tempel beserta path absolut di mesinmu.

### Konfigurasi MCP Client Lokal (`stdio`)

Tambahkan ke konfigurasi MCP client (`.mcp.json`, Claude Desktop, Cursor, atau Antigravity):

```json
{
  "mcpServers": {
    "gemini-web": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/absolut/ke/gemini-web-mcp",
        "gemini-web-mcp"
      ],
      "env": {
        "GEMINI_PROFILE_DIR": "~/.gemini-web-mcp/profile",
        "GEMINI_HEADLESS": "true",
        "GEMINI_BROWSER_CHANNEL": "chrome"
      }
    }
  }
}
```

Atau jalankan langsung tanpa clone manual via `uvx` (setelah pernah menjalankan `--setup-auth`):

```json
{
  "mcpServers": {
    "gemini-web": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/ridloabelian/gemini-web-mcp.git",
        "gemini-web-mcp"
      ]
    }
  }
}
```

## Memasang Bundled Agent Skill (`SKILL.md`)

Repositori ini menyertakan skill siap pakai di folder `skills/gemini-web-mcp/` (`SKILL.md` berbahasa Inggris sebagai default dan `SKILL.id.md` untuk Bahasa Indonesia) agar coding agent tahu alur cek sesi, pemilihan model, serta upload file secara presisi:

```bash
# Via Agent Skills CLI
npx skills add ridloabelian/gemini-web-mcp

# Claude Code
cp -r skills/gemini-web-mcp ~/.claude/skills/

# Antigravity / Hermes Agent workspace
mkdir -p ~/.agent/skills && cp -r skills/gemini-web-mcp ~/.agent/skills/
```

## Quick Start 2: Deploy di VPS / Homelab (Docker + Xvfb + noVNC)

Untuk server Linux tanpa monitor fisik, container ini menjalankan browser *headed* di atas layar virtual **Xvfb (`:99`)** sehingga lolos deteksi headless Google, dilengkapi portal **noVNC** untuk login pertama kali:

```bash
git clone https://github.com/ridloabelian/gemini-web-mcp.git
cd gemini-web-mcp
cp .env.example .env
# Isi GEMINI_AUTH_TOKEN di .env dengan token acak yang kuat!
docker compose up -d --build
```

### Langkah Login Pertama Kali di VPS:
1. Buat SSH tunnel dari laptop ke VPS untuk membuka portal noVNC secara aman:
   ```bash
   ssh -L 6080:127.0.0.1:6080 user@ip-vps-kamu
   ```
2. Buka `http://localhost:6080/vnc.html` di browser laptop, klik **Connect**, lalu login ke akun Google pada jendela Chromium yang tampil di layar.
3. Setelah masuk ke halaman chat Gemini, sesi tersimpan permanen di volume `gemini_profile`. Kamu bisa mematikan noVNC kapan saja dengan mengubah `ENABLE_NOVNC=false` di `.env` lalu `docker compose up -d`.

### Konfigurasi Remote MCP (`StreamableHTTP`)

Endpoint MCP aktif di `http://<host>:8765/mcp` (dan healthcheck di `/healthz`). Jika dipasang di balik Cloudflare Tunnel / Nginx Reverse Proxy:

```json
{
  "mcpServers": {
    "gemini-web-remote": {
      "url": "https://mcp-domain-kamu.id/mcp",
      "headers": {
        "Authorization": "Bearer TOKEN_RAHASIA_DARI_ENV"
      }
    }
  }
}
```

## Daftar MCP Tools yang Tersedia

| Nama Tool | Fungsi Utama |
| :--- | :--- |
| `gemini_setup_auth` | Membuka browser berjendela (headed) untuk login akun Google pertama kali dan menyimpan sesi ke persistent profile. |
| `gemini_chat` | Mengirim prompt (mendukung `new_chat`, `conversation_url`, pilih `model` otomatis, dan lampirkan `file_paths`) serta mengembalikan jawaban Markdown bersih. |
| `gemini_select_model` | Mengganti model aktif di menu mode switcher Gemini (`Flash`, `Thinking`, `Pro`, dsb.) dan menampilkan daftar model yang tersedia. |
| `gemini_upload_files` | Mengunggah satu atau banyak file lokal ke percakapan aktif (dengan atau tanpa instruksi `prompt` langsung). |
| `gemini_list_recent_chats` | Mengambil daftar judul dan URL percakapan terbaru dari sidebar `gemini.google.com`. |
| `gemini_new_chat` | Membuka percakapan baru yang bersih di `gemini.google.com/app`. |
| `gemini_status` | Mengecek status autentikasi profil, model aktif, URL saat ini, dan kecocokan selector DOM. |

## Variabel Lingkungan (`.env`)

| Variabel | Default | Keterangan |
| :--- | :--- | :--- |
| `GEMINI_PROFILE_DIR` | `~/.gemini-web-mcp/profile` | Direktori penyimpanan persistent browser profile. |
| `GEMINI_HEADLESS` | `true` | Jalankan browser tanpa jendela (`false` direkomendasikan saat di dalam Xvfb Docker). |
| `GEMINI_BROWSER_CHANNEL` | `chrome` | Gunakan `chrome` lokal, `msedge`, atau kosongkan `""` untuk memakai Chromium bawaan. |
| `GEMINI_CDP_URL` | *(kosong)* | Opsional attach ke Chrome aktif via CDP, mis. `http://127.0.0.1:9222`. |
| `GEMINI_RESPONSE_TIMEOUT` | `180` | Batas tunggu maksimum respons streaming Gemini dalam detik. |
| `GEMINI_AUTH_TOKEN` | *(kosong)* | Bearer token untuk memproteksi endpoint HTTP/SSE publik. |

## Pengujian Lokal & CI

```bash
make test
```

Template GitHub Actions tersedia di `examples/github-actions-ci.yml` (salin ke `.github/workflows/ci.yml` jika ingin mengaktifkan pengujian otomatis pada setiap push).

## Lisensi

MIT License
