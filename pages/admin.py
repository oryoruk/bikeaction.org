from django.contrib import admin

from pages.models import LegacyQRCode, LegacyQRCodeScan


class LegacyQRCodeAdmin(admin.ModelAdmin):
    list_display = ["description", "target", "key", "active"]


class LegacyQRCodeScanAdmin(admin.ModelAdmin):
    list_display = ["qr_code", "created_at"]


admin.site.register(LegacyQRCode, LegacyQRCodeAdmin)
admin.site.register(LegacyQRCodeScan, LegacyQRCodeScanAdmin)
