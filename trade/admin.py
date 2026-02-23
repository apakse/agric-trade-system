from django.contrib import admin

# Register your models here.
# from django.contrib import admin
from .models import TradeData, HSCode


@admin.register(HSCode)
class HSCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "description")
    search_fields = ("code", "description")
    ordering = ("code",)


@admin.register(TradeData)
class TradeDataAdmin(admin.ModelAdmin):
    list_display = (
        "year",
        "month",
        "trade_type",
        "hs_code",
        "country",
        "quantity",
        "value_usd",
    )

    list_filter = ("year", "month", "trade_type")
    search_fields = ("hs_code__code", "country")
    list_select_related = ("hs_code",)
    list_per_page = 50
