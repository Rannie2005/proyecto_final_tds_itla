from django.contrib import admin
from .models import Prestamo, Venta, Consumo



admin.site.register(Prestamo)
admin.site.register(Venta)
admin.site.register(Consumo)