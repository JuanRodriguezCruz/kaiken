from decimal import Decimal
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from .forms import TenderForm, OrderFormSet

from .models import Tender


def tender_list(request):
    """Devuelve una lista de licitaciones con margen total.

    Soporta respuesta JSON en rutas `api/` (existente) y renderizado HTML
    para la vista pública. Si la petición pide JSON (por cabecera
    `Accept: application/json` o la ruta contiene `/api/`), devuelve JSON,
    en otro caso renderiza la plantilla `licitaciones/tender_list.html`.
    """
    tenders = Tender.objects.all().order_by('-awarded_date')

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
    }
    return render(request, 'licitaciones/tender_list.html', context)


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

