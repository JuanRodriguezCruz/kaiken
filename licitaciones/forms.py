from django import forms
from django.forms.models import inlineformset_factory
from .models import Tender, Order, Client


class TenderForm(forms.ModelForm):
    class Meta:
        model = Tender
        # Usamos la relación `client_obj` en lugar del campo de texto `client`
        fields = ['identifier', 'client_obj', 'awarded_date']
        widgets = {
            'awarded_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'identifier': 'Identificador',
            'client_obj': 'Cliente',
            'awarded_date': 'Fecha adjudicación',
        }

    client_obj = forms.ModelChoiceField(queryset=Client.objects.all(), required=False, label='Cliente')


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ('name',)
        labels = {'name': 'Nombre'}


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


