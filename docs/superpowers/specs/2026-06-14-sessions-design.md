# Sessions Browser — Design Spec

## Goal

Add session browsing capability to AI Config Manager: view all sessions per provider, with metadata, chat preview, and stats summary.

## Scope

### A. Tab "Sessions" in provider detail (`/p/<key>/`)
- Only shown for providers that have session data: Claude, Qwen, Codex
- Lists all sessions for that provider

### B. Page `/sessions/`
- Shows all providers' sessions in one view
- Tab filter by provider + search by project name
- Sort by most recent

### C. Session Detail (`/sessions/<provider>/<session_id>/`)
- Full chat history page (separate route)
- Metadata strip: started, last activity, duration, message count
- Details: version, cwd, entrypoint, status
- Full chat: all messages chronologically, role badges (You/AI/Sys), scrollable
- Back button → back to sessions list

## Data Sources

| Provider | Sessions | History | Stats |
|---|---|---|---|
| Claude | `~/.claude/sessions/*.json` + `~/.claude/projects/*/` | `~/.claude/history.jsonl` | `~/.claude/stats-cache.json` |
| Qwen | `~/.qwen/projects/*/` dirs | — | — |
| Codex | `~/.codex/logs_2.sqlite` | `~/.codex/history.jsonl` | — |
| Others | ❌ | ❌ | ❌ |

## No Database Changes

All data is read-only from filesystem. No new models.

## Layout

### `/p/<key>/` tab "Sessions"
- Shown only if provider has session data
- Simple table: Project | Started | Status | Duration | Messages

### `/sessions/` page
- Header + "All Providers" tab group (includes providers with no data, grayed out)
- Search box for project name
- Table: Project | Started | Last Activity | Status | Duration | Messages
- Project name is a link to `/sessions/<provider>/<session_id>/`

### `/sessions/<provider>/<session_id>/` (new)
- Full chat history page
- Metadata strip: started, last activity, duration, message count
- Details: version, cwd, entrypoint, status
- Full chat: all messages chronologically, role badges (You/AI/Sys), scrollable max-h-[70vh]
- Back button → back to sessions list

## Components

### `providers/sessions.py`
- `SessionEntry` dataclass: sessionId, cwd, project, startedAt, updatedAt, status, version, entrypoint, messageCount, duration, lastMessages, tools
- `read_claude_sessions()` → list[SessionEntry]
- `read_qwen_sessions()` → list[SessionEntry]
- `read_codex_sessions()` → list[SessionEntry]
- `get_session_stats(session, history_path)` → dict

### `providers/views.py`
- `sessions_view(request)` → GET `/sessions/`
- `provider_sessions(request, key)` → GET `/p/<key>/sessions/`
- `session_detail(request, provider, session_id)` → GET `/sessions/<provider>/<session_id>/`
- `_load_full_chat(provider, session_id, cwd)` → list of formatted messages

### `providers/urls.py`
- `path("sessions/", views.sessions_view, name="sessions")`
- `path("p/<str:key>/sessions/", views.provider_sessions, name="provider_sessions")`
- `path("sessions/<str:provider>/<str:session_id>/", views.session_detail, name="session_detail")`

### `templates/providers/sessions.html`
- Alpine.js tabs + search
- Session table with project name as link to detail page

### `templates/providers/session_detail.html`
- Full chat history page (new)
- Session table with expandable rows

### `templates/providers/_session_detail.html`
- Partial for expanded session detail

## Implementation Order

1. `providers/sessions.py` — reader functions
2. `providers/urls.py` — add routes
3. `providers/views.py` — view functions
4. `templates/providers/sessions.html` — main page
5. `providers/detail.html` — add Sessions tab
6. Update `CLAUDE.md`
