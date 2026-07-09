"""Form schemas for structured editing per provider."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldSpec:
    path: tuple[Any, ...]
    label: str
    kind: str = "text"          # 'text' | 'password' | 'select' | 'textarea'
    description: str = ""
    options: tuple[str, ...] = ()
    placeholder: str = ""


@dataclass(frozen=True)
class ProviderSchema:
    fields: tuple[FieldSpec, ...] = ()
    has_env_editor: bool = False
    has_qwen_model_providers: bool = False
    has_opencode_providers: bool = False    # OpenCode + Kilo nested provider.<id>.models
    has_claude_permissions: bool = False    # allow/deny string lists
    has_claude_hooks: bool = False          # hooks editor
    has_oauth: bool = False                 # OAuth-based login (e.g., Claude Code `claude auth login`)
    has_pi_multifile: bool = False          # Pi coding agent multi-file support (settings/models/mcp)
    has_pi_models: bool = False             # Pi models with dynamic UI (like OpenCode providers)


SCHEMAS: dict[str, ProviderSchema] = {
    "claude": ProviderSchema(
        has_oauth=True,
        fields=(
            FieldSpec(
                path=("env", "ANTHROPIC_BASE_URL"),
                label="Anthropic base URL",
                placeholder="https://api.anthropic.com",
            ),
            FieldSpec(
                path=("env", "ANTHROPIC_AUTH_TOKEN"),
                label="Auth token",
                kind="password",
                placeholder="sk-...",
            ),
            FieldSpec(
                path=("env", "ANTHROPIC_DEFAULT_OPUS_MODEL"),
                label="Default Opus model",
            ),
            FieldSpec(
                path=("env", "ANTHROPIC_DEFAULT_SONNET_MODEL"),
                label="Default Sonnet model",
            ),
            FieldSpec(
                path=("env", "ANTHROPIC_DEFAULT_HAIKU_MODEL"),
                label="Default Haiku model",
            ),
            FieldSpec(
                path=("model",),
                label="Active model alias",
                kind="select",
                options=("", "haiku", "sonnet", "opus"),
            ),
            FieldSpec(
                path=("permissions", "defaultMode"),
                label="Permissions default mode",
                kind="select",
                options=("", "default", "plan", "acceptAll"),
            ),
        ),
        has_env_editor=True,
        has_claude_permissions=True,
        has_claude_hooks=True,
    ),
    "qwen": ProviderSchema(
        has_env_editor=True,
        has_qwen_model_providers=True,
    ),
    "codex": ProviderSchema(
        fields=(
            FieldSpec(
                path=("model_reasoning_effort",),
                label="Reasoning effort",
                kind="select",
                options=("", "low", "medium", "high"),
            ),
        ),
    ),
    "opencode": ProviderSchema(
        fields=(
            FieldSpec(
                path=("$schema",),
                label="Schema URL",
                placeholder="https://opencode.ai/config.json",
            ),
            FieldSpec(path=("model",), label="Default model", placeholder="anthropic/claude-sonnet-4"),
        ),
        has_opencode_providers=True,
    ),
    "kilo": ProviderSchema(
        fields=(
            FieldSpec(
                path=("$schema",),
                label="Schema URL",
                placeholder="https://app.kilo.ai/config.json",
            ),
        ),
        has_opencode_providers=True,
    ),
    "gemini": ProviderSchema(
        fields=(
            FieldSpec(path=("apiKey",), label="API key", kind="password", placeholder="..."),
            FieldSpec(path=("model",), label="Model", placeholder="gemini-2.5-pro"),
        ),
        has_env_editor=True,
    ),
    "cursor": ProviderSchema(
        fields=(
            FieldSpec(path=("ai.provider",), label="AI provider"),
            FieldSpec(path=("ai.apiKey",), label="API key", kind="password"),
        ),
    ),
    "qwenpaw": ProviderSchema(),
    "pi": ProviderSchema(
        has_pi_multifile=True,
        fields=(
            FieldSpec(path=("defaultProvider",), label="Default provider", placeholder="anthropic"),
            FieldSpec(path=("defaultModel",), label="Default model", placeholder="claude-sonnet-4"),
            FieldSpec(path=("theme",), label="Theme", kind="select", options=("dark", "light")),
            FieldSpec(path=("quietStartup",), label="Quiet startup", kind="select", options=("true", "false")),
            FieldSpec(path=("enableInstallTelemetry",), label="Enable telemetry", kind="select", options=("true", "false")),
            FieldSpec(path=("defaultProjectTrust",), label="Default project trust", kind="select", options=("ask", "always", "never")),
            FieldSpec(path=("defaultThinkingLevel",), label="Default thinking level", kind="select", options=("low", "medium", "high")),
            FieldSpec(path=("hideThinkingBlock",), label="Hide thinking block", kind="select", options=("true", "false")),
        ),
    ),
    "pi-models": ProviderSchema(
        has_pi_models=True,
    ),
    "pi-mcp": ProviderSchema(),
}


def schema_for(key: str) -> ProviderSchema:
    return SCHEMAS.get(key, ProviderSchema())
