from django import forms
from django.forms.models import inlineformset_factory
from .models import Tender, Order


class TenderForm(forms.ModelForm):
    class Meta:
        model = Tender
        fields = ['identifier', 'client', 'awarded_date']
        widgets = {
            'awarded_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'identifier': 'Identificador',
            'client': 'Cliente',
            'awarded_date': 'Fecha adjudicación',
        }


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('product', 'quantity', 'unit_price', 'unit_cost')
        labels = {
            'product': 'Producto',
            'quantity': 'Cantidad',
            'unit_price': 'Precio unitario',
            'unit_cost': 'Coste unitario',
        }


OrderFormSet = inlineformset_factory(
    Tender,
    Order,
    form=OrderForm,
    extra=1,
    can_delete=True,
)


