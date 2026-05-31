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


SCHEMAS: dict[str, ProviderSchema] = {
    "claude": ProviderSchema(
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
}


def schema_for(key: str) -> ProviderSchema:
    return SCHEMAS.get(key, ProviderSchema())
