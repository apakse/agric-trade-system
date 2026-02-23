from django.db import models

# Create your models here.
# from django.db import models


class HSCode(models.Model):
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField()

    # First 2 digits (chapter)
    chapter = models.CharField(max_length=2, db_index=True)

    # Optional: 4-digit group
    heading = models.CharField(max_length=4, db_index=True, blank=True)

    # Optional: 6-digit subheading
    subheading = models.CharField(max_length=6, db_index=True, blank=True)

    def save(self, *args, **kwargs):
        self.chapter = self.code[:2]
        self.heading = self.code[:4]
        self.subheading = self.code[:6]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code}"


# trade data models
class TradeData(models.Model):
    TRADE_TYPE_CHOICES = [
        ("IMPORT", "Import"),
        ("EXPORT", "Export"),
    ]

    year = models.PositiveSmallIntegerField(db_index=True)
    month = models.PositiveSmallIntegerField(db_index=True)

    trade_type = models.CharField(
        max_length=6, choices=TRADE_TYPE_CHOICES, db_index=True
    )

    hs_code = models.ForeignKey(HSCode, on_delete=models.PROTECT, related_name="trades")

    country = models.CharField(max_length=100, db_index=True)

    quantity = models.DecimalField(max_digits=18, decimal_places=2)
    unit = models.CharField(max_length=20, blank=True, null=True)

    value_usd = models.DecimalField(max_digits=18, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["year", "month"]),
            models.Index(fields=["trade_type"]),
            models.Index(fields=["hs_code", "year"]),
            models.Index(fields=["hs_code", "trade_type"]),
            models.Index(fields=["country"]),
        ]
        ordering = ["-year", "-month"]

    def __str__(self):
        return f"{self.hs_code.code} - {self.trade_type} ({self.year}-{self.month})"
