from django.contrib import admin

from .models import Tender, Product, Order, Client


class OrderInline(admin.TabularInline):
    model = Order
    extra = 0
    readonly_fields = ('unit_price', 'unit_cost')


@admin.register(Tender)
class TenderAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'get_client_name', 'awarded_date', 'total_margin_display')
    inlines = (OrderInline,)

    def total_margin_display(self, obj):  # pragma: no cover - admin helper
        return obj.total_margin()

    total_margin_display.short_description = 'Total Margin'

    def get_client_name(self, obj):
        return obj.client_obj.name if obj.client_obj else ''
    get_client_name.short_description = 'Cliente'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'price', 'cost')


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('tender', 'product', 'quantity', 'unit_price', 'unit_cost')

from django.contrib import admin

# Register your models here.
