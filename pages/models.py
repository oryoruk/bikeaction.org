from django.db import models


class LegacyQRCode(models.Model):
    description = models.CharField(max_length=512)
    target = models.URLField()
    key = models.CharField(max_length=64)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"Legacy QR: {self.description}"


class LegacyQRCodeScan(models.Model):
    qr_code = models.ForeignKey(LegacyQRCode, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
