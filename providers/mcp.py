"""MCP server management — read/write mcpServers from provider config files."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .services import read_text, serialize, write_text


# Map provider → config key for MCP servers
MCP_KEY_MAP: dict[str, str] = {
    "claude": "mcpServers",
    "gemini": "mcp",
    "codex": "mcp_servers",
    "opencode": "mcpServers",
    "qwen": "mcpServers",
    "cursor": "mcpServers",
    "kilo": "mcpServers",
}


@dataclass
class MCPServer:
    """A single MCP server entry."""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str = ""
    server_type: str = ""  # e.g. "stdio" for Claude

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"command": self.command}
        if self.server_type:
            d["type"] = self.server_type
        if self.args:
            d["args"] = self.args
        if self.env:
            d["env"] = self.env
        if self.cwd:
            d["cwd"] = self.cwd
        return d

    @classmethod
    def from_dict(cls, name: str, data: dict) -> MCPServer:
        return cls(
            name=name,
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            cwd=data.get("cwd", ""),
            server_type=data.get("type", ""),
        )


def get_mcp_key(provider_key: str) -> str | None:
    return MCP_KEY_MAP.get(provider_key)


def read_mcp_servers(provider) -> list[MCPServer]:
    """Read MCP servers from a provider's config file."""
    key = get_mcp_key(provider.key)
    if not key:
        return []

    try:
        text = read_text(provider)
        data = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return []

    mcp_data = data.get(key, {})
    if not isinstance(mcp_data, dict):
        return []

    return [
        MCPServer.from_dict(name, val)
        for name, val in mcp_data.items()
        if isinstance(val, dict) and "command" in val
    ]


def write_mcp_servers(provider, servers: list[MCPServer]) -> Path | None:
    """Write MCP servers list back to provider's config file."""
    key = get_mcp_key(provider.key)
    if not key:
        return None

    try:
        text = read_text(provider)
        data = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return None

    data[key] = {s.name: s.to_dict() for s in servers}

    new_text = serialize(data, provider.format)
    return write_text(provider, new_text, do_backup=True)
