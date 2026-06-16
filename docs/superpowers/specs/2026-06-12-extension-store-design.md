# Extension Store: Install & Manage Extensions Per Provider

**Date:** 2026-06-12
**Status:** Draft
**Author:** Brainstorming session

---

## Overview

Add an Extension Store feature to the AI Config Manager app that allows users to browse, install, and manage extensions (Skills, MCP servers, Hooks, Plugins, Agents) for multiple AI providers (Claude Code, Qwen, Gemini, Codex, OpenCode, Kilo, Cursor, QwenPaw) from a centralized catalog page.

**Key concept:** Install once globally, attach to multiple providers with per-provider configuration.

## Scope

- **Extension types:** skill, mcp, hook, plugin, agent
- **Providers:** all 8 registered providers
- **Sources:** GitHub repos, npm packages, brew packages, uvx packages, raw scripts
- **Lifecycle:** install + uninstall (update deferred to future iteration)

## Data Model

### `ExtensionCatalog`

Represents an available extension in the catalog.

| Field | Type | Keterangan |
|---|---|---|
| `name` | CharField(max_length=200) | Display name |
| `slug` | SlugField(unique=True) | URL-safe identifier, auto-generated from name |
| `ext_type` | CharField | One of: `skill`, `mcp`, `hook`, `plugin`, `agent` |
| `description` | TextField | Short description |
| `source_url` | URLField(blank=True) | GitHub repo URL or package registry URL |
| `install_method` | CharField | One of: `git_clone`, `npm_npx`, `uvx`, `brew`, `script` |
| `package_name` | CharField(max_length=200, blank=True) | Package name (e.g., `@modelcontextprotocol/server-filesystem`) |
| `supported_providers` | JSONField(default=list) | List of provider keys (e.g., `["claude", "qwen", "gemini"]`) |
| `install_config` | JSONField(default=dict) | Per-provider install template (see below) |
| `is_curated` | BooleanField(default=False) | True = curated seed, False = user-added |
| `icon` | CharField(max_length=10, blank=True) | Emoji or icon class |
| `created_at` | DateTimeField(auto_now_add=True) | |
| `updated_at` | DateTimeField(auto_now=True) | |

#### `install_config` JSON Structure

```json
{
  "claude": {
    "target_dir": "~/.claude/skills/{slug}",
    "config_file": "~/.claude/settings.json",
    "config_path": "mcpServers.{slug}",
    "config_value": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  },
  "qwen": {
    "target_dir": "~/.qwen/skills/{slug}",
    "config_file": "~/.qwen/settings.json",
    "config_path": "mcpServers.{slug}",
    "config_value": { "command": "npx", "args": ["-y", "..."] }
  }
}
```

- `{slug}` is replaced with the extension's slug at install time.
- `target_dir` is used for `git_clone` and `script` methods. Can be empty for config-only installs (`npm_npx`, `uvx`).
- `config_file` + `config_path` + `config_value` define what gets written to the provider's config.

### `InstalledExtension`

Represents a globally installed extension artifact.

| Field | Type | Keterangan |
|---|---|---|
| `catalog` | ForeignKey(ExtensionCatalog) | The extension that was installed |
| `install_path` | CharField(max_length=500, blank=True) | Absolute path on disk |
| `version` | CharField(max_length=100, blank=True) | Git commit hash or package version |
| `installed_at` | DateTimeField(auto_now_add=True) | |

**Computed properties:**

- `status` → `"installed"` | `"missing"` | `"update_available"` | `"modified"`
- `attached_providers` → list of provider keys from related ProviderAttachments

### `ProviderAttachment`

Links an installed extension to a specific provider with provider-specific config.

| Field | Type | Keterangan |
|---|---|---|
| `installed` | ForeignKey(InstalledExtension, related_name="attachments") | The installed extension |
| `provider_key` | CharField(max_length=50) | Provider key (e.g., "claude") |
| `config_file` | CharField(max_length=500) | Absolute path to provider config file |
| `config_path` | CharField(max_length=200) | JSON/TOML path in config (e.g., `mcpServers.filesystem`) |
| `config_value` | JSONField | The value written to config |
| `attached_at` | DateTimeField(auto_now_add=True) | |

**Unique constraint:** `(installed, provider_key)` — one attachment per provider per extension.

## Install Engine

### Architecture

Single `InstallEngine` class with method handlers per install method.

```python
class InstallEngine:
    def install(catalog, provider_keys) -> InstalledExtension
    def attach(installed, provider_key, overrides=None) -> ProviderAttachment
    def detach(attachment) -> None
    def uninstall(installed) -> None
    def validate(catalog, provider_key) -> list[str]
```

### Install Flow

1. **Validate** — check provider exists, extension not already installed globally, dependencies available
2. **Backup** — backup provider config file (uses existing backup system)
3. **Install artifact** — execute based on `install_method`:

| Method | Command | Notes |
|---|---|---|
| `git_clone` | `git clone <source_url> <target_dir>` | Clone repo to target directory |
| `npm_npx` | No-op | Config-only; npx runs on-demand |
| `uvx` | No-op | Config-only; uvx runs on-demand |
| `brew` | `brew install <package_name>` | System-wide install |
| `script` | Download/write to target_dir | Write script file |

4. **Write config** — if `config_path` is set, write `config_value` to provider config file
5. **Record** — save `InstalledExtension` and `ProviderAttachment` rows
6. **Rollback on failure** — if step 3 or 4 fails, restore backup and remove artifact

### Uninstall Flow

**Detach (per provider):**
1. Backup config file
2. Remove config entry from provider config
3. Delete `ProviderAttachment` record
4. Artifact remains on disk (can be attached to other providers)

**Uninstall (global):**
1. Check: any `ProviderAttachment` still exists? → Block with "Detach from all providers first"
2. Remove artifact from disk (`shutil.rmtree` or `brew uninstall`)
3. Delete `InstalledExtension` record

### Pre-flight Checks

| Check | On Failure |
|---|---|
| Provider exists and config file exists | Block, show error |
| Extension not already installed globally | Block, suggest "Attach to provider" |
| Extension not already attached to this provider | Block, show "already attached" |
| Required tool available (`git`/`npm`/`brew`/`uv`) | Block, show install instructions |
| Target directory writable | Block, show permission error |
| Config file parseable | Block, show parse error |

### Rollback Strategy

- **Step 2 (artifact) fails:** No rollback needed — config not touched.
- **Step 3 (config write) fails:** Restore config from backup, remove artifact.
- **Step 3 succeeds but verification fails:** Restore config from backup, remove artifact.

## UI/UX

### New Page: `/extensions/store/`

**Layout:**
- Header: "Extension Store" with search bar and filters
- Two sections: "Curated" and "Custom (User Added)"
- Grid of extension cards

### Extension Card

Each card shows:
- Icon/emoji
- Name
- Description (one line)
- Badges: install method, extension type, supported providers
- Install button with dropdown:
  - "Install & Attach to..." → submenu to pick provider(s)
  - "Install only" → install globally without attaching

### Filters

- **Search:** client-side filter by name/description (Alpine.js)
- **Type filter:** All / Skill / MCP / Hook / Plugin / Agent
- **Provider filter:** All / Claude / Qwen / Gemini / Codex / OpenCode / Kilo / Cursor / QwenPaw
- **Source filter:** All / Curated / Custom

### Install Modal

Shows:
- Extension name, source, method
- Checkbox list of supported providers to attach
- Per-provider command preview (editable args)
- "What will happen" summary (backup path, config changes, files to install)
- Cancel / Install buttons

### Add Custom Extension Form

Fields:
- Name
- Type (dropdown: skill/mcp/hook/plugin/agent)
- Source URL (GitHub, npm, etc.)
- Install Method (dropdown: git_clone/npm_npx/uvx/brew/script)
- Package Name
- Supported Providers (checkboxes)

### Integration with Existing Extensions Page (`/extensions/`)

- Extensions with `ProviderAttachment` show "Attached" badge
- "Detach" button per provider
- "Browse Store" link in header → redirects to `/extensions/store/`
- Extensions with `status == "missing"` show warning + offer cleanup/reinstall

## Error Handling

### Status Display

| Status | Icon | Meaning |
|---|---|---|
| `installed` | ✅ | Normal, working |
| `missing` | ⚠️ | Artifact deleted manually from disk |
| `update_available` | 🔄 | New commit/version available |
| `modified` | ✏️ | Local changes detected |

### Error Messages

- Install success → green toast + redirect to Extensions page
- Install failed → red banner with detail + auto-rollback notification
- Partial failure → yellow banner listing what succeeded and what failed

### Edge Cases

| Case | Handling |
|---|---|
| Config file edited manually after install | Detect via signature check, warn before uninstall |
| Git clone target dir already exists | Skip clone, verify correct repo via `git remote -v` |
| npm package deprecated | Show warning (optional registry check) |
| Provider config format changed | Catch parse error, suggest manual fix |
| User deletes artifact manually | Detect on Extensions page load, mark as "missing", offer cleanup |
| Duplicate extension name | Block with error message |

## Curated Catalog (Seed Data)

### MCP Servers

| Name | Package | Method | Providers |
|---|---|---|---|
| Filesystem | `@modelcontextprotocol/server-filesystem` | npm_npx | claude, qwen, gemini, qwenpaw |
| GitHub | `@modelcontextprotocol/server-github` | npm_npx | claude, qwen, gemini, qwenpaw |
| Postgres | `@modelcontextprotocol/server-postgres` | npm_npx | claude, qwen, gemini, qwenpaw |
| Slack | `@modelcontextprotocol/server-slack` | npm_npx | claude, qwen, gemini, qwenpaw |
| Memory | `@modelcontextprotocol/server-memory` | npm_npx | claude, qwen, gemini, qwenpaw |
| Puppeteer | `@modelcontextprotocol/server-puppeteer` | npm_npx | claude, qwen, gemini, qwenpaw |
| Brave Search | `@modelcontextprotocol/server-brave-search` | npm_npx | claude, qwen, gemini, qwenpaw |
| Code Review Graph | `code-review-graph` | uvx | claude, qwen, gemini, qwenpaw |

### Skills

| Name | Source | Method | Providers |
|---|---|---|---|
| Brainstorming | User-provided GitHub URL | git_clone | claude, qwen, gemini |
| Code Review | User-provided GitHub URL | git_clone | claude, qwen, gemini |
| Refactor | User-provided GitHub URL | git_clone | claude, qwen, gemini |

> Note: Skill source URLs are placeholders — users add their own GitHub repos via the "Add Custom Extension" form. Curated skills will be populated once specific repos are identified.

### Hooks

| Name | Source | Method | Providers |
|---|---|---|---|
| Auto-format | Built-in script template | script | claude, gemini, codex |
| Pre-commit check | Built-in script template | script | claude, gemini, codex |

> Note: Hook scripts are bundled with the app as templates. Users customize args per provider during attach.

### Tools

| Name | Source | Method | Providers |
|---|---|---|---|
| RTK | `github.com/rtk-ai/rtk` | git_clone | claude, qwen, gemini, qwenpaw |

### Seed Strategy

- Django fixture: `providers/fixtures/curated_extensions.json`
- Management command: `python manage.py seed_catalog`
- Auto-seed on first migrate via `post_migrate` signal (only if catalog is empty)
- Update command: `python manage.py update_catalog` for future curated additions

## Security Considerations

- All commands previewed in confirmation dialog before execution
- No arbitrary code execution — only commands defined in catalog
- Custom extensions: user provides URL, user is responsible
- Pre-flight checks prevent execution of unavailable tools
- Config backup before every modification
- All subprocess calls use explicit argument lists (no shell=True)

## Out of Scope (Future Iterations)

- **Update/upgrade** — detect and apply updates for installed extensions
- **Version pinning** — pin specific versions of extensions
- **Extension sharing** — export/import extension configurations
- **Remote catalog** — fetch catalog from a remote registry/API
- **Dependency resolution** — auto-install dependencies
- **Extension marketplace** — community-submitted extensions with reviews
