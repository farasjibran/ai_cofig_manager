from django.db import models


class Profile(models.Model):
    """A saved snapshot of a provider config that can be restored on demand."""

    provider_key = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=120)
    content = models.TextField(blank=True)
    fmt = models.CharField(max_length=8)  # 'json' | 'toml'
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = [("provider_key", "name")]

    def __str__(self) -> str:
        return f"{self.provider_key}/{self.name}"


class PathOverride(models.Model):
    """User-defined custom path for a provider's config file."""

    provider_key = models.CharField(max_length=64, unique=True)
    path = models.CharField(max_length=1024)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.provider_key} → {self.path}"


class OAuthConfig(models.Model):
    """Per-provider OAuth detection settings.

    Defines which CLI command to run and how to parse its JSON output
    to determine login status.  Only used when ``enabled=True``.
    """

    provider_key = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(default=True)
    command = models.CharField(
        max_length=255,
        default="claude auth status",
        help_text="CLI command that outputs JSON with login status.",
    )
    json_path_email = models.CharField(
        max_length=128,
        default="email",
        help_text="JSON key path for user email (dot-separated, e.g. 'user.email').",
    )
    json_path_plan = models.CharField(
        max_length=128,
        default="subscriptionType",
        help_text="JSON key path for plan name.",
    )
    json_path_org = models.CharField(
        max_length=128,
        default="orgName",
        blank=True,
        help_text="JSON key path for organization name (optional).",
    )
    json_path_logged_in = models.CharField(
        max_length=128,
        default="loggedIn",
        help_text="JSON key path for boolean login flag.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"OAuth[{self.provider_key}] enabled={self.enabled} cmd={self.command}"


class TokenCheck(models.Model):
    """History of token/credential health checks per provider."""

    provider_key = models.CharField(max_length=64, db_index=True)
    status = models.CharField(
        max_length=24,
        choices=[
            ("ok", "OK"),
            ("invalid", "Invalid"),
            ("expired", "Expired"),
            ("missing", "Missing"),
            ("error", "Error"),
            ("untested", "Untested"),
        ],
    )
    message = models.CharField(max_length=255, blank=True)
    auth_type = models.CharField(
        max_length=32, blank=True,
        help_text="OAuth, API key, or none",
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Token expiry time (OAuth tokens)",
    )
    latency_ms = models.IntegerField(null=True, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [
            models.Index(fields=["provider_key", "-checked_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider_key} {self.status} @ {self.checked_at:%Y-%m-%d %H:%M}"
