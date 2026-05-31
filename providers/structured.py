"""Structured-form editing helpers."""

from __future__ import annotations

import json
from typing import Any

from .registry import Provider
from .schema import FieldSpec, ProviderSchema, schema_for
from .services import has_jsonc_artifacts, looks_secret, parse_text, serialize


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------


def get_path(data: Any, path: tuple[Any, ...]) -> Any:
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def set_path(data: dict, path: tuple[Any, ...], value: Any) -> None:
    cur = data
    for key in path[:-1]:
        node = cur.get(key)
        if not isinstance(node, dict):
            node = {}
            cur[key] = node
        cur = node
    cur[path[-1]] = value


def remove_path(data: dict, path: tuple[Any, ...]) -> None:
    cur: Any = data
    for key in path[:-1]:
        if not isinstance(cur, dict):
            return
        cur = cur.get(key)
        if cur is None:
            return
    if isinstance(cur, dict):
        cur.pop(path[-1], None)


# ---------------------------------------------------------------------------
# Build context for rendering
# ---------------------------------------------------------------------------


def build_context(provider: Provider, text: str) -> dict[str, Any]:
    schema = schema_for(provider.key)
    ctx: dict[str, Any] = {
        "schema": schema,
        "field_rows": [],
        "env_rows": [],
        "qwen_rows": [],
        "opencode_providers_json": "[]",
        "claude_allow": [],
        "claude_deny": [],
        "claude_hooks_json": "{}",
        "parse_error": None,
        "jsonc_warning": False,
        "has_structured": (
            bool(schema.fields)
            or schema.has_env_editor
            or schema.has_qwen_model_providers
            or schema.has_opencode_providers
            or schema.has_claude_permissions
            or schema.has_claude_hooks
        ),
    }
    if not ctx["has_structured"]:
        return ctx

    try:
        data = parse_text(text, provider.format) if text.strip() else {}
    except Exception as exc:
        ctx["parse_error"] = str(exc)
        return ctx

    if provider.format == "json" and has_jsonc_artifacts(text):
        ctx["jsonc_warning"] = True

    if not isinstance(data, dict):
        ctx["parse_error"] = "Top-level config is not an object/table."
        return ctx

    rows: list[dict[str, Any]] = []
    for index, spec in enumerate(schema.fields):
        value = get_path(data, spec.path)
        if value is None:
            value = ""
        elif not isinstance(value, (str, int, float, bool)):
            value = ""
        rows.append(
            {
                "index": index,
                "spec": spec,
                "value": "" if value is False or value is None else str(value),
                "options": spec.options,
                "path_label": ".".join(str(p) for p in spec.path),
            }
        )
    ctx["field_rows"] = rows

    if schema.has_env_editor:
        env = data.get("env") or {}
        if isinstance(env, dict):
            ctx["env_rows"] = [
                {
                    "key": k,
                    "value": "" if v is None else str(v),
                    "secret": looks_secret(k),
                }
                for k, v in env.items()
            ]

    if schema.has_qwen_model_providers:
        mp = (data.get("modelProviders") or {}).get("openai") or []
        if isinstance(mp, list):
            ctx["qwen_rows"] = [
                {
                    "id": str(item.get("id", "")),
                    "name": str(item.get("name", "")),
                    "baseUrl": str(item.get("baseUrl", "")),
                    "envKey": str(item.get("envKey", "")),
                }
                for item in mp
                if isinstance(item, dict)
            ]

    if schema.has_opencode_providers:
        providers = data.get("provider") or {}
        out_list: list[dict[str, Any]] = []
        if isinstance(providers, dict):
            for pid, pdata in providers.items():
                if not isinstance(pdata, dict):
                    continue
                opts = pdata.get("options") or {}
                if not isinstance(opts, dict):
                    opts = {}
                headers = opts.get("headers") or {}
                if not isinstance(headers, dict):
                    headers = {}
                models = pdata.get("models") or {}
                model_rows = []
                if isinstance(models, dict):
                    for mid, mdata in models.items():
                        if isinstance(mdata, dict):
                            model_rows.append({"id": mid, "name": str(mdata.get("name", ""))})
                        else:
                            model_rows.append({"id": mid, "name": ""})
                out_list.append(
                    {
                        "id": pid,
                        "name": str(pdata.get("name", "")),
                        "npm": str(pdata.get("npm", "")),
                        "baseUrl": str(opts.get("baseURL", opts.get("baseUrl", ""))),
                        "authHeader": str(headers.get("Authorization", "")),
                        "models": model_rows,
                    }
                )
        ctx["opencode_providers_json"] = json.dumps(out_list, ensure_ascii=False)

    if schema.has_claude_permissions:
        perms = data.get("permissions") or {}
        if isinstance(perms, dict):
            allow = perms.get("allow") or []
            deny = perms.get("deny") or []
            ctx["claude_allow"] = [str(x) for x in allow if isinstance(x, (str, int, float))]
            ctx["claude_deny"] = [str(x) for x in deny if isinstance(x, (str, int, float))]

    if schema.has_claude_hooks:
        hooks = data.get("hooks") or {}
        ctx["claude_hooks_json"] = json.dumps(hooks, ensure_ascii=False, indent=2)

    return ctx


# ---------------------------------------------------------------------------
# Apply POST data
# ---------------------------------------------------------------------------


def apply_post(provider: Provider, current_text: str, post) -> tuple[bool, str, str]:
    schema = schema_for(provider.key)

    try:
        data = parse_text(current_text, provider.format) if current_text.strip() else {}
    except Exception as exc:
        return False, f"Cannot parse existing file: {exc}", current_text
    if not isinstance(data, dict):
        return False, "Top-level config must be an object/table.", current_text

    # 1) Named fields
    for index, spec in enumerate(schema.fields):
        raw = post.get(f"field_{index}", "")
        value = raw.strip()
        if value == "":
            remove_path(data, spec.path)
        else:
            set_path(data, spec.path, _coerce(spec, value))

    # 2) Generic env editor
    if schema.has_env_editor:
        keys = post.getlist("env_key")
        vals = post.getlist("env_value")
        env: dict[str, str] = {}
        for k, v in zip(keys, vals):
            k = k.strip()
            if not k:
                continue
            env[k] = v
        if env:
            data["env"] = env
        else:
            data.pop("env", None)

    # 3) Qwen modelProviders
    if schema.has_qwen_model_providers:
        ids = post.getlist("mp_id")
        names = post.getlist("mp_name")
        urls = post.getlist("mp_baseUrl")
        env_keys = post.getlist("mp_envKey")
        items: list[dict] = []
        for i in range(max(len(ids), len(names), len(urls), len(env_keys))):
            row = {
                "id": ids[i].strip() if i < len(ids) else "",
                "name": names[i].strip() if i < len(names) else "",
                "baseUrl": urls[i].strip() if i < len(urls) else "",
                "envKey": env_keys[i].strip() if i < len(env_keys) else "",
            }
            if not any(row.values()):
                continue
            items.append({k: v for k, v in row.items() if v})
        if items:
            mp = data.get("modelProviders") if isinstance(data.get("modelProviders"), dict) else {}
            mp["openai"] = items
            data["modelProviders"] = mp
        else:
            mp = data.get("modelProviders")
            if isinstance(mp, dict):
                mp.pop("openai", None)
                if not mp:
                    data.pop("modelProviders", None)

    # 4) OpenCode/Kilo providers (rich nested)
    if schema.has_opencode_providers:
        payload = post.get("opencode_providers_json", "[]")
        try:
            providers_list = json.loads(payload) if payload else []
        except json.JSONDecodeError as exc:
            return False, f"Invalid providers JSON payload: {exc}", current_text
        if not isinstance(providers_list, list):
            return False, "Providers payload must be a list.", current_text

        # Preserve any existing provider data we don't manage in the form.
        existing_root = data.get("provider")
        if not isinstance(existing_root, dict):
            existing_root = {}

        new_root: dict[str, dict] = {}
        for entry in providers_list:
            if not isinstance(entry, dict):
                continue
            pid = str(entry.get("id", "")).strip()
            if not pid:
                continue

            existing = existing_root.get(pid) if isinstance(existing_root.get(pid), dict) else {}
            merged: dict[str, Any] = dict(existing)

            name = str(entry.get("name", "")).strip()
            npm = str(entry.get("npm", "")).strip()
            base_url = str(entry.get("baseUrl", "")).strip()
            auth_header = str(entry.get("authHeader", "")).strip()
            models = entry.get("models") or []
            if not isinstance(models, list):
                models = []

            if name:
                merged["name"] = name
            else:
                merged.pop("name", None)
            if npm:
                merged["npm"] = npm
            else:
                merged.pop("npm", None)

            opts = merged.get("options")
            if not isinstance(opts, dict):
                opts = {}
            if base_url:
                opts["baseURL"] = base_url
            else:
                opts.pop("baseURL", None)
                opts.pop("baseUrl", None)

            headers = opts.get("headers") if isinstance(opts.get("headers"), dict) else {}
            if auth_header:
                headers["Authorization"] = auth_header
            else:
                headers.pop("Authorization", None)
            if headers:
                opts["headers"] = headers
            else:
                opts.pop("headers", None)

            if opts:
                merged["options"] = opts
            else:
                merged.pop("options", None)

            existing_models = merged.get("models") if isinstance(merged.get("models"), dict) else {}
            new_models: dict[str, dict] = {}
            for m in models:
                if not isinstance(m, dict):
                    continue
                mid = str(m.get("id", "")).strip()
                if not mid:
                    continue
                mdata = existing_models.get(mid) if isinstance(existing_models.get(mid), dict) else {}
                mdata = dict(mdata)
                mname = str(m.get("name", "")).strip()
                if mname:
                    mdata["name"] = mname
                else:
                    mdata.pop("name", None)
                new_models[mid] = mdata
            if new_models:
                merged["models"] = new_models
            else:
                merged.pop("models", None)

            new_root[pid] = merged

        if new_root:
            data["provider"] = new_root
        else:
            data.pop("provider", None)

    # 5) Claude permissions allow/deny
    if schema.has_claude_permissions:
        allow = [s.strip() for s in post.getlist("perm_allow") if s.strip()]
        deny = [s.strip() for s in post.getlist("perm_deny") if s.strip()]
        perms = data.get("permissions") if isinstance(data.get("permissions"), dict) else {}
        if allow:
            perms["allow"] = allow
        else:
            perms.pop("allow", None)
        if deny:
            perms["deny"] = deny
        else:
            perms.pop("deny", None)
        if perms:
            data["permissions"] = perms
        else:
            data.pop("permissions", None)

    # 6) Claude hooks (raw JSON sub-document)
    if schema.has_claude_hooks:
        raw = post.get("claude_hooks_json", "").strip()
        if not raw:
            data.pop("hooks", None)
        else:
            try:
                hooks = json.loads(raw)
            except json.JSONDecodeError as exc:
                return False, f"Invalid hooks JSON: {exc}", current_text
            if not isinstance(hooks, dict):
                return False, "Hooks must be a JSON object.", current_text
            data["hooks"] = hooks

    try:
        new_text = serialize(data, provider.format)
    except Exception as exc:
        return False, f"Failed to serialize: {exc}", current_text

    return True, "ok", new_text


def _coerce(spec: FieldSpec, value: str):
    if spec.kind == "select" and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value
