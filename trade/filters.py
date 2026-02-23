import django_filters
from .models import TradeData


class TradeDataFilter(django_filters.FilterSet):
    year = django_filters.NumberFilter()
    month = django_filters.NumberFilter()
    trade_type = django_filters.ChoiceFilter(choices=TradeData.TRADE_TYPE_CHOICES)

    # Exact HS code
    hs_code = django_filters.CharFilter(field_name="hs_code__code", lookup_expr="exact")

    # Filter by chapter (2-digit)
    chapter = django_filters.CharFilter(
        field_name="hs_code__chapter", lookup_expr="exact"
    )

    # Filter by heading (4-digit)
    heading = django_filters.CharFilter(
        field_name="hs_code__heading", lookup_expr="exact"
    )

    # Filter by subheading (6-digit)
    subheading = django_filters.CharFilter(
        field_name="hs_code__subheading", lookup_expr="exact"
    )

    class Meta:
        model = TradeData
        fields = ["year", "month", "trade_type"]
