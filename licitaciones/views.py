from decimal import Decimal
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, F, Sum, ExpressionWrapper, DecimalField, Value
from django.db.models.functions import Coalesce, Cast
from django.db.models import Q

from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from .forms import TenderForm, OrderFormSet

from .models import Tender
from .models import Client
from .forms import ClientForm


def tender_list(request):
    """Devuelve una lista de licitaciones con margen total.

    Soporta respuesta JSON en rutas `api/` (existente) y renderizado HTML
    para la vista pública. Si la petición pide JSON (por cabecera
    `Accept: application/json` o la ruta contiene `/api/`), devuelve JSON,
    en otro caso renderiza la plantilla `licitaciones/tender_list.html`.
    """
    # Anotar margen total para poder filtrar por él eficientemente
    # Evitar errores por mezcla de tipos: declarar DecimalField explícito y
    # castear quantity al mismo tipo antes de multiplicar.
    dec_field = DecimalField(max_digits=18, decimal_places=2)
    margin_expr = ExpressionWrapper(
        (F('orders__unit_price') - F('orders__unit_cost')) * Cast(F('orders__quantity'), output_field=dec_field),
        output_field=dec_field,
    )
    tenders = Tender.objects.all().annotate(total_margin=Coalesce(Sum(margin_expr), Value(0, output_field=dec_field), output_field=dec_field)).order_by('-awarded_date')

    # Búsqueda por query 'q' en identificador o cliente
    q = request.GET.get('q', '').strip()
    if q:
        tenders = tenders.filter(Q(identifier__icontains=q) | Q(client__icontains=q))

    # Filtros: cliente exacto/contains, rango de fechas, margen min/max
    client_filter = request.GET.get('client', '').strip()
    if client_filter:
        tenders = tenders.filter(client__icontains=client_filter)

    start_date = request.GET.get('start_date', '').strip()
    if start_date:
        tenders = tenders.filter(awarded_date__gte=start_date)

    end_date = request.GET.get('end_date', '').strip()
    if end_date:
        tenders = tenders.filter(awarded_date__lte=end_date)

    min_margin = request.GET.get('min_margin', '').strip()
    if min_margin:
        try:
            minm = Decimal(min_margin)
            tenders = tenders.filter(total_margin__gte=minm)
        except Exception:
            pass

    max_margin = request.GET.get('max_margin', '').strip()
    if max_margin:
        try:
            maxm = Decimal(max_margin)
            tenders = tenders.filter(total_margin__lte=maxm)
        except Exception:
            pass

    # Si la petición es para la API, mantenemos la respuesta JSON existente
    if request.path.startswith('/api/') or request.headers.get('Accept', '').find('application/json') != -1:
        data = []
        for t in tenders:
            data.append({
                'identifier': t.identifier,
                'client': t.client,
                'awarded_date': t.awarded_date.isoformat(),
                'total_margin': str(t.total_margin() or Decimal('0')),
            })
        return JsonResponse(data, safe=False)

    # Paginación para la vista HTML
    page = request.GET.get('page', 1)
    paginator = Paginator(tenders, 10)  # 10 por página
    try:
        tenders_page = paginator.page(page)
    except PageNotAnInteger:
        tenders_page = paginator.page(1)
    except EmptyPage:
        tenders_page = paginator.page(paginator.num_pages)

    context = {
        'tenders': tenders_page,
        'paginator': paginator,
        'q': q,
    }
    return render(request, 'licitaciones/tender_list.html', context)


def client_list(request):
    clients = Client.objects.all().order_by('-created_at')
    q = request.GET.get('q', '').strip()
    if q:
        clients = clients.filter(name__icontains=q)
    page = request.GET.get('page', 1)
    paginator = Paginator(clients, 20)
    try:
        clients_page = paginator.page(page)
    except PageNotAnInteger:
        clients_page = paginator.page(1)
    except EmptyPage:
        clients_page = paginator.page(paginator.num_pages)

    return render(request, 'licitaciones/client_list.html', {'clients': clients_page, 'paginator': paginator, 'q': q})


def client_create(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            return redirect('client_detail', pk=client.pk)
    else:
        form = ClientForm()
    return render(request, 'licitaciones/client_form.html', {'form': form})


def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    tenders = client.tenders.order_by('-awarded_date').all()
    return render(request, 'licitaciones/client_detail.html', {'client': client, 'tenders': tenders})


def tender_detail(request, identifier):
    """Detalle de una licitación con productos adjudicados y margen por item.

    Igual que `tender_list`, soporta JSON para la API existente y HTML para
    la vista pública en la plantilla `licitaciones/tender_detail.html`.
    """
    tender = get_object_or_404(Tender, identifier=identifier)
    orders = tender.orders.select_related('product').all()

    # Si la petición es para la API existente, devolvemos JSON igual que antes
    if request.path.startswith('/api/') or request.headers.get('Accept', '').find('application/json') != -1:
        items = []
        for o in orders:
            items.append({
                'product_sku': o.product.sku,
                'product_name': o.product.name,
                'quantity': o.quantity,
                'unit_price': str(o.unit_price),
                'unit_cost': str(o.unit_cost),
                'margin': str(o.margin()),
            })

        resp = {
            'identifier': tender.identifier,
            'client': tender.client,
            'awarded_date': tender.awarded_date.isoformat(),
            'total_margin': str(tender.total_margin() or Decimal('0')),
            'items': items,
        }
        return JsonResponse(resp)

    # Render para la vista HTML
    context = {
        'tender': tender,
        'orders': orders,
    }
    return render(request, 'licitaciones/tender_detail.html', context)


@require_http_methods(['GET', 'POST'])
def tender_create(request):
    """Formulario para crear una Tender con sus Orders inline."""
    if request.method == 'POST':
        form = TenderForm(request.POST)
        # Crear instancia no guardada para validar formset antes de persistir
        if form.is_valid():
            tender = form.save(commit=False)
            formset = OrderFormSet(request.POST, instance=tender)
            if formset.is_valid():
                # Requerir al menos una orden no marcada para eliminar
                orders_count = 0
                for fdata in formset.cleaned_data:
                    if fdata and not fdata.get('DELETE', False):
                        orders_count += 1

                if orders_count == 0:
                    form.add_error(None, 'Debe incluir al menos una orden para la licitación.')
                else:
                    tender.save()
                    formset.save()
                    return redirect('tender_detail_html', identifier=tender.identifier)
        else:
            formset = OrderFormSet(request.POST)
    else:
        form = TenderForm()
        formset = OrderFormSet()

    return render(request, 'licitaciones/tender_form.html', {'form': form, 'formset': formset})

