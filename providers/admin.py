from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("provider_key", "name", "fmt", "updated_at")
    list_filter = ("provider_key", "fmt")
    search_fields = ("provider_key", "name", "note")
