"""Connection tests per provider.

For each provider with a known API shape, derive base URL + auth headers from
the parsed config and probe ``<base>/models`` (or equivalent). Returns a list
of TestResult so providers with multiple sub-providers (Qwen, OpenCode) can
report each one separately.

Uses stdlib ``urllib`` so no new dependency.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .registry import Provider
from .services import parse_text


@dataclass
class TestResult:
    label: str
    url: str
    status: str            # 'ok' | 'auth_failed' | 'error' | 'skipped'
    http_code: int | None
    latency_ms: int
    message: str


def _http_get(url: str, headers: dict[str, str], timeout: float = 8.0):
    req = urllib.request.Request(url, headers=headers, method="GET")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(1024)
            latency = int((time.perf_counter() - start) * 1000)
            return resp.status, "", latency
    except urllib.error.HTTPError as exc:
        latency = int((time.perf_counter() - start) * 1000)
        return exc.code, "", latency


def _classify(http_code: int) -> tuple[str, str]:
    if 200 <= http_code < 300:
        return "ok", "Authenticated"
    if http_code in (401, 403):
        return "auth_failed", f"Auth failed (HTTP {http_code})"
    if http_code == 404:
        return "error", "Endpoint not found (404)"
    return "error", f"HTTP {http_code}"


def _do_test(label: str, base: str, headers: dict[str, str], suffix: str = "/models") -> TestResult:
    url = base.rstrip("/") + suffix
    try:
        code, _, latency = _http_get(url, headers)
    except urllib.error.URLError as exc:
        return TestResult(label, url, "error", None, 0, f"Connection error: {exc.reason}")
    except TimeoutError:
        return TestResult(label, url, "error", None, 0, "Timeout")
    except Exception as exc:                       # pragma: no cover - defensive
        return TestResult(label, url, "error", None, 0, str(exc))
    status, msg = _classify(code)
    return TestResult(label, url, status, code, latency, msg)


# ---------------------------------------------------------------------------
# Per-provider testers
# ---------------------------------------------------------------------------


def test_claude(data: dict) -> list[TestResult]:
    env = data.get("env") or {}
    base = env.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com"
    token = env.get("ANTHROPIC_AUTH_TOKEN")
    if not token:
        return [TestResult("Claude", base, "skipped", None, 0, "No ANTHROPIC_AUTH_TOKEN set")]
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": token,
        "anthropic-version": "2023-06-01",
    }
    return [_do_test("Claude", base, headers)]


def test_qwen(data: dict) -> list[TestResult]:
    env = data.get("env") or {}
    providers = (data.get("modelProviders") or {}).get("openai") or []
    results: list[TestResult] = []
    for p in providers:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id", "?"))
        base = p.get("baseUrl")
        env_key = p.get("envKey")
        if not base or not env_key:
            results.append(TestResult(pid, base or "", "skipped", None, 0, "Missing baseUrl or envKey"))
            continue
        token = env.get(env_key)
        if not token:
            results.append(TestResult(pid, base, "skipped", None, 0, f"env.{env_key} not set"))
            continue
        results.append(_do_test(pid, base, {"Authorization": f"Bearer {token}"}))
    if not results:
        return [TestResult("Qwen", "", "skipped", None, 0, "No model providers configured")]
    return results


def test_opencode_like(data: dict) -> list[TestResult]:
    providers = data.get("provider") or {}
    if not isinstance(providers, dict):
        return [TestResult("provider", "", "error", None, 0, "'provider' key is not an object")]
    results: list[TestResult] = []
    for pid, pdata in providers.items():
        if not isinstance(pdata, dict):
            continue
        opts = pdata.get("options") or {}
        if not isinstance(opts, dict):
            opts = {}
        base = opts.get("baseURL") or opts.get("baseUrl")
        headers = opts.get("headers") if isinstance(opts.get("headers"), dict) else {}
        if not base:
            results.append(TestResult(pid, "", "skipped", None, 0, "no baseURL"))
            continue
        if not headers:
            results.append(TestResult(pid, base, "skipped", None, 0, "no Authorization header"))
            continue
        results.append(_do_test(pid, base, headers))
    if not results:
        return [TestResult("providers", "", "skipped", None, 0, "No providers configured")]
    return results


def test_gemini(data: dict) -> list[TestResult]:
    api_key = data.get("apiKey")
    if not api_key:
        return [TestResult("Gemini", "", "skipped", None, 0, "No apiKey set")]
    base = "https://generativelanguage.googleapis.com/v1beta"
    url = f"{base}/models?key={api_key}"
    try:
        code, _, latency = _http_get(url, {})
    except urllib.error.URLError as exc:
        return [TestResult("Gemini", base, "error", None, 0, f"Connection error: {exc.reason}")]
    except Exception as exc:                       # pragma: no cover
        return [TestResult("Gemini", base, "error", None, 0, str(exc))]
    status, msg = _classify(code)
    return [TestResult("Gemini", base, status, code, latency, msg)]


TESTERS: dict[str, Callable[[dict], list[TestResult]]] = {
    "claude": test_claude,
    "qwen": test_qwen,
    "opencode": test_opencode_like,
    "kilo": test_opencode_like,
    "gemini": test_gemini,
}


def test_provider(provider: Provider, text: str) -> list[TestResult]:
    if not text.strip():
        return [TestResult("config", "", "skipped", None, 0, "Config file is empty")]
    try:
        data = parse_text(text, provider.format)
    except Exception as exc:
        return [TestResult("config", "", "error", None, 0, f"Cannot parse config: {exc}")]
    if not isinstance(data, dict):
        return [TestResult("config", "", "error", None, 0, "Top-level config must be an object")]
    fn = TESTERS.get(provider.key)
    if fn is None:
        return [TestResult(provider.name, "", "skipped", None, 0,
                           "No connection test defined for this provider")]
    try:
        return fn(data)
    except Exception as exc:                       # pragma: no cover - defensive
        return [TestResult("test", "", "error", None, 0, f"Test crashed: {exc}")]
