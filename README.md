# AI Config Manager

Web app sederhana untuk membaca, mengedit, dan generate file konfigurasi
dari berbagai AI provider CLI/tool dalam satu tempat.

## Provider yang didukung

| Key | Tool | File | Format |
|-----|------|------|--------|
| `claude` | Claude Code | `~/.claude/settings.json` | JSON |
| `qwen` | Qwen CLI | `~/.qwen/settings.json` | JSON |
| `codex` | OpenAI Codex | `~/.codex/config.toml` | TOML |
| `opencode` | OpenCode | `~/.config/opencode/opencode.json` | JSON |
| `gemini` | Gemini CLI | `~/.gemini/settings.json` | JSON |
| `cursor` | Cursor | `~/.cursor/settings.json` | JSON |
| `kilo` | Kilo Code | `~/.config/kilo/config.json` | JSON |
| `qwenpaw` | QwenPaw | `~/.qwenpaw/config.json` | JSON |
| `pi` | Pi Coding Agent | `~/.pi/agent/settings.json` | JSON (multi-file: settings/models/mcp) |

Provider list ada di `providers/registry.py` jika perlu menambah/ubah.

## Fitur

- List semua provider + status (file ada / belum ada).
- Editor raw text dengan syntax-aware validation (JSON/TOML).
- Tombol **Validate** sebelum save (AJAX).
- **Save** dengan auto-backup `<file>.bak.<timestamp>` di samping aslinya.
- **Generate starter template** untuk membuat file dari nol dengan default values.
- **Download** file aktif sebagai attachment.
- **Reload from disk** untuk discard perubahan di form.

## Stack

- Django 6, Tailwind (CDN), Alpine.js (CDN)
- `tomli-w` untuk write TOML, `tomllib` (stdlib 3.11+) untuk read

## Run

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Buka http://127.0.0.1:8000/

## Catatan keamanan

- App ini menulis ke file di home directory user. Auto-backup aktif by default,
  bisa di-uncheck di toolbar editor.
- Tidak menjalankan server publik. Default `runserver` listen 127.0.0.1.
- File yang dikelola sering memuat API key. Jangan host instance ini di
  jaringan terbuka.
