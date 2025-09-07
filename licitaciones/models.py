from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Sum, ExpressionWrapper, DecimalField


# Create your models here.


class Tender(models.Model):
    """Licitación adjudicada."""

    identifier = models.CharField(max_length=128, unique=True)
    # Identificador normalizado (sin guiones) para búsquedas robustas desde
    # sistemas externos que pueden enviar el id sin guiones.
    normalized_identifier = models.CharField(max_length=128, blank=True, db_index=True)
    # Relación con tabla de clientes.
    client_obj = models.ForeignKey('Client', null=True, blank=True, on_delete=models.SET_NULL, related_name='tenders')
    awarded_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - trivial
        client_name = self.client_obj.name if self.client_obj else ''
        return f"{self.identifier} - {client_name}"

    def total_margin(self) -> Decimal:
        """Calcula el margen total de la licitación: sum((price-cost)*qty).

        Usa agregaciones para evitar traer todas las filas a memoria.
        """
        expr = ExpressionWrapper((F('unit_price') - F('unit_cost')) * F('quantity'), output_field=DecimalField())
        result = self.orders.aggregate(total=Sum(expr))
        return result['total'] or Decimal('0')

    def save(self, *args, **kwargs):
        # Mantener `normalized_identifier` sincronizado con `identifier`.
        if self.identifier:
            self.normalized_identifier = str(self.identifier).replace('-', '')
        # Ejecutar validaciones de modelo siempre (no se permite bypass).
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        # No permitir que una licitación existente quede sin órdenes.
        # Para nuevas instancias (sin pk) la validación se omite aquí porque
        # normalmente se crean primero y luego se añaden las órdenes.
        if self.pk:
            if self.orders.count() == 0:
                raise ValidationError('No se permiten licitaciones sin productos.')


class Product(models.Model):
    """Producto disponible para incluir en una licitación."""

    name = models.CharField(max_length=256)
    sku = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    cost = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(price__gt=F('cost')), name='price_gt_cost')
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name} ({self.sku})"


class Client(models.Model):
    """Cliente que contrata las licitaciones."""

    name = models.CharField(max_length=256, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name



class Order(models.Model):
    """Detalle de productos adjudicados en una licitación.

    Se almacena unit_price y unit_cost al momento de la adjudicación para
    preservar el historial si el `Product` cambia luego.
    """

    tender = models.ForeignKey(Tender, related_name='orders', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.tender.identifier} - {self.product.sku} x{self.quantity}"

    def clean(self):
        """Validaciones de negocio.

        - unit_price debe ser > unit_cost
        - quantity > 0 (ya lo garantiza PositiveIntegerField)
        """
        if self.unit_price <= self.unit_cost:
            raise ValidationError('El precio unitario debe ser mayor que el costo unitario.')

    def save(self, *args, **kwargs):
        # Si no se especifican unitarios, los tomamos del producto actual
        if not self.unit_price:
            self.unit_price = self.product.price
        if not self.unit_cost:
            self.unit_cost = self.product.cost
        # Ejecutar validaciones
        self.full_clean()
        super().save(*args, **kwargs)

    def margin(self) -> Decimal:
        return (self.unit_price - self.unit_cost) * Decimal(self.quantity)

    @property
    def margin_percentage(self) -> Decimal:
        """Porcentaje de margen unitario: ((unit_price - unit_cost) / unit_price) * 100.

        Devuelve un Decimal cuantizado a 2 decimales; si unit_price es 0 devuelve 0.
        """
        try:
            if not self.unit_price or self.unit_price == 0:
                return Decimal('0.00')
            pct = (self.unit_price - self.unit_cost) / self.unit_price * Decimal('100')
            return pct.quantize(Decimal('0.01'))
        except Exception:
            return Decimal('0.00')

