"""Extension discovery and management for AI providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .registry import Provider, get_provider


    


@dataclass
class Extension:
    """Represents a skill, agent, MCP, hook, or plugin."""

    provider_key: str
    ext_type: Literal["skill", "agent", "mcp", "hook", "plugin"]
    name: str
    path: str
    description: str = ""
    enabled: bool = True
    metadata: dict | None = None

    @property
    def provider(self) -> Provider | None:
        return get_provider(self.provider_key)


# Explanatory labels for each extension type
EXTENSION_LABELS = {
    "skill": {
        "title": "Skills",
        "description": "Custom commands that AI can invoke",
        "example": "e.g., /review-code, /refactor, /debug-issue",
        "format": "Folder with SKILL.md containing instructions",
    },
    "agent": {
        "title": "Agents",
        "description": "AI personas with separate workspaces & configs",
        "example": "e.g., QA Agent for testing, Dev Agent for coding",
        "format": "Profile with dedicated workspace directory",
    },
    "mcp": {
        "title": "MCP (Model Context Protocol)",
        "description": "External tools accessible via standard protocol",
        "example": "e.g., code-review-graph, filesystem, github",
        "format": "JSON config with command + args",
    },
    "hook": {
        "title": "Hooks",
        "description": "Scripts that run automatically on events",
        "example": "e.g., PostToolUse (after AI uses tool), SessionStart (on session start)",
        "format": "Shell script or JS file",
    },
    "plugin": {
        "title": "Plugins",
        "description": "Extensions that add features to provider",
        "example": "e.g., custom syntax highlighter, IDE integrations",
        "format": "Package in plugins/ folder",
    },
}


def discover_extensions() -> list[Extension]:
    """Scan all providers and return their extensions."""
    extensions: list[Extension] = []

    # Claude Code
    claude = get_provider("claude")
    if claude and claude.exists:
        extensions.extend(_discover_claude(claude))

    # Qwen
    qwen = get_provider("qwen")
    if qwen and qwen.exists:
        extensions.extend(_discover_qwen(qwen))

    # Gemini CLI
    gemini = get_provider("gemini")
    if gemini and gemini.exists:
        extensions.extend(_discover_gemini(gemini))

    # QwenPaw
    qwenpaw = get_provider("qwenpaw")
    if qwenpaw and qwenpaw.exists:
        extensions.extend(_discover_qwenpaw(qwenpaw))

    # Codex
    codex = get_provider("codex")
    if codex and codex.exists:
        extensions.extend(_discover_codex(codex))

    # OpenCode
    opencode = get_provider("opencode")
    if opencode and opencode.exists:
        extensions.extend(_discover_opencode(opencode))

    # Kilo
    kilo = get_provider("kilo")
    if kilo and kilo.exists:
        extensions.extend(_discover_kilo(kilo))

    return sorted(extensions, key=lambda e: (e.provider_key, e.ext_type, e.name))


def _discover_claude(provider: Provider) -> list[Extension]:
    """Discover Claude Code extensions."""
    extensions: list[Extension] = []
    base = provider.path.parent  # ~/.claude/

    # Skills
    skills_dir = base / "skills"
    if skills_dir.is_dir():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                skill_md = skill_dir / "SKILL.md"
                desc = ""
                if skill_md.exists():
                    try:
                        content = skill_md.read_text(errors="ignore")
                        # Extract first line or description
                        for line in content.splitlines():
                            if line.strip() and not line.startswith("#"):
                                desc = line.strip()[:100]
                                break
                    except Exception:
                        pass
                extensions.append(
                    Extension(
                        provider_key="claude",
                        ext_type="skill",
                        name=skill_dir.name,
                        path=str(skill_dir),
                        description=desc,
                    )
                )

    # Hooks
    hooks_dir = base / "hooks"
    if hooks_dir.is_dir():
        for hook_file in hooks_dir.iterdir():
            if hook_file.is_file() and hook_file.suffix in (".js", ".sh", ".ps1", ".py"):
                extensions.append(
                    Extension(
                        provider_key="claude",
                        ext_type="hook",
                        name=hook_file.stem,
                        path=str(hook_file),
                        description=f"{hook_file.suffix} script",
                    )
                )

    # MCP from settings.json
    try:
        data = json.loads(provider.path.read_text())
        mcp_servers = data.get("mcpServers", {})
        for name, config in mcp_servers.items():
            command = config.get("command", "")
            args = config.get("args", [])
            extensions.append(
                Extension(
                    provider_key="claude",
                    ext_type="mcp",
                    name=name,
                    path=str(provider.path),
                    description=command,
                    metadata=config,
                )
            )
    except Exception:
        pass

    return extensions


def _discover_qwen(provider: Provider) -> list[Extension]:
    """Discover Qwen extensions."""
    extensions: list[Extension] = []
    base = provider.path.parent  # ~/.qwen/

    # Skills
    skills_dir = base / "skills"
    if skills_dir.is_dir():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                extensions.append(
                    Extension(
                        provider_key="qwen",
                        ext_type="skill",
                        name=skill_dir.name,
                        path=str(skill_dir),
                    )
                )

    # MCP from settings.json
    try:
        data = json.loads(provider.path.read_text())
        mcp_servers = data.get("mcpServers", data.get("mcp", {}))
        for name, config in mcp_servers.items():
            extensions.append(
                Extension(
                    provider_key="qwen",
                    ext_type="mcp",
                    name=name,
                    path=str(provider.path),
                    description=config.get("command", ""),
                    metadata=config,
                )
            )
    except Exception:
        pass

    return extensions


def _discover_gemini(provider: Provider) -> list[Extension]:
    """Discover Gemini CLI extensions."""
    extensions: list[Extension] = []
    base = provider.path.parent  # ~/.gemini/

    # Skills
    skills_dir = base / "skills"
    if skills_dir.is_dir():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                extensions.append(
                    Extension(
                        provider_key="gemini",
                        ext_type="skill",
                        name=skill_dir.name,
                        path=str(skill_dir),
                    )
                )

    # Hooks
    hooks_dir = base / "hooks"
    if hooks_dir.is_dir():
        for hook_file in hooks_dir.iterdir():
            if hook_file.is_file() and hook_file.suffix in (".sh", ".bash"):
                extensions.append(
                    Extension(
                        provider_key="gemini",
                        ext_type="hook",
                        name=hook_file.stem,
                        path=str(hook_file),
                        description=f"{hook_file.suffix} script",
                    )
                )

    # MCP from settings.json
    try:
        data = json.loads(provider.path.read_text())
        mcp_servers = data.get("mcpServers", {})
        for name, config in mcp_servers.items():
            command = config.get("command", "")
            args = config.get("args", [])
            extensions.append(
                Extension(
                    provider_key="gemini",
                    ext_type="mcp",
                    name=name,
                    path=str(provider.path),
                    description=command,
                    metadata=config,
                )
            )
    except Exception:
        pass

    return extensions


def _discover_qwenpaw(provider: Provider) -> list[Extension]:
    """Discover QwenPaw extensions."""
    extensions: list[Extension] = []
    base = provider.path.parent  # ~/.qwenpaw/

    # Skills (skill_pool)
    skill_pool = base / "skill_pool"
    if skill_pool.is_dir():
        for skill_dir in skill_pool.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                extensions.append(
                    Extension(
                        provider_key="qwenpaw",
                        ext_type="skill",
                        name=skill_dir.name,
                        path=str(skill_dir),
                    )
                )

    # Agents from config.json
    try:
        data = json.loads(provider.path.read_text())
        agents = data.get("agents", {})
        profiles = agents.get("profiles", {})
        for agent_id, agent_config in profiles.items():
            workspace = agent_config.get("workspace_dir", "")
            extensions.append(
                Extension(
                    provider_key="qwenpaw",
                    ext_type="agent",
                    name=agent_id,
                    path=workspace,
                    description=f"Workspace: {Path(workspace).name}",
                    enabled=agent_config.get("enabled", True),
                    metadata=agent_config,
                )
            )
    except Exception:
        pass

    # MCP from config.json
    try:
        data = json.loads(provider.path.read_text())
        mcp = data.get("mcp", {})
        for name, config in mcp.items():
            extensions.append(
                Extension(
                    provider_key="qwenpaw",
                    ext_type="mcp",
                    name=name,
                    path=str(provider.path),
                    description=config.get("command", ""),
                    metadata=config,
                )
            )
    except Exception:
        pass

    return extensions


def _discover_codex(provider: Provider) -> list[Extension]:
    """Discover Codex extensions (hooks only)."""
    extensions: list[Extension] = []
    hooks_file = provider.path.parent / "hooks.json"

    if hooks_file.exists():
        try:
            data = json.loads(hooks_file.read_text())
            hooks = data.get("hooks", {})
            for event_name, hook_list in hooks.items():
                for i, hook_config in enumerate(hook_list):
                    matcher = hook_config.get("matcher", "")
                    hook_cmds = hook_config.get("hooks", [])
                    for j, cmd_config in enumerate(hook_cmds):
                        cmd = cmd_config.get("command", "")[:50]
                        extensions.append(
                            Extension(
                                provider_key="codex",
                                ext_type="hook",
                                name=f"{event_name}_{matcher}_{i}_{j}",
                                path=str(hooks_file),
                                description=f"{event_name} → {matcher}: {cmd}...",
                                metadata=cmd_config,
                            )
                        )
        except Exception:
            pass

    return extensions


def _discover_opencode(provider: Provider) -> list[Extension]:
    """Discover OpenCode extensions (plugins only)."""
    extensions: list[Extension] = []
    plugins_dir = provider.path.parent / "plugins"

    if plugins_dir.is_dir():
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith("."):
                extensions.append(
                    Extension(
                        provider_key="opencode",
                        ext_type="plugin",
                        name=plugin_dir.name,
                        path=str(plugin_dir),
                    )
                )

    return extensions


def _discover_kilo(provider: Provider) -> list[Extension]:
    """Discover Kilo extensions (plugins only)."""
    extensions: list[Extension] = []
    plugins_dir = provider.path.parent / "plugins"

    if plugins_dir.is_dir():
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith("."):
                extensions.append(
                    Extension(
                        provider_key="kilo",
                        ext_type="plugin",
                        name=plugin_dir.name,
                        path=str(plugin_dir),
                    )
                )

    return extensions


