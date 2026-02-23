from django import forms


class TradeUploadForm(forms.Form):
    file = forms.FileField()
