# CLAUDE.md

Project context for Claude Code. Read this before making changes.

## What this is

Local Django web app to view and edit AI tool configuration files (Claude Code, Qwen, Codex, OpenCode, Gemini, Cursor, Kilo, QwenPaw). Reads/writes JSON and TOML files under the user's home directory, with auto-backup, profile snapshots, structured forms, diff preview, and extension discovery.

Runs on `127.0.0.1` only. Not designed for multi-user or network exposure.

## Stack

- Python 3.12, Django 6.x, `tomli_w` for TOML write, `tomllib` (stdlib) for read
- SQLite (`db.sqlite3`) — stores profiles, path overrides, OAuth configs, and token check history
- Frontend: Tailwind via CDN + Alpine.js (no build step)
- Package manager: `uv`

## Layout

```
config_manager/        Django project (settings, urls, wsgi)
providers/
  registry.py          Static list of supported providers (path, format, description)
  schema.py            Per-provider structured form schemas (FieldSpec + flags)
  services.py          read/parse/serialize/validate/backup/mask + JSONC fallback
  structured.py        build_context() and apply_post() for structured forms
  views.py             index, detail, validate, diff, download, profiles, backups, settings, oauth
  extensions.py        discover_extensions() — scans filesystem for skills/agents/mcp/hooks/plugins
  sessions.py          read_claude_sessions(), read_qwen_sessions(), read_codex_sessions()
  connection.py        ConnectionTester — test API connectivity for providers
  forms.py             ConfigEditForm (single content textarea)
  models.py            Profile, PathOverride, OAuthConfig, TokenCheck
  urls.py
templates/
  base.html
  providers/
    index.html         provider grid
    detail.html        Structured/Raw/Sessions tabs + profiles + backups
    sessions.html      Sessions Browser (all providers + per-provider views)
    extensions.html    Extensions Dashboard (discovered extensions by provider)
    settings.html      Custom paths + OAuth config management
    _structured_form.html   structured editor partial
    _extensions_section.html  extension type section partial
```

## Run

```bash
cd ~/LATIHAN/ai_config_manager
uv run python manage.py migrate
uv run python manage.py runserver 8801
```

Open http://127.0.0.1:8801/.

## Key behaviors to preserve

- **Auto-backup**: every write creates `<file>.bak.<YYYYMMDD-HHMMSS>` next to the original. Keep this in any new write path.
- **Preserve unknown keys**: structured `apply_post` parses the file, mutates only known paths, then re-serializes. Do not replace the whole document.
- **Empty field = remove key**: structured forms remove a JSON key when the field is blank, rather than writing `""`. Match this convention for any new fields.
- **Path safety**: `find_backup` uses `Path.relative_to` to prevent traversal. Apply the same pattern when adding new file ops driven by URL params.
- **Secret masking**: `mask_secrets` recursively masks values whose key contains `key`, `token`, `secret`, `password`, `auth`, `api_key`. Keep this list in `services.py`.
- **JSONC fallback**: `parse_text` falls back to `_strip_jsonc` for JSON files containing `//` or `/* */` (e.g. `~/.qwen/settings.json`). `has_jsonc_artifacts` flags this so the UI can warn that structured save will strip comments.

## Adding a new provider

1. Append a `Provider(...)` to `PROVIDERS` in `providers/registry.py`.
2. (Optional) Add a `ProviderSchema` in `providers/schema.py` with the named fields. Set `has_env_editor`, `has_qwen_model_providers`, `has_opencode_providers`, `has_claude_permissions`, or `has_claude_hooks` if needed.
3. (Optional) Add a starter template entry to `STARTER_TEMPLATES` in `providers/views.py`.

No URL or template changes needed for raw editor support.

## Adding a new structured editor type

1. Add a flag (`has_xxx`) to `ProviderSchema` in `schema.py`.
2. In `structured.py`:
   - In `build_context`, populate context keys from the parsed file when the flag is set.
   - In `apply_post`, read POST values, mutate `data`, and merge back. Preserve any unrelated keys.
3. In `templates/providers/_structured_form.html`, add a `{% if structured.schema.has_xxx %}` block. Reuse Alpine helpers `addRow` or write a dedicated component like `opencodeProviders`.

## Endpoints (relevant ones)

### Core
- `GET  /` — index (provider grid)
- `GET  /p/<key>/` — detail (structured + raw + profiles + backups)
- `POST /p/<key>/` — save raw editor contents
- `POST /p/<key>/structured/save/` — save structured form
- `POST /p/<key>/validate/` — JSON validation (returns `{ok, message, format}`)
- `POST /p/<key>/diff/` — unified diff for raw editor vs disk
- `POST /p/<key>/structured/diff/` — diff for structured form vs disk
- `GET  /p/<key>/download/` — download current file (or starter when missing)
- `POST /p/<key>/template/` — write starter template
- `POST /p/<key>/profiles/save/` — save profile from POST `name`, `note`, `content`
- `POST /p/<key>/profiles/<id>/apply/` — write profile content to disk (with backup)
- `POST /p/<key>/profiles/<id>/delete/`
- `POST /p/<key>/backups/<filename>/restore/` — restore a `.bak.*` file (with current backup first)
- `POST /p/<key>/backups/<filename>/delete/`

### Settings & OAuth
- `GET  /settings/` — custom paths + OAuth config management
- `POST /settings/save/` — save custom path override
- `POST /settings/reset/<key>/` — reset path to default
- `POST /settings/oauth/save/` — save OAuth detection config
- `POST /settings/oauth/reset/<key>/` — reset OAuth config to default

### Extensions
- `GET  /extensions/` — Extensions Dashboard (discovered extensions by provider)

All POST routes use Django CSRF.

## Conventions

- Don't introduce new dependencies without a strong reason.
- Don't change file format on save (JSON stays JSON, TOML stays TOML).
- TOML root must be a dict; reject otherwise.
- Use `messages` framework for user-visible feedback after redirects.
- Follow the existing error handling style: `ConfigParseError` for parser issues, `OSError` caught around `write_text`, JSON validation returned via `JsonResponse`.
- Alpine.js dynamic DOM: use Vanilla JS (`document.createElement` + `addEventListener`) instead of `innerHTML` + `Alpine.initTree` for reliable event binding (see Env Editor `addEnvRow` pattern).

## Features implemented

### Core
- Provider registry with OS-aware paths (Windows/Linux/macOS)
- Raw editor (textarea) with syntax validation
- Structured forms (schema-driven) with field types: text, select, checkbox, textarea, env-editor, array
- Auto-backup on every write
- Profile snapshots (save/restore/delete)
- Backup history (restore/delete)
- Diff preview (raw vs disk, structured vs disk)
- Secret masking in raw editor
- JSONC fallback for files with comments

### Settings
- Custom path overrides per provider (stored in `PathOverride` model)
- OAuth login status detection (CLI-based, supports Claude Code)
- OAuth config management (stored in `OAuthConfig` model)
- Connection testing (`ConnectionTester` — validates API keys/tokens)

### Extensions
- Extensions Dashboard (`/extensions/`) — auto-discovers skills/agents/mcp/hooks/plugins from filesystem
- Extension types: skill, agent, mcp, hook, plugin
- Provider tabs with extension counts
- Type-based sections with descriptions and examples

### UI/UX
- Password field show/hide toggle (auto-detects secret keys)
- Env Editor with dynamic row add/remove (Vanilla JS pattern)
- Responsive grid layouts
- Toast messages for success/error feedback

## Things not implemented yet

- Permission editor for Kilo (`permission.bash`, `permission.read`, `permission.external_directory`)
- Diff against an arbitrary profile (currently only vs disk)
- Export/import profile bundle
- Search/filter provider list
- Tests (no `pytest` or Django test setup yet)

