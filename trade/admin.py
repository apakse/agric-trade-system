from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect

# from django.contrib import messages
from .models import TradeData, HSCode
from .views import TradeUploadView

# ── Rebrand the admin site ──────────────────────────────────────────
admin.site.site_header = "MOFA SRID Trade Dashboard"
admin.site.site_title = "Trade Dashboard Admin"
admin.site.index_title = "Welcome to Trade Dashboard Admin"


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


change_list_template = "admin/trade/change_list.html"


def get_urls(self):
    urls = super().get_urls()
    custom_urls = [
        path(
            "upload-data/",
            self.admin_site.admin_view(self.upload_data),
            name="trade-upload-data",
        ),
    ]
    return custom_urls + urls


def upload_data(self, request):
    view = TradeUploadView()

    if request.method == "POST":
        return view.post(request)

    return view.get(request)
