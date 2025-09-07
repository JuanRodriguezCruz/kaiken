import json
from decimal import Decimal
from urllib.request import urlopen
from django.conf import settings

from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError

from licitaciones.models import Tender, Product, Order, Client


TENDER_URL = getattr(settings, 'SAMPLE_TENDER_URL', 'https://kaiken.up.railway.app/webhook/tender-sample')
PRODUCT_URL = getattr(settings, 'SAMPLE_PRODUCT_URL', 'https://kaiken.up.railway.app/webhook/product-sample')
ORDER_URL = getattr(settings, 'SAMPLE_ORDER_URL', 'https://kaiken.up.railway.app/webhook/order-sample')


def fetch_json(url: str):
    with urlopen(url) as resp:
        return json.load(resp)


class Command(BaseCommand):
    help = 'Importa datos de ejemplo desde los endpoints proporcionados'

    def handle(self, *args, **options):
        self.stdout.write('Descargando productos...')
        products = fetch_json(PRODUCT_URL)
        for p in products:
            try:
                sku = str(p.get('sku') or p.get('product_id'))
                name = p.get('title') or p.get('name') or ''
                cost = Decimal(str(p.get('cost', 0)))
                # Si no hay precio de venta, aplicar un margen por defecto para cumplir la restricción price>cost
                price_val = p.get('price') or p.get('unit_price')
                if price_val is None:
                    price = (cost * Decimal('1.20')).quantize(Decimal('0.01'))
                else:
                    price = Decimal(str(price_val))

                Product.objects.update_or_create(
                    sku=sku,
                    defaults={'name': name, 'price': price, 'cost': cost},
                )
            except Exception as exc:
                self.stderr.write(f'Error importando producto {p!r}: {exc}')

        # Descargar órdenes primero para saber qué tenders tienen productos
        orders_data = fetch_json(ORDER_URL)
        tender_to_orders = {}
        for o in orders_data:
            tid = o.get('tender_id') or o.get('tender_identifier')
            key = str(tid or '').replace('-', '')
            tender_to_orders.setdefault(key, []).append(o)

        self.stdout.write('Descargando licitaciones...')
        tenders = fetch_json(TENDER_URL)
        for t in tenders:
            identifier = t.get('id') or t.get('identifier')
            client_name = t.get('client', '')
            # Mapeamos `creation_date` al campo `awarded_date` del modelo
            awarded_date = t.get('creation_date') or t.get('awarded_date')

            try:
                # Crear o obtener cliente en la tabla Client
                client_obj = None
                if client_name:
                    client_obj, _ = Client.objects.get_or_create(name=client_name)

                # Si existe, actualizar y validar mediante save()
                existing = Tender.objects.filter(identifier=identifier).first()
                if existing:
                    existing.client = client_name
                    existing.client_obj = client_obj
                    existing.awarded_date = awarded_date
                    try:
                        existing.save()
                    except ValidationError as ve:
                        self.stderr.write(f'Error validando licitación {identifier}: {ve}')
                        continue
                else:
                    # Sólo crear la tender si existen órdenes asociadas
                    normalized = str(identifier or '').replace('-', '')
                    if normalized not in tender_to_orders:
                        self.stderr.write(f'Omitiendo licitación sin órdenes: {identifier}')
                        continue

                    tender = Tender(identifier=identifier, client_obj=client_obj, awarded_date=awarded_date)
                    try:
                        tender.save()
                    except ValidationError as ve:
                        self.stderr.write(f'Error creando licitación {identifier}: {ve}')
                        continue
            except Exception as exc:
                self.stderr.write(f'Error importando licitación {t!r}: {exc}')

        self.stdout.write('Descargando órdenes...')
        orders = fetch_json(ORDER_URL)
        for o in orders:
            try:
                tender_identifier = o.get('tender_id') or o.get('tender_identifier')
                product_id = o.get('product_id') or o.get('product_sku') or o.get('sku')
                quantity = int(o.get('quantity', 1))

                # Convertir y normalizar unit_price a 2 decimales para evitar
                # problemas con representaciones en coma flotante que generan
                # demasiados dígitos al validar el DecimalField.
                raw_price = o.get('price') or o.get('unit_price') or 0
                unit_price = Decimal(str(raw_price))
                # Quantize to the Order.unit_price decimal places
                unit_price = unit_price.quantize(Decimal('0.01'))

                # Asegurar que el valor no exceda la precisión total del campo
                field = Order._meta.get_field('unit_price')
                max_digits = field.max_digits
                decimal_places = field.decimal_places
                int_digits = max_digits - decimal_places
                # Construir el máximo permitido, por ejemplo '999... .99'
                if decimal_places:
                    max_allowed = Decimal(''.join(['9'] * int_digits) + '.' + ''.join(['9'] * decimal_places))
                else:
                    max_allowed = Decimal(''.join(['9'] * int_digits))

                if unit_price.copy_abs() > max_allowed:
                    self.stderr.write(f'unit_price demasiado grande en orden {o.get("id", o)!r}: {unit_price} -> se ajusta a {max_allowed}')
                    unit_price = max_allowed

                # Intentamos buscar por identifier exacto
                try:
                    tender = Tender.objects.get(identifier=tender_identifier)
                except Tender.DoesNotExist:
                    # Buscar por normalized_identifier si viene sin guiones
                    normalized = str(tender_identifier or '').replace('-', '')
                    try:
                        tender = Tender.objects.get(normalized_identifier=normalized)
                    except Tender.DoesNotExist:
                        self.stderr.write(f'Tender no encontrada: {tender_identifier}')
                        continue
                product = Product.objects.get(sku=str(product_id))

                try:
                    Order.objects.create(
                        tender=tender,
                        product=product,
                        quantity=quantity,
                        unit_price=unit_price if unit_price > 0 else product.price,
                        unit_cost=product.cost,
                    )
                except ValidationError as ve:
                    self.stderr.write(f"Error importando orden {o!r}: {ve.message_dict if hasattr(ve,'message_dict') else ve}")
                    continue
            except Tender.DoesNotExist:
                self.stderr.write(f'Tender no encontrada: {tender_identifier}')
            except Product.DoesNotExist:
                self.stderr.write(f'Product no encontrada: {product_id}')
            except Exception as exc:
                self.stderr.write(f'Error importando orden {o!r}: {exc}')

        self.stdout.write(self.style.SUCCESS('Importación finalizada.'))


