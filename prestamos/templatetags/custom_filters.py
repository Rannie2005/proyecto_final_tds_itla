# Crea este archivo: prestamos/templatetags/custom_filters.py

from django import template

# En custom_filters.py


register = template.Library()

@register.filter
def mul(value, arg):
    """Multiplica value por arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
register = template.Library()

@register.filter
def dividir(value, arg):
    """Divide el valor por el argumento"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def calcular_promedio(total, cantidad):
    """Calcula el promedio (total / cantidad)"""
    try:
        if float(cantidad) > 0:
            return float(total) / float(cantidad)
        return 0
    except (ValueError, TypeError):
        return 0