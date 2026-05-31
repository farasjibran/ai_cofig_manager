from __future__ import annotations

import difflib
import os
import shutil

from django.contrib import messages
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ConfigEditForm
from .models import PathOverride, Profile
from .registry import PROVIDER_MAP, all_providers, default_path, get_provider
from .services import (
    ConfigParseError,
    backup_file,
    find_backup,
    list_backups,
    mask_text,
    parse_text,
    read_text,
    serialize,
    validate_text,
    write_text,
)
from .connection import test_provider as run_connection_test
from .structured import apply_post, build_context


def _file_signature(provider) -> dict:
    """Return mtime + size for the provider's config file (or zero if missing)."""
    if not provider.path.exists():
        return {"mtime": 0, "size": 0}
    st = provider.path.stat()
    return {"mtime": int(st.st_mtime), "size": st.st_size}


def index(request):
    items = []
    for p in all_providers():
        size = p.path.stat().st_size if p.exists else 0
        backups = list_backups(p)
        profiles = list(Profile.objects.filter(provider_key=p.key))
        items.append(
            {
                "provider": p,
                "size": size,
                "backup_count": len(backups),
                "profile_count": len(profiles),
                "profiles": profiles,
            }
        )
    return render(request, "providers/index.html", {"items": items})


def detail(request, key: str):
    provider = get_provider(key)
    if provider is None:
        raise Http404(f"Unknown provider: {key}")

    if request.method == "POST":
        form = ConfigEditForm(request.POST)
        if form.is_valid():
            text = form.cleaned_data["content"] or ""
            create_backup = form.cleaned_data["create_backup"]
            ok, msg = validate_text(text, provider.format)
            if not ok:
                messages.error(request, f"Invalid {provider.format.upper()}: {msg}")
            else:
                try:
                    backup = write_text(provider, text, do_backup=create_backup)
                except OSError as exc:
                    messages.error(request, f"Failed to write file: {exc}")
                else:
                    if backup:
                        messages.success(request, f"Saved. Backup at {backup.name}")
                    else:
                        messages.success(request, "Saved.")
                    return redirect(reverse("provider_detail", args=[key]))
    else:
        form = ConfigEditForm(initial={"content": read_text(provider)})

    raw_text = form["content"].value() or ""
    masked_preview = mask_text(raw_text, provider.format) if raw_text else ""
    structured_ctx = build_context(provider, raw_text)
    file_sig = _file_signature(provider)

    return render(
        request,
        "providers/detail.html",
        {
            "provider": provider,
            "form": form,
            "raw_text": raw_text,
            "masked_preview": masked_preview,
            "backups": list_backups(provider),
            "profiles": Profile.objects.filter(provider_key=provider.key),
            "structured": structured_ctx,
            "file_sig": file_sig,
        },
    )


@require_POST
def validate(request, key: str):
    provider = get_provider(key)
    if provider is None:
        raise Http404
    text = request.POST.get("content", "")
    ok, msg = validate_text(text, provider.format)
    return JsonResponse({"ok": ok, "message": msg, "format": provider.format})


def _build_diff(old: str, new: str, label: str) -> str:
    diff_lines = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{label}",
        tofile=f"b/{label}",
        n=3,
    )
    return "".join(diff_lines)


@require_POST
def diff_preview(request, key: str):
    """Return a unified diff between proposed raw content and disk."""
    provider = get_provider(key)
    if provider is None:
        raise Http404
    new_text = request.POST.get("content", "")
    old_text = read_text(provider)
    diff = _build_diff(old_text, new_text, provider.path.name)
    return JsonResponse(
        {
            "ok": True,
            "diff": diff,
            "unchanged": old_text == new_text,
            "format": provider.format,
        }
    )


@require_POST
def structured_diff(request, key: str):
    """Apply structured POST to current file in-memory and return a diff."""
    provider = get_provider(key)
    if provider is None:
        raise Http404
    current = read_text(provider)
    ok, msg, new_text = apply_post(provider, current, request.POST)
    if not ok:
        return JsonResponse({"ok": False, "message": msg})
    diff = _build_diff(current, new_text, provider.path.name)
    return JsonResponse(
        {
            "ok": True,
            "diff": diff,
            "unchanged": current == new_text,
            "format": provider.format,
        }
    )


def file_signature(request, key: str):
    """GET: return current mtime+size for change detection polling."""
    provider = get_provider(key)
    if provider is None:
        raise Http404
    return JsonResponse(_file_signature(provider))


def connection_test(request, key: str):
    provider = get_provider(key)
    if provider is None:
        raise Http404
    text = read_text(provider)
    results = run_connection_test(provider, text)
    return JsonResponse(
        {
            "results": [
                {
                    "label": r.label,
                    "url": r.url,
                    "status": r.status,
                    "http_code": r.http_code,
                    "latency_ms": r.latency_ms,
                    "message": r.message,
                }
                for r in results
            ]
        }
    )


def download(request, key: str):
    provider = get_provider(key)
    if provider is None:
        raise Http404
    text = read_text(provider)
    if not text:
        text = serialize({}, provider.format)
    response = HttpResponse(text, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{provider.path.name}"'
    return response


@require_POST
def reload_from_disk(request, key: str):
    provider = get_provider(key)
    if provider is None:
        raise Http404
    messages.info(request, "Reloaded from disk.")
    return redirect(reverse("provider_detail", args=[key]))


@require_POST
def save_structured(request, key: str):
    provider = get_provider(key)
    if provider is None:
        raise Http404
    current = read_text(provider)
    ok, msg, new_text = apply_post(provider, current, request.POST)
    if not ok:
        messages.error(request, msg)
        return redirect(reverse("provider_detail", args=[key]))
    create_backup = request.POST.get("create_backup") in ("on", "true", "1")
    try:
        backup = write_text(provider, new_text, do_backup=create_backup)
    except OSError as exc:
        messages.error(request, f"Failed to write file: {exc}")
        return redirect(reverse("provider_detail", args=[key]))
    if backup:
        messages.success(request, f"Saved structured changes. Backup at {backup.name}")
    else:
        messages.success(request, "Saved structured changes.")
    return redirect(reverse("provider_detail", args=[key]))


@require_POST
def generate_template(request, key: str):
    provider = get_provider(key)
    if provider is None:
        raise Http404
    template = STARTER_TEMPLATES.get(key, {})
    text = serialize(template, provider.format)
    try:
        write_text(provider, text, do_backup=True)
    except OSError as exc:
        messages.error(request, f"Failed to write template: {exc}")
    else:
        messages.success(request, "Template generated.")
    return redirect(reverse("provider_detail", args=[key]))


# ---------------------------------------------------------------------------
# Backup actions
# ---------------------------------------------------------------------------


@require_POST
def restore_backup(request, key: str, filename: str):
    provider = get_provider(key)
    if provider is None:
        raise Http404
    backup_path = find_backup(provider, filename)
    if backup_path is None:
        raise Http404("Backup not found")
    # Backup current state before restoring, so the action is reversible.
    if provider.path.exists():
        backup_file(provider.path)
    provider.path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, provider.path)
    messages.success(request, f"Restored from {backup_path.name}")
    return redirect(reverse("provider_detail", args=[key]))


@require_POST
def delete_backup(request, key: str, filename: str):
    provider = get_provider(key)
    if provider is None:
        raise Http404
    backup_path = find_backup(provider, filename)
    if backup_path is None:
        raise Http404("Backup not found")
    backup_path.unlink()
    messages.success(request, f"Deleted backup {backup_path.name}")
    return redirect(reverse("provider_detail", args=[key]))


# ---------------------------------------------------------------------------
# Profile actions
# ---------------------------------------------------------------------------


@require_POST
def save_profile(request, key: str):
    provider = get_provider(key)
    if provider is None:
        raise Http404
    name = (request.POST.get("name") or "").strip()
    note = (request.POST.get("note") or "").strip()
    content = request.POST.get("content") or read_text(provider)

    if not name:
        messages.error(request, "Profile name is required.")
        return redirect(reverse("provider_detail", args=[key]))

    ok, msg = validate_text(content, provider.format)
    if not ok:
        messages.error(request, f"Cannot save profile: invalid {provider.format.upper()}: {msg}")
        return redirect(reverse("provider_detail", args=[key]))

    profile, created = Profile.objects.update_or_create(
        provider_key=key,
        name=name,
        defaults={"content": content, "fmt": provider.format, "note": note},
    )
    messages.success(
        request,
        f"Profile '{profile.name}' {'created' if created else 'updated'}.",
    )
    return redirect(reverse("provider_detail", args=[key]))


@require_POST
def apply_profile(request, key: str, pid: int):
    provider = get_provider(key)
    if provider is None:
        raise Http404
    profile = get_object_or_404(Profile, pk=pid, provider_key=key)
    backup = write_text(provider, profile.content, do_backup=True)
    if backup:
        messages.success(
            request,
            f"Applied profile '{profile.name}'. Previous file backed up to {backup.name}.",
        )
    else:
        messages.success(request, f"Applied profile '{profile.name}'.")
    return redirect(reverse("provider_detail", args=[key]))


@require_POST
def delete_profile(request, key: str, pid: int):
    provider = get_provider(key)
    if provider is None:
        raise Http404
    profile = get_object_or_404(Profile, pk=pid, provider_key=key)
    name = profile.name
    profile.delete()
    messages.success(request, f"Deleted profile '{name}'.")
    return redirect(reverse("provider_detail", args=[key]))


# ---------------------------------------------------------------------------
# Starter templates per provider — minimal, sane defaults.
# ---------------------------------------------------------------------------

def connection_test(request, key: str):
    provider = get_provider(key)
    if provider is None:
        raise Http404
    text = read_text(provider)
    results = run_connection_test(provider, text)
    return JsonResponse(
        {
            "results": [
                {
                    "label": r.label,
                    "url": r.url,
                    "status": r.status,
                    "http_code": r.http_code,
                    "latency_ms": r.latency_ms,
                    "message": r.message,
                }
                for r in results
            ]
        }
    )


# ---------------------------------------------------------------------------
# Settings page — custom paths per provider
# ---------------------------------------------------------------------------


def settings_view(request):
    """List all providers with current path + override status."""
    overrides = {o.provider_key: o for o in PathOverride.objects.all()}
    rows = []
    for base in PROVIDER_MAP.values():
        eff = get_provider(base.key) or base
        ovr = overrides.get(base.key)
        rows.append(
            {
                "key": base.key,
                "name": base.name,
                "format": base.format,
                "default_path": str(default_path(base.key) or ""),
                "current_path": str(eff.path),
                "is_override": bool(ovr),
                "exists": eff.exists,
            }
        )
    import platform as _platform
    return render(
        request,
        "providers/settings.html",
        {
            "rows": rows,
            "system": _platform.system(),
        },
    )


@require_POST
def settings_save(request):
    key = request.POST.get("provider_key", "").strip()
    raw_path = (request.POST.get("path") or "").strip()
    if key not in PROVIDER_MAP:
        messages.error(request, f"Unknown provider: {key}")
        return redirect(reverse("settings"))
    if not raw_path:
        # Empty input means "reset to default"
        PathOverride.objects.filter(provider_key=key).delete()
        messages.success(request, f"Reset {key} to default path.")
        return redirect(reverse("settings"))
    expanded = os.path.expanduser(os.path.expandvars(raw_path))
    PathOverride.objects.update_or_create(
        provider_key=key,
        defaults={"path": expanded},
    )
    messages.success(request, f"Saved custom path for {key}: {expanded}")
    return redirect(reverse("settings"))


@require_POST
def settings_reset(request, key: str):
    if key not in PROVIDER_MAP:
        raise Http404
    deleted, _ = PathOverride.objects.filter(provider_key=key).delete()
    if deleted:
        messages.success(request, f"Reset {key} to default path.")
    return redirect(reverse("settings"))


STARTER_TEMPLATES: dict[str, dict] = {
    "claude": {
        "env": {
            "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
            "ANTHROPIC_AUTH_TOKEN": "sk-...",
        },
        "model": "sonnet",
        "permissions": {
            "allow": ["Read(**)"],
            "deny": ["Bash(rm -rf *)"],
            "defaultMode": "plan",
        },
    },
    "qwen": {
        "env": {"DASHSCOPE_API_KEY": "sk-..."},
        "modelProviders": {
            "openai": [
                {
                    "id": "qwen-max",
                    "name": "Qwen Max",
                    "baseUrl": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
                    "envKey": "DASHSCOPE_API_KEY",
                }
            ]
        },
    },
    "codex": {
        "model_reasoning_effort": "high",
        "projects": {},
    },
    "opencode": {
        "$schema": "https://opencode.ai/config.json",
        "model": "anthropic/claude-sonnet-4",
    },
    "gemini": {
        "apiKey": "...",
        "model": "gemini-2.5-pro",
    },
    "cursor": {
        "ai.provider": "anthropic",
        "ai.apiKey": "sk-...",
    },
    "kilo": {
        "apiProvider": "anthropic",
        "apiKey": "sk-...",
    },
    "qwenpaw": {
        "providers": [],
    },
}
