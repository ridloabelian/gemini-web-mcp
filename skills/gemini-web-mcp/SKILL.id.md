---
name: gemini-web-mcp
description: Orkestrasi Google Gemini Web (gemini.google.com/app) melalui server Playwright gemini-web-mcp. Gunakan saat pengguna meminta untuk bertanya ke Gemini Web, meminta second opinion dari model Gemini Pro atau Thinking, menganalisis file PDF/gambar/kode/video lokal lewat sesi Gemini Web persisten, atau melanjutkan percakapan gemini.google.com tanpa memakai kuota API berbayar.
---

# gemini-web-mcp (Versi Bahasa Indonesia)

[English](SKILL.md) | **Bahasa Indonesia**

Kendalikan sesi browser `gemini.google.com/app` yang sudah terautentikasi secara persisten melalui MCP server `gemini-web-mcp` untuk chat multi-turn, pergantian model dinamis, dan analisis multi-file lokal.

## Kapan Menggunakan Skill Ini

- Mendelegasikan penalaran kompleks, *second-opinion code review*, atau sintesis berbasis web ke Gemini Web (model `Flash`, `Thinking`, atau `Pro`).
- Menganalisis dokumen lokal, PDF, tangkapan layar, kode sumber, atau video dengan mengunggahnya langsung ke percakapan `gemini.google.com`.
- Melanjutkan atau menelusuri riwayat percakapan dari akun Gemini Web pengguna tanpa memerlukan API key berbayar dari AI Studio maupun Vertex AI.

## Langkah Kerja Utama

### 1. Periksa Kesehatan Sesi Lebih Dulu

Panggil `gemini_status` di awal sesi baru atau setiap kali muncul galat autentikasi maupun selector.

- Pastikan nilai `"authenticated": true` pada respons JSON sebelum mengirim prompt atau mengunggah file.
- Jika `"authenticated": false`, jalankan `gemini_setup_auth` agar pengguna dapat menyelesaikan login Google satu kali pada jendela browser (atau melalui portal Xvfb/noVNC di server remote).

### 2. Sesuaikan Model dengan Beban Tugas

Pilih model Gemini Web secara langsung lewat parameter `model` pada `gemini_chat` atau secara eksplisit lewat `gemini_select_model`:

- Gunakan `"Flash"` (atau `"Fast"`) untuk pertanyaan singkat, ringkasan cepat, dan ekstraksi dokumen ringan.
- Gunakan `"Thinking"` atau `"Pro"` untuk analisis arsitektur, *debugging* mendalam, matematika bertahap, dan riset panjang.
- Jika `gemini_select_model` mengembalikan `"switched": false`, periksa daftar `"available_models"` pada responsnya lalu ulangi dengan label model yang tersedia di akun tersebut.

### 3. Jalankan Chat Single-Turn, Multi-Turn, atau Multimodal

Utamakan `gemini_chat` karena tool ini menangani pemilihan model, unggah lampiran file, injeksi prompt multi-baris, dan deteksi selesainya streaming dalam satu panggilan atomik:

```json
{
  "prompt": "Audit spesifikasi arsitektur ini untuk potensi race condition dan rangkum solusinya dalam tabel.",
  "new_chat": true,
  "model": "Pro",
  "file_paths": ["/path/absolut/ke/arsitektur.pdf"]
}
```

- Simpan nilai `"conversation_url"` dari hasil `gemini_chat` jika berencana mengirim pertanyaan lanjutan.
- Kirim kembali `"conversation_url"` tersebut pada panggilan `gemini_chat` berikutnya (dengan `"new_chat": false`) agar konteks percakapan tetap utuh.
- Atur `"new_chat": true` (atau panggil `gemini_new_chat`) saat berpindah ke topik baru agar konteks lama tidak mencemari jawaban.
- Gunakan `gemini_list_recent_chats` ketika pengguna ingin membuka kembali diskusi lama dari sidebar Gemini.

## Referensi Tool

| Nama Tool | Kegunaan Utama | Parameter Kunci |
| :--- | :--- | :--- |
| `gemini_status` | Cek status login, badge model aktif, URL saat ini, dan kecocokan selector DOM | *(tidak ada)* |
| `gemini_setup_auth` | Buka jendela browser / noVNC untuk login akun Google satu kali | `timeout_seconds` (default `300`) |
| `gemini_chat` | Kirim prompt, opsional ganti model & unggah file, kembalikan Markdown bersih | `prompt`, `new_chat`, `conversation_url`, `model`, `file_paths`, `timeout_seconds` |
| `gemini_select_model` | Ganti model aktif di Gemini Web dan tampilkan daftar opsi model | `model_name` |
| `gemini_upload_files` | Unggah file lokal ke kotak komposisi, opsional langsung kirim `prompt` | `file_paths`, `prompt`, `new_chat` |
| `gemini_list_recent_chats` | Ambil daftar judul dan URL percakapan terbaru dari sidebar | `limit` (default `15`) |
| `gemini_new_chat` | Buka percakapan baru yang bersih di `gemini.google.com/app` | *(tidak ada)* |

## Hal Penting yang Perlu Diperhatikan (Gotchas)

- **Gunakan path absolut pada `file_paths`**: Server MCP memvalidasi file pada mesin tempat `gemini-web-mcp` berjalan. Jangan mengirim path file lokal laptop ke server `StreamableHTTP` di VPS remote kecuali file tersebut memang berada di filesystem server tersebut.
- **Naikkan `timeout_seconds` untuk model `Thinking` / `Pro` dan file besar**: Proses berpikir mendalam atau pembacaan banyak PDF bisa memakan waktu lebih dari 120 detik. Berikan `timeout_seconds: 300` agar tidak terputus sebelum selesai.
- **Jalankan pemanggilan secara berurutan pada satu profil**: Satu profil browser memakai satu kunci antrean (`asyncio.Lock`). Hindari memanggil beberapa `gemini_chat` secara paralel tanpa menyertakan `conversation_url` masing-masing.
- **Antisipasi pembaruan antarmuka web Google**: Jika `gemini_status` menunjukkan `null` pada `matched_selectors`, periksa `src/gemini_web_mcp/selectors.py` dan tambahkan selector terbaru ke urutan teratas daftar fallback terkait.
