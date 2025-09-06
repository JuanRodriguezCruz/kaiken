from django.contrib import admin

from .models import Tender, Product, Order


class OrderInline(admin.TabularInline):
    model = Order
    extra = 0
    readonly_fields = ('unit_price', 'unit_cost')


@admin.register(Tender)
class TenderAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'client', 'awarded_date', 'total_margin_display')
    inlines = (OrderInline,)

    def total_margin_display(self, obj):  # pragma: no cover - admin helper
        return obj.total_margin()

    total_margin_display.short_description = 'Total Margin'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'price', 'cost')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('tender', 'product', 'quantity', 'unit_price', 'unit_cost')

from django.contrib import admin

# Register your models here.
