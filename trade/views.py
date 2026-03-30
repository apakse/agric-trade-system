from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.core.files.storage import default_storage

import pandas as pd
import io

from .models import TradeData, HSCode
from .forms import TradeUploadForm
from django.views.generic import ListView
from django.db.models import Q
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.db.models import F, Value
from django.db.models.functions import Concat, Cast
from django.db.models import DateField
import calendar
import csv
from django.http import HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required


class TradeUploadView(LoginRequiredMixin, View):
    template_name = "trade/upload.html"
    login_url = "login"

    def get(self, request):
        form = TradeUploadForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = TradeUploadForm(request.POST, request.FILES)

        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        file = request.FILES["file"]
        filename = file.name.lower()

        try:
            if filename.endswith(".csv"):
                df = self.read_csv_safely(file)
            elif filename.endswith(".xlsx"):
                df = pd.read_excel(file)
            else:
                messages.error(request, "Only CSV or Excel files are allowed.")
                return redirect("trade_upload")

            required_columns = {
                "year",
                "month",
                "trade_type",
                "hs_code",
                "country",
                "quantity",
                "description",
                "value_usd",
            }

            if not required_columns.issubset(df.columns):
                messages.error(request, "Missing required columns in file.")
                return redirect("trade_upload")

            records_inserted, records_skipped = self.process_dataframe(df)

            messages.success(
                request,
                f"{records_inserted} records uploaded successfully. {records_skipped} duplicate records skipped.",
            )
            return redirect("trade_upload")

        except Exception as e:
            messages.error(request, f"Upload failed: {str(e)}")
            return redirect("trade_upload")

    def read_csv_safely(self, file):
        file.seek(0)
        raw_data = file.read()

        try:
            return pd.read_csv(io.BytesIO(raw_data), encoding="utf-8")
        except UnicodeDecodeError:
            pass

        try:
            return pd.read_csv(io.BytesIO(raw_data), encoding="latin1")
        except UnicodeDecodeError:
            pass

        return pd.read_csv(io.BytesIO(raw_data), encoding="cp1252")

    def process_dataframe(self, df):
        df = df.fillna("")
        df["hs_code"] = df["hs_code"].astype(str).str.strip()
        df["trade_type"] = df["trade_type"].str.upper().str.strip()

        # Validate month range
        df = df[(df["month"] >= 1) & (df["month"] <= 12)]

        # Deduplicate HS codes within the file by hs_code only
        unique_hs_codes = df[["hs_code", "description"]].drop_duplicates(
            subset=["hs_code"]
        )

        # Preload existing HS codes
        existing_hs = {
            hs.code: hs
            for hs in HSCode.objects.filter(code__in=unique_hs_codes["hs_code"])
        }

        new_hs_objects = []
        for row in unique_hs_codes.itertuples(index=False):
            if row.hs_code not in existing_hs:
                new_hs_objects.append(
                    HSCode(
                        code=row.hs_code,
                        description=row.description,
                    )
                )

        if new_hs_objects:
            # ignore_conflicts prevents crash if concurrent upload sneaks in the same code
            HSCode.objects.bulk_create(
                new_hs_objects, batch_size=1000, ignore_conflicts=True
            )

        # Reload all HS codes after insertion
        all_hs = {hs.code: hs for hs in HSCode.objects.filter(code__in=df["hs_code"])}

        # Build a set of existing (year, month, hs_code_id, country, trade_type) to detect duplicates
        incoming_keys = set(
            zip(
                df["year"].astype(int),
                df["month"].astype(int),
                df["hs_code"],
                df["country"].astype(str).str.strip(),
                df["trade_type"],
            )
        )

        existing_records = TradeData.objects.filter(
            year__in=df["year"].unique(),
            month__in=df["month"].unique(),
            hs_code__in=[hs for hs in all_hs.values()],
        ).values_list("year", "month", "hs_code__code", "country", "trade_type")

        existing_keys = set(existing_records)

        trade_objects = []
        records_skipped = 0

        for row in df.itertuples(index=False):
            key = (
                int(row.year),
                int(row.month),
                row.hs_code,
                str(row.country).strip(),
                row.trade_type,
            )

            if key in existing_keys:
                records_skipped += 1
                continue

            trade_objects.append(
                TradeData(
                    year=int(row.year),
                    month=int(row.month),
                    trade_type=row.trade_type,
                    hs_code=all_hs[row.hs_code],
                    country=row.country,
                    quantity=row.quantity,
                    unit=None,
                    value_usd=row.value_usd,
                )
            )

        with transaction.atomic():
            TradeData.objects.bulk_create(
                trade_objects, batch_size=2000, ignore_conflicts=True
            )

        return len(trade_objects), records_skipped


class TradeDataListView(LoginRequiredMixin, ListView):
    model = TradeData
    template_name = "trade/dashboard.html"
    login_url = "login"
    context_object_name = "trades"
    paginate_by = 50

    def get_queryset(self):
        queryset = TradeData.objects.select_related("hs_code").all()

        year = self.request.GET.get("year")
        month = self.request.GET.get("month")
        trade_type = self.request.GET.get("trade_type")
        country = self.request.GET.get("country")
        search = self.request.GET.get("search")

        if year:
            queryset = queryset.filter(year=year)

        if month:
            queryset = queryset.filter(month=month)

        if trade_type:
            queryset = queryset.filter(trade_type=trade_type)

        if country:
            queryset = queryset.filter(country=country)

        if search:
            queryset = queryset.filter(
                Q(hs_code__code__icontains=search)
                | Q(hs_code__description__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        filtered_queryset = self.get_queryset()

        totals = filtered_queryset.aggregate(
            total_quantity=Sum("quantity"),
            total_value=Sum("value_usd"),
            total_records=Count("id"),
        )

        context["total_quantity"] = totals["total_quantity"] or 0
        context["total_value"] = totals["total_value"] or 0
        context["total_records"] = totals["total_records"] or 0

        top_countries = (
            filtered_queryset.exclude(country__isnull=True)
            .exclude(country="")
            .values("country")
            .annotate(total_value=Sum("value_usd"))
            .order_by("-total_value")[:10]
        )
        context["top_countries"] = top_countries

        top_hs_codes = (
            filtered_queryset.values("hs_code__code", "hs_code__description")
            .annotate(total_value=Sum("value_usd"))
            .order_by("-total_value")[:10]
        )
        context["top_hs_codes"] = top_hs_codes

        trade_split = list(
            filtered_queryset.values("trade_type").annotate(
                total_value=Sum("value_usd")
            )
        )
        total_trade = sum(item["total_value"] or 0 for item in trade_split)
        for item in trade_split:
            if total_trade > 0:
                item["percentage"] = round((item["total_value"] / total_trade) * 100, 2)
            else:
                item["percentage"] = 0
        context["trade_split"] = trade_split

        top_total = sum(item["total_value"] for item in top_hs_codes)
        overall_total = (
            filtered_queryset.aggregate(total=Sum("value_usd"))["total"] or 0
        )
        concentration_ratio = (
            (top_total / overall_total) * 100 if overall_total > 0 else 0
        )
        context["concentration_ratio"] = round(concentration_ratio, 2)

        exports = (
            filtered_queryset.filter(trade_type="EXPORT").aggregate(
                total=Sum("value_usd")
            )["total"]
            or 0
        )
        imports = (
            filtered_queryset.filter(trade_type="IMPORT").aggregate(
                total=Sum("value_usd")
            )["total"]
            or 0
        )
        context["trade_balance"] = exports - imports

        context["years"] = (
            TradeData.objects.values_list("year", flat=True).distinct().order_by("year")
        )
        context["months"] = (
            TradeData.objects.values_list("month", flat=True)
            .distinct()
            .order_by("month")
        )
        context["trade_types"] = (
            TradeData.objects.values_list("trade_type", flat=True)
            .distinct()
            .order_by("trade_type")
        )
        context["countries"] = (
            TradeData.objects.values_list("country", flat=True)
            .distinct()
            .order_by("country")
        )

        return context


@login_required(login_url="login")
def export_filtered_data(request):
    queryset = TradeData.objects.all()

    year = request.GET.get("year")
    month = request.GET.get("month")
    crop = request.GET.get("crop")
    country = request.GET.get("country")

    if year:
        queryset = queryset.filter(year=year)
    if month:
        queryset = queryset.filter(month=month)
    if crop:
        queryset = queryset.filter(hs_code__description=crop)
    if country:
        queryset = queryset.filter(country=country)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="filtered_trade_data.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Year",
            "Month",
            "Country",
            "HS Code",
            "Description",
            "Trade Type",
            "Quantity",
            "Value (USD)",
        ]
    )

    for obj in queryset:
        writer.writerow(
            [
                obj.year,
                obj.month,
                obj.country,
                obj.hs_code.code if obj.hs_code else "",
                obj.hs_code.description if obj.hs_code else "",
                obj.trade_type,
                obj.quantity,
                obj.value_usd,
            ]
        )

    return response
