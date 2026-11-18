"""Daftar fallback selector DOM `gemini.google.com/app` dan serializer HTML -> Markdown."""

from __future__ import annotations

import re
from pathlib import Path

SELECTORS: dict[str, list[str]] = {
    # Kotak input prompt utama Gemini (Quill rich-textarea / input-area-v2)
    "prompt_input": [
        "rich-textarea div.ql-editor[contenteditable='true']",
        "input-area-v2 div[contenteditable='true'][role='textbox']",
        "div.ql-editor.textarea[contenteditable='true']",
        "div[contenteditable='true'][aria-label*='prompt' i]",
        "div[contenteditable='true'][aria-label*='Gemini' i]",
        "div[contenteditable='true'][role='textbox']",
        "rich-textarea textarea",
    ],
    # Tombol kirim pesan
    "send_button": [
        "button.send-button:not([disabled])",
        "button[aria-label*='Send message' i]:not([disabled])",
        "button[aria-label*='Kirim pesan' i]:not([disabled])",
        "button[aria-label='Send' i]:not([disabled])",
        "button[aria-label='Kirim' i]:not([disabled])",
        "input-area-v2 button.submit:not([disabled])",
    ],
    # Indikator bahwa Gemini masih men-stream jawaban / sedang berpikir
    "stop_generating": [
        "button[aria-label*='Stop response' i]",
        "button[aria-label*='Stop generating' i]",
        "button[aria-label*='Hentikan respons' i]",
        "button[aria-label*='Hentikan' i]",
        "button.send-button.stop",
        "div.blue-circle.stop-icon",
    ],
    # Elemen pesan jawaban model
    "response_containers": [
        "model-response message-content",
        "message-content.model-response-text",
        ".model-response-text .markdown",
        "model-response .markdown-main-panel",
        ".response-container-content message-content",
    ],
    # Tombol pemilih model (Fast / Flash / Thinking / Pro)
    "model_switcher_button": [
        "[data-test-id='bard-mode-menu-button']",
        "bard-mode-switcher button",
        "button.input-area-switch",
        "input-area-v2 button[aria-haspopup='menu'][aria-label*='mode' i]",
        "button[aria-label*='Switch model' i]",
        "button[aria-label*='Ganti model' i]",
        "bard-mode-switcher [role='button']",
    ],
    # Daftar opsi di dalam menu dropdown model
    "model_menu_items": [
        "[data-test-id*='bard-mode-option']",
        ".mat-mdc-menu-panel [role='menuitemradio']",
        ".mat-mdc-menu-panel [role='menuitem']",
        ".bard-mode-list-button",
        "mat-bottom-sheet-container button",
        "[role='menu'] [role='menuitemradio']",
        "[role='menu'] [role='menuitem']",
    ],
    # Tombol '+' / pembuka menu upload file
    "upload_trigger_button": [
        "button[aria-label*='Open upload file menu' i]",
        "button[aria-label*='Add files' i]",
        "button[aria-label*='Upload files' i]",
        "button[aria-label*='Tambahkan file' i]",
        "button[aria-label*='Buka menu upload' i]",
        "uploader button",
        "[data-test-id='upload-image-button']",
        "input-area-v2 button:has(mat-icon[fonticon='add'])",
        "input-area-v2 button:has(mat-icon[data-mat-icon-name='add'])",
    ],
    # Item menu "Upload files" lokal setelah klik '+'
    "upload_local_menuitem": [
        "[data-test-id='local-images-files-uploader-button']",
        "[data-test-id*='local' i][role='menuitem']",
        "[role='menuitem']:has-text('Upload files')",
        "[role='menuitem']:has-text('Upload file')",
        "[role='menuitem']:has-text('Upload dari komputer')",
        "[role='menuitem']:has-text('Unggah file')",
        "button:has-text('Upload files')",
        "button:has-text('Unggah file')",
    ],
    # Spinner / progress upload file
    "upload_in_progress": [
        "uploader mat-progress-spinner",
        "input-area-v2 mat-progress-spinner",
        "[aria-label*='Uploading' i]",
        "[aria-label*='Mengunggah' i]",
        ".file-preview-loading",
    ],
    # Riwayat percakapan di sidebar Gemini
    "sidebar_conversations": [
        "conversations-list a[href*='/app/']",
        "nav a[href*='/app/']",
        "a.conversation[href*='/app/']",
    ],
    # Indikator pengguna belum login ke akun Google
    "unauthenticated_indicators": [
        "a[href*='accounts.google.com/ServiceLogin']",
        "button:has-text('Sign in')",
        "a:has-text('Sign in')",
        "a:has-text('Login')",
        "a:has-text('Masuk')",
    ],
}

DOM_TO_MARKDOWN_JS = r"""
(rootEl) => {
  if (!rootEl) return "";
  const clone = rootEl.cloneNode(true);

  const noiseSelectors = [
    "button",
    "mat-icon",
    ".code-block-decoration",
    ".header-formatted",
    ".tts-button",
    ".response-footer",
    ".thoughts-header-button",
    "script",
    "style",
    "svg"
  ];
  for (const sel of noiseSelectors) {
    clone.querySelectorAll(sel).forEach((n) => n.remove());
  }

  function tableToMd(table) {
    const rows = Array.from(table.querySelectorAll("tr"));
    if (!rows.length) return "";
    const matrix = rows.map((tr) =>
      Array.from(tr.querySelectorAll("th, td")).map((cell) =>
        cell.innerText.replace(/\s+/g, " ").trim().replace(/\|/g, "\\|")
      )
    );
    const colCount = Math.max(...matrix.map((r) => r.length), 0);
    if (colCount === 0) return "";
    const normalized = matrix.map((r) => {
      while (r.length < colCount) r.push("");
      return "| " + r.join(" | ") + " |";
    });
    const sep = "| " + Array(colCount).fill("---").join(" | ") + " |";
    normalized.splice(1, 0, sep);
    return "\n\n" + normalized.join("\n") + "\n\n";
  }

  function walk(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      return node.nodeValue || "";
    }
    if (node.nodeType !== Node.ELEMENT_NODE) {
      return "";
    }
    const tag = node.tagName.toLowerCase();

    if (tag === "pre") {
      const codeEl = node.querySelector("code");
      let lang = "";
      if (codeEl && codeEl.className) {
        const m = codeEl.className.match(/language-([a-zA-Z0-9_+-]+)/);
        if (m) lang = m[1];
      }
      const rawCode = (codeEl ? codeEl.innerText : node.innerText).replace(/\n+$/, "");
      return `\n\n\`\`\`${lang}\n${rawCode}\n\`\`\`\n\n`;
    }

    if (tag === "code") {
      return "`" + node.innerText.trim() + "`";
    }

    if (tag === "table") {
      return tableToMd(node);
    }

    if (tag === "br") {
      return "\n";
    }

    if (tag === "hr") {
      return "\n\n---\n\n";
    }

    const childrenText = Array.from(node.childNodes).map(walk).join("");

    if (/^h[1-6]$/.test(tag)) {
      const level = Number(tag[1]);
      return `\n\n${"#".repeat(level)} ${childrenText.trim()}\n\n`;
    }
    if (tag === "p" || tag === "div" || tag === "section" || tag === "article") {
      const trimmed = childrenText.trim();
      return trimmed ? `\n\n${trimmed}\n\n` : "";
    }
    if (tag === "strong" || tag === "b") {
      return childrenText.trim() ? `**${childrenText.trim()}**` : "";
    }
    if (tag === "em" || tag === "i") {
      return childrenText.trim() ? `*${childrenText.trim()}*` : "";
    }
    if (tag === "a") {
      const href = node.getAttribute("href") || "";
      const label = childrenText.trim() || href;
      return href && !href.startsWith("javascript:") ? `[${label}](${href})` : label;
    }
    if (tag === "ul") {
      const items = Array.from(node.children)
        .filter((c) => c.tagName.toLowerCase() === "li")
        .map((li) => `- ${walk(li).trim().replace(/\n+/g, "\n  ")}`);
      return "\n" + items.join("\n") + "\n";
    }
    if (tag === "ol") {
      const items = Array.from(node.children)
        .filter((c) => c.tagName.toLowerCase() === "li")
        .map((li, idx) => `${idx + 1}. ${walk(li).trim().replace(/\n+/g, "\n   ")}`);
      return "\n" + items.join("\n") + "\n";
    }
    if (tag === "blockquote") {
      const lines = childrenText.trim().split("\n").map((l) => `> ${l}`);
      return "\n\n" + lines.join("\n") + "\n\n";
    }
    return childrenText;
  }

  return walk(clone)
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
"""


def normalize_model_query(name: str) -> str:
    """Normalisasi nama model untuk pencocokan fleksibel pada menu Gemini Web."""
    cleaned = re.sub(r"\s+", " ", name.strip().lower())
    aliases = {
        "fast": "flash",
        "cepat": "flash",
        "penalaran": "thinking",
        "reasoning": "thinking",
    }
    return aliases.get(cleaned, cleaned)


def validate_local_files(file_paths: list[str]) -> list[Path]:
    """Validasi daftar path file lokal sebelum diunggah ke antarmuka Gemini Web."""
    resolved: list[Path] = []
    for raw in file_paths:
        p = Path(raw).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"File tidak ditemukan: {p}")
        if not p.is_file():
            raise ValueError(f"Path bukan file reguler: {p}")
        resolved.append(p)
    return resolved
