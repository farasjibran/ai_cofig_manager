"""Read-only session data from AI provider filesystems."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


HOME = Path.home()


@dataclass
class SessionEntry:
    """A single session from an AI provider."""
    session_id: str
    provider: str
    cwd: str
    project: str
    started_at: int  # ms timestamp
    updated_at: int  # ms timestamp
    status: str = "idle"
    version: str = ""
    entrypoint: str = ""
    message_count: int = 0
    tool_count: int = 0
    last_messages: list[dict] = field(default_factory=list)

    @property
    def started_dt(self) -> datetime:
        return datetime.fromtimestamp(self.started_at / 1000, tz=timezone.utc)

    @property
    def updated_dt(self) -> datetime:
        return datetime.fromtimestamp(self.updated_at / 1000, tz=timezone.utc)

    @property
    def duration_sec(self) -> int:
        return max(0, (self.updated_at - self.started_at) // 1000)

    @property
    def project_name(self) -> str:
        if self.project:
            return Path(self.project).name
        if self.cwd:
            return Path(self.cwd).name
        return "—"

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "provider": self.provider,
            "cwd": self.cwd,
            "project": self.project,
            "project_name": self.project_name,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "version": self.version,
            "entrypoint": self.entrypoint,
            "message_count": self.message_count,
            "tool_count": self.tool_count,
            "duration_sec": self.duration_sec,
            "last_messages": self.last_messages,
        }


def _parse_jsonl(path: Path, session_id: Optional[str] = None, limit: int = 5) -> tuple[int, int, list[dict]]:
    """Parse history.jsonl, return (message_count, tool_count, last_n_messages)."""
    if not path.exists():
        return 0, 0, []
    msgs, tools = 0, 0
    entries: list[dict] = []
    try:
        for line in reversed(path.read_text().splitlines()):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            msgs += 1
            if "tool" in entry.get("type", "").lower() or "tool_use" in str(entry.get("type", "")):
                tools += 1
            sid = entry.get("sessionId") or entry.get("session_id")
            if session_id and sid and sid != session_id:
                continue
            entries.insert(0, entry)
            if len(entries) >= limit:
                break
    except (OSError, json.JSONDecodeError):
        pass
    return msgs, tools, entries


def _parse_qwen_chat(chat_path: Path, limit: int = 5) -> tuple[int, list[dict]]:
    """Parse Qwen chats/*.jsonl, return (message_count, last_n_messages)."""
    if not chat_path.exists():
        return 0, []
    msgs = 0
    entries: list[dict] = []
    try:
        for line in reversed(chat_path.read_text().splitlines()):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            msgs += 1
            # Extract display text
            display = ""
            entry_type = entry.get("type", "")
            if entry_type == "user":
                parts = entry.get("message", {}).get("parts", [])
                for p in parts:
                    if isinstance(p, dict) and "text" in p:
                        display = p["text"]
                        break
            elif entry_type == "model":
                parts = entry.get("message", {}).get("parts", [])
                for p in parts:
                    if isinstance(p, dict) and "text" in p:
                        display = p["text"]
                        break
            elif entry_type == "system":
                display = entry.get("subtype", "system")
            entries.insert(0, {"type": entry_type, "display": display[:200]})
            if len(entries) >= limit:
                break
    except (OSError, json.JSONDecodeError):
        pass
    return msgs, entries


# ── Claude ──────────────────────────────────────────────────────────────────

def read_claude_sessions() -> list[SessionEntry]:
    """Read sessions from ~/.claude/sessions/*.json."""
    sessions_dir = HOME / ".claude" / "sessions"
    history_path = HOME / ".claude" / "history.jsonl"
    entries: list[SessionEntry] = []

    if not sessions_dir.exists():
        return entries

    for f in sessions_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue

        sid = data.get("sessionId", f.stem)
        started = data.get("startedAt", 0)
        updated = data.get("updatedAt", started)

        msgs, tools, last_msgs = _parse_jsonl(history_path, sid, limit=5)

        entries.append(SessionEntry(
            session_id=sid,
            provider="claude",
            cwd=data.get("cwd", ""),
            project=data.get("cwd", ""),
            started_at=started,
            updated_at=updated,
            status=data.get("status", "idle"),
            version=data.get("version", ""),
            entrypoint=data.get("entrypoint", ""),
            message_count=msgs,
            tool_count=tools,
            last_messages=last_msgs,
        ))

    entries.sort(key=lambda e: e.started_at, reverse=True)
    return entries


# ── Qwen ───────────────────────────────────────────────────────────────────

def read_qwen_sessions() -> list[SessionEntry]:
    """Read sessions from ~/.qwen/projects/*/chats/*.jsonl."""
    projects_dir = HOME / ".qwen" / "projects"
    entries: list[SessionEntry] = []

    if not projects_dir.exists():
        return entries

    for proj in projects_dir.iterdir():
        if not proj.is_dir():
            continue

        chats_dir = proj / "chats"
        if not chats_dir.exists():
            continue

        for chat_file in sorted(chats_dir.glob("*.jsonl")):
            sid = chat_file.stem  # UUID without .jsonl
            msgs, last_msgs = _parse_qwen_chat(chat_file, limit=5)

            # Read runtime.json for metadata
            runtime_path = chat_file.with_suffix(".runtime.json")
            started_at = int(proj.stat().st_mtime * 1000)
            version = ""
            cwd = str(proj)
            if runtime_path.exists():
                try:
                    rt = json.loads(runtime_path.read_text())
                    started_at = int(rt.get("started_at", started_at) * 1000)
                    version = rt.get("qwen_version", "")
                    cwd = rt.get("work_dir", cwd)
                except (OSError, json.JSONDecodeError, ValueError):
                    pass

            entries.append(SessionEntry(
                session_id=sid,
                provider="qwen",
                cwd=cwd,
                project=str(proj),
                started_at=started_at,
                updated_at=int(chat_file.stat().st_mtime * 1000),
                status="idle",
                version=version,
                entrypoint="",
                message_count=msgs,
                tool_count=0,
                last_messages=last_msgs,
            ))

    entries.sort(key=lambda e: e.started_at, reverse=True)
    return entries


# ── Codex ───────────────────────────────────────────────────────────────────

def read_codex_sessions() -> list[SessionEntry]:
    """Read sessions from ~/.codex/logs_2.sqlite + history.jsonl."""
    db_path = HOME / ".codex" / "logs_2.sqlite"
    history_path = HOME / ".codex" / "history.jsonl"
    entries: list[SessionEntry] = []

    if not db_path.exists():
        return entries

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT ts, thread_id, level, module_path, file, line, feedback_log_body "
            "FROM logs ORDER BY ts DESC LIMIT 200"
        )
        rows = cur.fetchall()
        conn.close()
    except sqlite3.Error:
        return entries

    if not rows:
        return entries

    # Group by thread_id (session)
    threads: dict[str, list] = {}
    for r in rows:
        tid = r["thread_id"] or "default"
        threads.setdefault(tid, []).append(dict(r))

    # Parse Codex history.jsonl
    msgs, tools, last_msgs = _parse_jsonl(history_path, limit=5)

    for tid, logs in threads.items():
        if not logs:
            continue
        first_ts = logs[-1]["ts"] * 1000
        last_ts = logs[0]["ts"] * 1000
        entries.append(SessionEntry(
            session_id=tid,
            provider="codex",
            cwd="",
            project="",
            started_at=int(first_ts),
            updated_at=int(last_ts),
            status="idle",
            version="",
            entrypoint="",
            message_count=msgs,
            tool_count=tools,
            last_messages=last_msgs,
        ))

    entries.sort(key=lambda e: e.started_at, reverse=True)
    return entries


# ── All providers ───────────────────────────────────────────────────────────

def read_all_sessions() -> dict[str, list[SessionEntry]]:
    """Return {provider_key: [SessionEntry]} for all providers."""
    return {
        "claude": read_claude_sessions(),
        "qwen": read_qwen_sessions(),
        "codex": read_codex_sessions(),
    }
