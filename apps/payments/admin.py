from django.contrib import admin

from .models import Coupon, Order, Transaction


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ["gateway_id", "success", "amount_cents", "source_type", "raw", "created_at"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "kind", "total", "currency", "status", "method", "created_at"]
    list_filter = ["status", "kind", "method"]
    search_fields = ["user__full_name", "user__phone", "reference", "paymob_order_id"]
    inlines = [TransactionInline]


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ["code", "percent_off", "amount_off", "applies_to", "used_count", "max_uses", "is_active"]
