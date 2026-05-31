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
