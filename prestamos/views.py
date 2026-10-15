from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
from django.conf import settings

from .models import Prestamo, Venta, Consumo, DevolucionConsumo
from .forms import PrestamoForm, VentaForm, ConsumoForm, DevolucionConsumoForm
from inventario.models import Herramienta
from .utils import generar_pdf_prestamo, generar_pdf_venta


from django.contrib import messages
from django.http import HttpResponse, FileResponse
from django.utils import timezone
import os
from datetime import timedelta, datetime
from django.db.models import Sum, Count, Avg, Max
from decimal import Decimal 
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from datetime import datetime, timedelta

@login_required
def listar_ventas(request):
    """
    Vista para listar todas las ventas con filtros y estadísticas
    """
    # Obtener todas las ventas ordenadas por fecha descendente
    ventas = Venta.objects.all().select_related(
        'herramienta', 
        'herramienta__categoria',
        'vendedor'
    ).order_by('-fecha_venta')
    
    # Filtros
    filtros = {}
    
    # Filtro por búsqueda
    search_query = request.GET.get('search', '')
    if search_query:
        ventas = ventas.filter(
            Q(numero_factura__icontains=search_query) |
            Q(cliente_nombre__icontains=search_query) |
            Q(cliente_cedula__icontains=search_query) |
            Q(herramienta__nombre__icontains=search_query) |
            Q(herramienta__codigo__icontains=search_query)
        )
        filtros['search'] = search_query
    
    # Filtro por vendedor
    vendedor_id = request.GET.get('vendedor')
    if vendedor_id:
        ventas = ventas.filter(vendedor_id=vendedor_id)
        filtros['vendedor'] = vendedor_id
    
    # Filtro por fecha
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d')
            ventas = ventas.filter(fecha_venta__date__gte=fecha_desde_obj)
            filtros['fecha_desde'] = fecha_desde
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d')
            ventas = ventas.filter(fecha_venta__date__lte=fecha_hasta_obj)
            filtros['fecha_hasta'] = fecha_hasta
        except ValueError:
            pass
    
    # Estadísticas generales
    total_ventas = ventas.count()
    total_monto = ventas.aggregate(total=Sum('total'))['total'] or 0
    total_cantidad = ventas.aggregate(total=Sum('cantidad_vendida'))['total'] or 0
    
    # Estadísticas por día (últimos 7 días)
    siete_dias_atras = datetime.now() - timedelta(days=7)
    ventas_ultima_semana = Venta.objects.filter(
        fecha_venta__gte=siete_dias_atras
    ).count()
    
    # Ventas de hoy
    hoy = datetime.now().date()
    ventas_hoy = Venta.objects.filter(fecha_venta__date=hoy).count()
    
    # Top vendedores
    top_vendedores = Venta.objects.values(
        'vendedor__username',
        'vendedor__first_name',
        'vendedor__last_name'
    ).annotate(
        total_ventas=Count('id'),
        monto_total=Sum('total')
    ).order_by('-monto_total')[:5]
    
    # Paginación
    paginator = Paginator(ventas, 20)  # 20 ventas por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Obtener todos los vendedores para el filtro
    vendedores = User.objects.filter(
        venta__isnull=False
    ).distinct().order_by('username')
    
    context = {
        'ventas': page_obj,
        'page_obj': page_obj,
        'vendedores': vendedores,
        'filtros': filtros,
        
        # Estadísticas
        'total_ventas': total_ventas,
        'total_monto': total_monto,
        'total_cantidad': total_cantidad,
        'ventas_hoy': ventas_hoy,
        'ventas_ultima_semana': ventas_ultima_semana,
        'top_vendedores': top_vendedores,
        
        # Fechas para filtros
        'hoy': datetime.now().date().isoformat(),
        'siete_dias_atras': (datetime.now() - timedelta(days=7)).date().isoformat(),
        'treinta_dias_atras': (datetime.now() - timedelta(days=30)).date().isoformat(),
    }
    
    return render(request, 'prestamos/listar_ventas.html', context)

@login_required
def crear_prestamo(request, herramienta_id=None):
    """
    Vista simplificada sin transacción (pero funcional)
    """
    herramienta = None
    
    if herramienta_id:
        herramienta = get_object_or_404(Herramienta, id=herramienta_id)
    
    if request.method == 'POST':
        form = PrestamoForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                prestamo = form.save(commit=False)
                prestamo.prestado_por = request.user
                prestamo.save()
                
                messages.success(
                    request, 
                    f'Préstamo registrado exitosamente para {prestamo.quien_recibe()}'
                )
                
                return redirect('prestamos:comprobante_prestamo', prestamo_id=prestamo.id)
                
            except Exception as e:
                messages.error(
                    request, 
                    f'Error: {str(e)}'
                )
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        initial = {}
        if herramienta:
            initial['herramienta'] = herramienta
        
        form = PrestamoForm(initial=initial, user=request.user)
    
    return render(request, 'prestamos/crear_prestamo.html', {
        'form': form,
        'herramienta': herramienta,
    })

@login_required
def crear_venta(request, herramienta_id=None):
    herramienta = None
    if herramienta_id:
        herramienta = get_object_or_404(Herramienta, id=herramienta_id)
    
    if request.method == 'POST':
        form = VentaForm(request.POST)
        if form.is_valid():
            venta = form.save(commit=False)
            venta.vendedor = request.user
            venta.save()
            
            messages.success(request, f'Venta registrada exitosamente a {venta.cliente_nombre}')
            
            # Redirigir a la página de confirmación en lugar de descargar automáticamente
            return redirect('prestamos:factura_venta', venta_id=venta.id)
            
    else:
        initial = {}
        if herramienta:
            initial['herramienta'] = herramienta
        form = VentaForm(initial=initial)
    
    return render(request, 'prestamos/crear_venta.html', {
        'form': form,
        'herramienta': herramienta,
    })


# En views.py - modificar comprobante_prestamo
@login_required
def comprobante_prestamo(request, prestamo_id):
    """
    Vista para mostrar el comprobante de préstamo
    """
    prestamo = get_object_or_404(Prestamo, id=prestamo_id)
    
    
    
    # ✅ SI viene con ?print=true, mostrar versión para imprimir (HTML independiente)
    if 'print' in request.GET:
        return render(request, 'prestamos/comprobante_prestamo_print.html', {
            'prestamo': prestamo,
        })
    
    # ✅ Versión normal (dentro de base.html)
    context = {
        'prestamo': prestamo,
        'from_form': request.GET.get('from_form', False)
    }
    
    return render(request, 'prestamos/comprobante_prestamo.html', context)

@login_required
def factura_venta(request, venta_id):
    """Vista para mostrar la factura en HTML con opciones de PDF"""
    venta = get_object_or_404(Venta, id=venta_id)
    
    # Verificar si es para imprimir
    if 'print' in request.GET:
        return render(request, 'prestamos/factura_venta_print.html', {
            'venta': venta,
        })
    
    from_form = 'success' in request.GET
    return render(request, 'prestamos/factura_venta.html', {
        'venta': venta,
        'from_form': from_form,
    })

# AÑADE ESTAS FUNCIONES QUE FALTAN:

# prestamos/views.py (continuación)

@login_required
def descargar_pdf_prestamo(request, prestamo_id):
    """Genera PDF del comprobante de préstamo"""
    from django.http import HttpResponse
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    import io
    
    prestamo = get_object_or_404(Prestamo, id=prestamo_id)
    
    # Crear buffer para PDF
    buffer = io.BytesIO()
    
    # Crear PDF
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Contenido del PDF
    p.setFont("Helvetica-Bold", 16)
    p.drawString(1*inch, height - 1*inch, "KEMA CONSTRUCTORA")
    p.setFont("Helvetica", 12)
    p.drawString(1*inch, height - 1.2*inch, "Comprobante de Préstamo")
    
    # Información del préstamo
    p.setFont("Helvetica-Bold", 10)
    p.drawString(1*inch, height - 1.5*inch, f"N° Comprobante: {prestamo.id}")
    p.drawString(1*inch, height - 1.7*inch, f"Fecha: {prestamo.fecha_prestamo.strftime('%d/%m/%Y %H:%M')}")
    

    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    
    # Crear respuesta
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="prestamo_{prestamo.id}.pdf"'
    
    return response

@login_required
def lista_prestamos(request):
    """Lista todos los préstamos con filtros"""
    from .forms import FiltroPrestamosForm
    
    prestamos = Prestamo.objects.all().order_by('-fecha_prestamo')
    form_filtro = FiltroPrestamosForm(request.GET or None)
    
    if form_filtro.is_valid():
        if form_filtro.cleaned_data.get('estado'):
            prestamos = prestamos.filter(estado=form_filtro.cleaned_data['estado'])
        
        if form_filtro.cleaned_data.get('herramienta'):
            prestamos = prestamos.filter(herramienta=form_filtro.cleaned_data['herramienta'])
        
        if form_filtro.cleaned_data.get('fecha_desde'):
            prestamos = prestamos.filter(fecha_prestamo__date__gte=form_filtro.cleaned_data['fecha_desde'])
        
        if form_filtro.cleaned_data.get('fecha_hasta'):
            prestamos = prestamos.filter(fecha_prestamo__date__lte=form_filtro.cleaned_data['fecha_hasta'])
    
    context = {
        'prestamos': prestamos,
        'form_filtro': form_filtro,
        'titulo': 'Lista de Préstamos',
    }
    
    return render(request, 'prestamos/lista_prestamos.html', context)

@login_required
def descargar_pdf_venta(request, venta_id):
    """Vista para descargar el PDF de una venta existente"""
    venta = get_object_or_404(Venta, id=venta_id)
    
    try:
        filepath, filename = generar_pdf_venta(venta)
        
        response = FileResponse(
            open(filepath, 'rb'),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        messages.error(request, f'Error al generar PDF: {str(e)}')
        return redirect('prestamos:factura_venta', venta_id=venta.id)


def generar_pdf_prestamo(prestamo):
    """Función auxiliar que debería estar en utils.py"""
    from .utils import generar_pdf_prestamo as generar_pdf
    return generar_pdf(prestamo)

def generar_pdf_venta(venta):
    """Función auxiliar que debería estar en utils.py"""
    from .utils import generar_pdf_venta as generar_pdf
    return generar_pdf(venta)


# prestamos/views.py (agregar estas funciones)
@login_required
def crear_consumo(request, herramienta_id=None):
    """Vista para registrar consumo interno de materiales"""
    herramienta = None
    if herramienta_id:
        herramienta = get_object_or_404(Herramienta, id=herramienta_id)
    
    if request.method == 'POST':
        # ✅ PASA el user al formulario
        form = ConsumoForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                consumo = form.save(commit=False)
                consumo.registrado_por = request.user
                consumo.save()
                
                messages.success(
                    request, 
                    f'✅ Consumo registrado exitosamente para el proyecto: {consumo.proyecto}'
                )
                return redirect('prestamos:comprobante_consumo', consumo_id=consumo.id)
            
            except Exception as e:
                messages.error(request, f'❌ Error: {str(e)}')
        
        else:
            # Muestra errores del formulario
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            
    else:
        initial = {}
        if herramienta:
            initial['herramienta'] = herramienta
        
        # ✅ PASA el user también en GET
        form = ConsumoForm(initial=initial, user=request.user)
    
    return render(request, 'prestamos/crear_consumo.html', {
        'form': form,
        'herramienta': herramienta,
        'title': 'Registrar Consumo Interno'
    })


@login_required
def comprobante_consumo(request, consumo_id):
    """Vista para mostrar el comprobante de consumo"""
    consumo = get_object_or_404(Consumo, id=consumo_id)
    devoluciones = consumo.devoluciones.all().order_by('-fecha_devolucion')
    
    
    
    # Si viene con ?print=true, mostrar versión para imprimir
    if 'print' in request.GET:
        return render(request, 'prestamos/comprobante_consumo_print.html', {
            'consumo': consumo,
            'devoluciones': devoluciones,
        })
    
    # Versión normal (dentro de base.html)
    context = {
        'consumo': consumo,
        'devoluciones': devoluciones,
        'from_form': request.GET.get('from_form', False)
    }
    
    return render(request, 'prestamos/comprobante_consumo.html', context)


@login_required
def listar_consumos(request):
    """Lista todos los consumos internos"""
    consumos = Consumo.objects.all().order_by('-fecha_consumo')
    
    # Filtros
    tipo_consumo = request.GET.get('tipo_consumo')
    if tipo_consumo:
        consumos = consumos.filter(tipo_consumo=tipo_consumo)
    
    estado = request.GET.get('estado')
    if estado:
        consumos = consumos.filter(estado=estado)
    
    proyecto = request.GET.get('proyecto')
    if proyecto:
        consumos = consumos.filter(proyecto__icontains=proyecto)
    
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    if fecha_inicio:
        consumos = consumos.filter(fecha_consumo__date__gte=fecha_inicio)
    if fecha_fin:
        consumos = consumos.filter(fecha_consumo__date__lte=fecha_fin)
    
    # Estadísticas
    total_consumido = sum([c.cantidad_actual for c in consumos] or [0])
    total_devuelto = sum([c.cantidad_devuelta for c in consumos] or [0])
    
    return render(request, 'prestamos/listar_consumos.html', {
        'consumos': consumos,
        'estados': dict(Consumo.ESTADOS_CONSUMO),
        'tipos_consumo': dict(Consumo.TIPOS_CONSUMO),
        'total_consumido': total_consumido,
        'total_devuelto': total_devuelto,
        'title': 'Consumos Internos'
    })

@login_required
def devolver_consumo(request, consumo_id):
    """Vista para devolver consumo parcialmente"""
    consumo = get_object_or_404(Consumo, id=consumo_id)
    
    if not consumo.puede_devolver():
        messages.error(request, 'No se puede devolver este consumo. Ya fue totalmente devuelto.')
        return redirect('prestamos:comprobante_consumo', consumo_id=consumo.id)
    
    if request.method == 'POST':
        form = DevolucionConsumoForm(request.POST, consumo=consumo)
        if form.is_valid():
            # Crear devolución
            devolucion = form.save(commit=False)
            devolucion.consumo = consumo
            devolucion.devuelto_por = request.user
            devolucion.save()
            
            # Actualizar consumo
            consumo.cantidad_devuelta += devolucion.cantidad_devuelta
            consumo.save()
            
            messages.success(request, 
                f'Devolución registrada exitosamente: {devolucion.cantidad_devuelta} devueltos. '
                f'Quedan {consumo.cantidad_actual} por devolver.'
            )
            return redirect('prestamos:comprobante_consumo', consumo_id=consumo.id)
    else:
        form = DevolucionConsumoForm(consumo=consumo)
    
    return render(request, 'prestamos/devolver_consumo.html', {
        'consumo': consumo,
        'form': form,
        'title': 'Devolver Consumo'
    })

@login_required
def dashboard_devoluciones(request):
    """Dashboard de devoluciones"""
    # Consumos que pueden devolverse
    consumos_pendientes = Consumo.objects.filter(
        cantidad_actual__gt=0
    ).order_by('-fecha_consumo')[:10]
    
    # Devoluciones recientes
    devoluciones_recientes = DevolucionConsumo.objects.all().order_by('-fecha_devolucion')[:10]
    
    # Estadísticas
    total_consumos = Consumo.objects.count()
    consumos_activos = Consumo.objects.filter(cantidad_actual__gt=0).count()
    total_devoluciones = DevolucionConsumo.objects.count()
    
    return render(request, 'prestamos/dashboard_devoluciones.html', {
        'consumos_pendientes': consumos_pendientes,
        'devoluciones_recientes': devoluciones_recientes,
        'total_consumos': total_consumos,
        'consumos_activos': consumos_activos,
        'total_devoluciones': total_devoluciones,
        'title': 'Dashboard de Devoluciones'
    })

# prestamos/views.py
@login_required
def devolver_prestamo(request, prestamo_id):
    """Vista para devolver un préstamo con cantidades específicas"""
    prestamo = get_object_or_404(Prestamo, id=prestamo_id)
    
    if prestamo.estado != 'activo':
        messages.error(request, 'Este préstamo ya fue devuelto o no está activo.')
        return redirect('prestamos:listar_prestamos')
    
    pendiente = prestamo.pendiente_por_devolver
    
    if request.method == 'POST':
        try:
            buenos = Decimal(request.POST.get('buenos', 0) or 0)
            danados = Decimal(request.POST.get('danados', 0) or 0)
            perdidos = Decimal(request.POST.get('perdidos', 0) or 0)
            
            condicion_devolucion = request.POST.get('condicion_devolucion', '')
            observaciones = request.POST.get('observaciones', '')
            
            # Validar que haya al menos algo para devolver
            if buenos == 0 and danados == 0 and perdidos == 0:
                messages.error(request, 'Debe especificar al menos una cantidad a devolver.')
            else:
                success, message = prestamo.marcar_devuelto_detallado(
                    buenos=buenos,
                    danados=danados,
                    perdidos=perdidos,
                    condicion_devolucion=condicion_devolucion,
                    observaciones=observaciones
                )
                
                if success:
                    # Mensaje según lo devuelto
                    msgs = []
                    if buenos > 0:
                        msgs.append(f"{buenos} en buen estado")
                    if danados > 0:
                        msgs.append(f"{danados} dañados")
                    if perdidos > 0:
                        msgs.append(f"{perdidos} perdidos")
                    
                    messages.success(request, f"Devolución registrada: {', '.join(msgs)}")
                    
                    # Si hay dañados/perdidos, notificar descuento de stock
                    if danados > 0 or perdidos > 0:
                        total_afectado = danados + perdidos
                        messages.warning(
                            request, 
                            f"{total_afectado} unidad(es) se descuentan permanentemente del stock."
                        )
                    
                    return redirect('prestamos:comprobante_prestamo', prestamo_id=prestamo.id)
                else:
                    messages.error(request, message)
                    
        except Exception as e:
            messages.error(request, f'Error al procesar la devolución: {str(e)}')
    
    context = {
        'prestamo': prestamo,
        'pendiente': pendiente,
        'title': 'Devolver Préstamo',
    }
    return render(request, 'prestamos/devolver_prestamo.html', context)

@login_required
def reporte_semanal_consumos(request):
    """Reporte semanal de consumos con parámetro de fecha"""
    # Obtener parámetro de fecha (si existe)
    fecha_param = request.GET.get('fecha')
    
    if fecha_param:
        try:
            fecha_seleccionada = datetime.strptime(fecha_param, '%Y-%m-%d').date()
            hoy = fecha_seleccionada
        except (ValueError, TypeError):
            hoy = timezone.now().date()
    else:
        hoy = timezone.now().date()
    
    # Calcular semana (lunes a domingo)
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    
    # Fechas para navegación
    semana_anterior = inicio_semana - timedelta(days=7)
    semana_siguiente = inicio_semana + timedelta(days=7)
    
    # Filtrar consumos de esta semana
    consumos_semana = Consumo.objects.filter(
        fecha_consumo__date__range=[inicio_semana, fin_semana]
    ).order_by('-fecha_consumo')
    
    # ✅ CORRECCIÓN: Calcular costo usando precio de la herramienta
    costo_total_semanal = 0
    consumos_con_costo = []
    
    for consumo in consumos_semana:
        # Obtener precio de la herramienta
        precio = 0
        if hasattr(consumo.herramienta, 'precio_unitario') and consumo.herramienta.precio_unitario:
            precio = float(consumo.herramienta.precio_unitario)
        elif hasattr(consumo.herramienta, 'costo') and consumo.herramienta.costo:
            precio = float(consumo.herramienta.costo)
        
        # Calcular costo para este consumo
        costo_consumo = float(consumo.cantidad_actual) * precio
        costo_total_semanal += costo_consumo
        
        # Agregar costo calculado al objeto consumo
        consumo.costo_calculado = round(costo_consumo, 2)
        consumo.precio_unitario = round(precio, 2)
        consumos_con_costo.append(consumo)
    
    # Agrupar por tipo de consumo
    consumos_por_tipo = {}
    for consumo in consumos_semana:
        tipo = consumo.get_tipo_consumo_display()
        if tipo not in consumos_por_tipo:
            consumos_por_tipo[tipo] = {
                'cantidad': 0,
                'valor': 0,
                'costo': 0,
                'consumos': []
            }
        
        # Calcular precio unitario de la herramienta
        precio = 0
        if hasattr(consumo.herramienta, 'precio_unitario') and consumo.herramienta.precio_unitario:
            precio = float(consumo.herramienta.precio_unitario)
        elif hasattr(consumo.herramienta, 'costo') and consumo.herramienta.costo:
            precio = float(consumo.herramienta.costo)
        
        costo_consumo = float(consumo.cantidad_actual) * precio
        
        consumos_por_tipo[tipo]['cantidad'] += float(consumo.cantidad_actual)
        consumos_por_tipo[tipo]['valor'] += costo_consumo
        consumos_por_tipo[tipo]['costo'] += costo_consumo
        consumos_por_tipo[tipo]['consumos'].append(consumo)
    
    # Devoluciones de la semana
    devoluciones_semana = DevolucionConsumo.objects.filter(
        fecha_devolucion__date__range=[inicio_semana, fin_semana]
    )
    
    # ✅ CORRECCIÓN: Calcular valor devuelto correctamente
    costo_total_devuelto = 0
    devoluciones_con_costo = []
    
    for devolucion in devoluciones_semana:
        # Obtener precio de la herramienta del consumo
        consumo = devolucion.consumo
        precio = 0
        if hasattr(consumo.herramienta, 'precio_unitario') and consumo.herramienta.precio_unitario:
            precio = float(consumo.herramienta.precio_unitario)
        elif hasattr(consumo.herramienta, 'costo') and consumo.herramienta.costo:
            precio = float(consumo.herramienta.costo)
        
        costo_devuelto = float(devolucion.cantidad_devuelta) * precio
        costo_total_devuelto += costo_devuelto
        
        # Agregar valor calculado
        devolucion.valor_devuelto = round(costo_devuelto, 2)
        devoluciones_con_costo.append(devolucion)
    
    # Totales
    total_consumido = sum([float(c.cantidad_actual) for c in consumos_semana] or [0])
    total_devuelto = sum([float(d.cantidad_devuelta) for d in devoluciones_semana] or [0])
    
    return render(request, 'prestamos/reporte_semanal_consumos.html', {
        'consumos_semana': consumos_con_costo,  # Usar lista con costos calculados
        'devoluciones_semana': devoluciones_con_costo,  # Usar lista con valores calculados
        'consumos_por_tipo': consumos_por_tipo,
        'inicio_semana': inicio_semana,
        'fin_semana': fin_semana,
        'total_consumido': total_consumido,
        'total_devuelto': total_devuelto,
        'costo_total_semanal': round(costo_total_semanal, 2),
        'costo_total_devuelto': round(costo_total_devuelto, 2),
        'semana_anterior': semana_anterior,
        'semana_siguiente': semana_siguiente,
        'fecha_actual': hoy,
        'title': 'Reporte Semanal de Consumos'
    })

# Añade estas importaciones al principio si no están
from django.views.generic import ListView
from django.db.models import Q
from django.utils.dateparse import parse_date
import json

# AÑADE ESTAS VISTAS QUE FALTAN:

@login_required
def listar_prestamos(request):
    """Lista todos los préstamos con filtros"""
    prestamos = Prestamo.objects.all().order_by('-fecha_prestamo')
    
    # Filtros
    estado = request.GET.get('estado')
    if estado:
        prestamos = prestamos.filter(estado=estado)
    
    cliente = request.GET.get('cliente')
    if cliente:
        prestamos = prestamos.filter(cliente__icontains=cliente)
    
    herramienta_nombre = request.GET.get('herramienta')
    if herramienta_nombre:
        prestamos = prestamos.filter(herramienta__nombre__icontains=herramienta_nombre)
    
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    if fecha_inicio:
        prestamos = prestamos.filter(fecha_prestamo__date__gte=fecha_inicio)
    if fecha_fin:
        prestamos = prestamos.filter(fecha_prestamo__date__lte=fecha_fin)
    
    # Estadísticas
    total_prestamos = prestamos.count()
    prestamos_activos = prestamos.filter(estado='activo').count()
    prestamos_devueltos = prestamos.filter(estado='devuelto').count()
    
    # Calcular préstamos vencidos (activos con fecha pasada)
    from django.utils import timezone
    prestamos_vencidos = prestamos.filter(
        estado='activo',
        fecha_devolucion_estimada__lt=timezone.now()
    ).count()
    
    return render(request, 'prestamos/listar_prestamos.html', {
        'prestamos': prestamos,
        'estados': dict(Prestamo.ESTADOS),
        'total_prestamos': total_prestamos,
        'prestamos_activos': prestamos_activos,
        'prestamos_devueltos': prestamos_devueltos,
        'prestamos_vencidos': prestamos_vencidos,
        'title': 'Préstamos Registrados'
    })

@login_required
def devoluciones_menu(request):
    """Menú principal de devoluciones"""
    # Préstamos pendientes de devolución
    prestamos_pendientes = Prestamo.objects.filter(
        estado='activo',
        fecha_devolucion_estimada__lt=timezone.now()
    ).order_by('fecha_devolucion_estimada')[:10]
    
    # Consumos con devolución pendiente
    consumos_pendientes = Consumo.objects.filter(
        cantidad_actual__gt=0
    ).order_by('-fecha_consumo')[:10]
    
    # Estadísticas
    total_prestamos_activos = Prestamo.objects.filter(estado='activo').count()
    total_consumos_activos = Consumo.objects.filter(cantidad_actual__gt=0).count()
    
    return render(request, 'prestamos/devoluciones_menu.html', {
        'prestamos_pendientes': prestamos_pendientes,
        'consumos_pendientes': consumos_pendientes,
        'total_prestamos_activos': total_prestamos_activos,
        'total_consumos_activos': total_consumos_activos,
        'title': 'Menú de Devoluciones'
    })

@login_required
def estadisticas_generales(request):
    """Dashboard con estadísticas generales"""
    from datetime import date, timedelta
    from django.db.models import Sum, Count, Max  # Asegurar importaciones
    
    # Fechas para filtros
    hoy = timezone.now()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    
    # Estadísticas de préstamos
    prestamos_totales = Prestamo.objects.count()
    prestamos_activos = Prestamo.objects.filter(estado='activo').count()
    prestamos_devueltos = Prestamo.objects.filter(estado='devuelto').count()
    prestamos_vencidos = Prestamo.objects.filter(
        estado='activo',
        fecha_devolucion_estimada__lt=timezone.now()
    ).count()
    
    # ✅ NUEVO: Estadísticas de dañados y perdidos
    total_danado = Prestamo.objects.aggregate(
        total=Sum('cantidad_devuelta_danada')
    )['total'] or 0
    
    total_perdido = Prestamo.objects.aggregate(
        total=Sum('cantidad_devuelta_perdida')
    )['total'] or 0
    
    # Dañados y perdidos este mes
    prestamos_este_mes_obj = Prestamo.objects.filter(
        fecha_prestamo__gte=inicio_mes
    )
    danados_este_mes = prestamos_este_mes_obj.aggregate(
        total=Sum('cantidad_devuelta_danada')
    )['total'] or 0
    
    perdidos_este_mes = prestamos_este_mes_obj.aggregate(
        total=Sum('cantidad_devuelta_perdida')
    )['total'] or 0
    
    # Estadísticas de préstamos este mes
    prestamos_este_mes = prestamos_este_mes_obj.count()
    
    # Estadísticas de consumos
    consumos_totales = Consumo.objects.count()
    consumos_activos = Consumo.objects.filter(cantidad_actual__gt=0).count()
    consumos_completados = Consumo.objects.filter(cantidad_actual=0).count()
    
    # Estadísticas de consumos este mes
    consumos_este_mes = Consumo.objects.filter(
        fecha_consumo__gte=inicio_mes
    ).count()
    
    # Estadísticas de ventas
    ventas_totales = Venta.objects.count()
    total_ventas_valor = Venta.objects.aggregate(Sum('total'))['total__sum'] or 0
    
    # Ventas este mes
    ventas_este_mes = Venta.objects.filter(
        fecha_venta__gte=inicio_mes
    ).aggregate(
        total=Sum('total'),
        cantidad=Count('id')
    )
    
    # Herramientas más prestadas (top 10)
    herramientas_populares = Prestamo.objects.values(
        'herramienta__nombre',
        'herramienta__codigo'
    ).annotate(
        total_prestamos=Count('id'),
        ultimo_prestamo=Max('fecha_prestamo')
    ).order_by('-total_prestamos')[:10]
    
    # Herramientas más consumidas (top 10)
    herramientas_consumidas = Consumo.objects.values(
        'herramienta__nombre',
        'herramienta__codigo'
    ).annotate(
        total_consumido=Sum('cantidad_consumida'),
        total_devuelto=Sum('cantidad_devuelta'),
        proyectos=Count('proyecto', distinct=True)
    ).order_by('-total_consumido')[:10]
    
    # Ventas por herramienta (top 10)
    ventas_por_herramienta = Venta.objects.values(
        'herramienta__nombre',
        'herramienta__codigo'
    ).annotate(
        total_ventas=Count('id'),
        total_valor=Sum('total')
    ).order_by('-total_valor')[:10]
    
    # ✅ NUEVO: Herramientas con más dañados/perdidos
    herramientas_danadas_perdidas = Prestamo.objects.values(
        'herramienta__nombre',
        'herramienta__codigo'
    ).annotate(
        total_danado=Sum('cantidad_devuelta_danada'),
        total_perdido=Sum('cantidad_devuelta_perdida'),
        total_afectado=Sum('cantidad_devuelta_danada') + Sum('cantidad_devuelta_perdida')
    ).filter(
        total_afectado__gt=0
    ).order_by('-total_afectado')[:10]
    
    # Estadísticas por mes (últimos 6 meses)
    meses = []
    prestamos_por_mes = []
    ventas_por_mes = []
    consumos_por_mes = []
    danados_por_mes = []
    perdidos_por_mes = []
    
    for i in range(5, -1, -1):
        mes_fecha = hoy - timedelta(days=30*i)
        mes_nombre = mes_fecha.strftime('%b')
        inicio_mes_calc = mes_fecha.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        if i == 0:
            fin_mes_calc = hoy
        else:
            next_month = inicio_mes_calc + timedelta(days=32)
            fin_mes_calc = next_month.replace(day=1) - timedelta(days=1)
        
        meses.append(mes_nombre)
        
        # Prestamos del mes
        prestamos_mes = Prestamo.objects.filter(
            fecha_prestamo__range=[inicio_mes_calc, fin_mes_calc]
        ).count()
        prestamos_por_mes.append(prestamos_mes)
        
        # Ventas del mes
        ventas_mes = Venta.objects.filter(
            fecha_venta__range=[inicio_mes_calc, fin_mes_calc]
        ).aggregate(total=Sum('total'))['total'] or 0
        ventas_por_mes.append(float(ventas_mes))
        
        # Consumos del mes
        consumos_mes = Consumo.objects.filter(
            fecha_consumo__range=[inicio_mes_calc, fin_mes_calc]
        ).count()
        consumos_por_mes.append(consumos_mes)
        
        # ✅ NUEVO: Dañados y perdidos del mes
        prestamos_mes_obj = Prestamo.objects.filter(
            fecha_prestamo__range=[inicio_mes_calc, fin_mes_calc]
        )
        danados_mes = prestamos_mes_obj.aggregate(
            total=Sum('cantidad_devuelta_danada')
        )['total'] or 0
        danados_por_mes.append(float(danados_mes))
        
        perdidos_mes = prestamos_mes_obj.aggregate(
            total=Sum('cantidad_devuelta_perdida')
        )['total'] or 0
        perdidos_por_mes.append(float(perdidos_mes))
    
    # ✅ NUEVO: Estadísticas de devoluciones detalladas
    prestamos_con_devoluciones = Prestamo.objects.filter(
        Q(cantidad_devuelta_buen_estado__gt=0) |
        Q(cantidad_devuelta_danada__gt=0) |
        Q(cantidad_devuelta_perdida__gt=0)
    ).count()
    
    # Porcentaje de devoluciones completas vs parciales
    prestamos_completamente_devueltos = Prestamo.objects.filter(
        estado='devuelto'
    ).count()
    
    context = {
        # Totales
        'prestamos_totales': prestamos_totales,
        'prestamos_activos': prestamos_activos,
        'prestamos_devueltos': prestamos_devueltos,
        'prestamos_vencidos': prestamos_vencidos,
        'prestamos_este_mes': prestamos_este_mes,
        
        # ✅ DAÑADOS Y PERDIDOS
        'total_danado': total_danado,
        'total_perdido': total_perdido,
        'danados_este_mes': danados_este_mes,
        'perdidos_este_mes': perdidos_este_mes,
        
        'consumos_totales': consumos_totales,
        'consumos_activos': consumos_activos,
        'consumos_completados': consumos_completados,
        'consumos_este_mes': consumos_este_mes,
        
        'ventas_totales': ventas_totales,
        'total_ventas_valor': total_ventas_valor,
        'ventas_este_mes_cantidad': ventas_este_mes['cantidad'] or 0,
        'ventas_este_mes_valor': ventas_este_mes['total'] or 0,
        
        # Rankings
        'herramientas_populares': herramientas_populares,
        'herramientas_consumidas': herramientas_consumidas,
        'ventas_por_herramienta': ventas_por_herramienta,
        'herramientas_danadas_perdidas': herramientas_danadas_perdidas,  # ✅ NUEVO
        
        # Gráficos
        'meses': meses,
        'prestamos_por_mes': prestamos_por_mes,
        'ventas_por_mes': ventas_por_mes,
        'consumos_por_mes': consumos_por_mes,
        'danados_por_mes': danados_por_mes,  # ✅ NUEVO
        'perdidos_por_mes': perdidos_por_mes,  # ✅ NUEVO
        
        # Título
        'title': 'Estadísticas Generales',
        
        # Fechas
        'hoy': hoy,
        'inicio_mes': inicio_mes,
        'inicio_semana': inicio_semana,
        
        # ✅ NUEVO: Estadísticas adicionales
        'prestamos_con_devoluciones': prestamos_con_devoluciones,
        'prestamos_completamente_devueltos': prestamos_completamente_devueltos,
    }
    
    return render(request, 'prestamos/estadisticas_generales.html', context)

@login_required
def reporte_semanal(request):
    """Reporte SEMANAL de todas las transacciones"""
    from django.db.models import Sum, Count, F
    
    # Obtener fecha actual
    hoy = timezone.now().date()
    
    # Calcular inicio y fin de semana (lunes a domingo)
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    
    # Si se especifica una fecha en los parámetros
    fecha_param = request.GET.get('fecha')
    if fecha_param:
        try:
            fecha_seleccionada = datetime.strptime(fecha_param, '%Y-%m-%d').date()
            inicio_semana = fecha_seleccionada - timedelta(days=fecha_seleccionada.weekday())
            fin_semana = inicio_semana + timedelta(days=6)
        except (ValueError, TypeError):
            pass
    
    # Préstamos de la semana
    prestamos_semana = Prestamo.objects.filter(
        fecha_prestamo__date__range=[inicio_semana, fin_semana]
    ).order_by('-fecha_prestamo')
    
    # Ventas de la semana
    ventas_semana = Venta.objects.filter(
        fecha_venta__date__range=[inicio_semana, fin_semana]
    ).order_by('-fecha_venta')
    
    # Consumos de la semana
    consumos_semana = Consumo.objects.filter(
        fecha_consumo__date__range=[inicio_semana, fin_semana]
    ).order_by('-fecha_consumo')
    
    # Devoluciones de la semana
    devoluciones_semana = DevolucionConsumo.objects.filter(
        fecha_devolucion__date__range=[inicio_semana, fin_semana]
    ).order_by('-fecha_devolucion')
    
    # ✅ NUEVO: Estadísticas de dañados y perdidos de la semana
    # Dañados de préstamos de esta semana
    total_danados_semana = prestamos_semana.aggregate(
        total=Sum('cantidad_devuelta_danada')
    )['total'] or 0
    
    # Perdidos de préstamos de esta semana
    total_perdidos_semana = prestamos_semana.aggregate(
        total=Sum('cantidad_devuelta_perdida')
    )['total'] or 0
    
    # Préstamos con devoluciones detalladas esta semana
    prestamos_con_devoluciones_semana = prestamos_semana.filter(
        Q(cantidad_devuelta_buen_estado__gt=0) |
        Q(cantidad_devuelta_danada__gt=0) |
        Q(cantidad_devuelta_perdida__gt=0)
    ).count()
    
    # Préstamos completamente devueltos esta semana
    prestamos_completamente_devueltos_semana = prestamos_semana.filter(
        estado='devuelto'
    ).count()
    
    # Préstamos devueltos en buen estado esta semana
    total_buen_estado_semana = prestamos_semana.aggregate(
        total=Sum('cantidad_devuelta_buen_estado')
    )['total'] or 0
    
    # Préstamos parcialmente devueltos esta semana
    prestamos_parcialmente_devueltos_semana = prestamos_semana.filter(
        Q(cantidad_devuelta_buen_estado__gt=0) |
        Q(cantidad_devuelta_danada__gt=0) |
        Q(cantidad_devuelta_perdida__gt=0)
    ).exclude(
        estado='devuelto'
    ).count()
    
    # Totales de la semana
    total_prestamos_semana = prestamos_semana.count()
    total_ventas_semana = ventas_semana.count()
    total_consumos_semana = consumos_semana.count()
    total_devoluciones_semana = devoluciones_semana.count()
    
    # Valores monetarios
    valor_ventas_semana = ventas_semana.aggregate(Sum('total'))['total__sum'] or 0
    valor_consumos_semana = sum([c.costo_estimado or 0 for c in consumos_semana])
    
    # ✅ NUEVO: Valor estimado de dañados y perdidos
    # Suponemos que el costo es el precio de referencia de la herramienta
    valor_danados_semana = 0
    valor_perdidos_semana = 0
    
    for prestamo in prestamos_semana:
        if hasattr(prestamo.herramienta, 'precio_referencia') and prestamo.herramienta.precio_referencia:
            valor_danados_semana += float(prestamo.cantidad_devuelta_danada or 0) * float(prestamo.herramienta.precio_referencia)
            valor_perdidos_semana += float(prestamo.cantidad_devuelta_perdida or 0) * float(prestamo.herramienta.precio_referencia)
    
    # Estadísticas por día de la semana
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    prestamos_por_dia = []
    ventas_por_dia = []
    consumos_por_dia = []
    danados_por_dia = []
    perdidos_por_dia = []
    
    for i in range(7):
        dia_fecha = inicio_semana + timedelta(days=i)
        
        prestamos_dia = prestamos_semana.filter(
            fecha_prestamo__date=dia_fecha
        ).count()
        prestamos_por_dia.append(prestamos_dia)
        
        ventas_dia = ventas_semana.filter(
            fecha_venta__date=dia_fecha
        ).aggregate(total=Sum('total'))['total'] or 0
        ventas_por_dia.append(float(ventas_dia))
        
        consumos_dia = consumos_semana.filter(
            fecha_consumo__date=dia_fecha
        ).count()
        consumos_por_dia.append(consumos_dia)
        
        # ✅ NUEVO: Dañados y perdidos por día
        prestamos_dia_obj = prestamos_semana.filter(
            fecha_prestamo__date=dia_fecha
        )
        danados_dia = prestamos_dia_obj.aggregate(
            total=Sum('cantidad_devuelta_danada')
        )['total'] or 0
        danados_por_dia.append(float(danados_dia))
        
        perdidos_dia = prestamos_dia_obj.aggregate(
            total=Sum('cantidad_devuelta_perdida')
        )['total'] or 0
        perdidos_por_dia.append(float(perdidos_dia))
    
    # Préstamos por estado
    prestamos_activos_semana = prestamos_semana.filter(estado='activo').count()
    prestamos_devueltos_semana = prestamos_semana.filter(estado='devuelto').count()
    
    # Consumos por tipo
    try:
        consumos_por_tipo = {}
        for consumo in consumos_semana:
            tipo = consumo.get_tipo_consumo_display() if hasattr(consumo, 'tipo_consumo') else 'General'
            if tipo not in consumos_por_tipo:
                consumos_por_tipo[tipo] = 0
            consumos_por_tipo[tipo] += 1
    except:
        consumos_por_tipo = {'General': total_consumos_semana}
    
    # ✅ NUEVO: Herramientas con más dañados/perdidos esta semana
    herramientas_danadas_perdidas_semana = prestamos_semana.values(
        'herramienta__nombre',
        'herramienta__codigo'
    ).annotate(
        total_danado=Sum('cantidad_devuelta_danada'),
        total_perdido=Sum('cantidad_devuelta_perdida'),
        total_afectado=Sum('cantidad_devuelta_danada') + Sum('cantidad_devuelta_perdida')
    ).filter(
        total_afectado__gt=0
    ).order_by('-total_afectado')[:5]
    
    # ✅ NUEVO: Estadísticas de devolución
    devoluciones_detalladas = {
        'buen_estado': total_buen_estado_semana,
        'danados': total_danados_semana,
        'perdidos': total_perdidos_semana,
        'total_devuelto': total_buen_estado_semana + total_danados_semana + total_perdidos_semana
    }
    
    context = {
        # Fechas
        'inicio_semana': inicio_semana,
        'fin_semana': fin_semana,
        'hoy': hoy,
        
        # Datos
        'prestamos_semana': prestamos_semana,
        'ventas_semana': ventas_semana,
        'consumos_semana': consumos_semana,
        'devoluciones_semana': devoluciones_semana,
        
        # Totales
        'total_prestamos_semana': total_prestamos_semana,
        'total_ventas_semana': total_ventas_semana,
        'total_consumos_semana': total_consumos_semana,
        'total_devoluciones_semana': total_devoluciones_semana,
        
        # ✅ NUEVO: Estadísticas de dañados y perdidos
        'total_danados_semana': total_danados_semana,
        'total_perdidos_semana': total_perdidos_semana,
        'total_buen_estado_semana': total_buen_estado_semana,
        'prestamos_con_devoluciones_semana': prestamos_con_devoluciones_semana,
        'prestamos_completamente_devueltos_semana': prestamos_completamente_devueltos_semana,
        'prestamos_parcialmente_devueltos_semana': prestamos_parcialmente_devueltos_semana,
        'valor_danados_semana': valor_danados_semana,
        'valor_perdidos_semana': valor_perdidos_semana,
        
        # Valores
        'valor_ventas_semana': valor_ventas_semana,
        'valor_consumos_semana': valor_consumos_semana,
        
        # Estadísticas por estado
        'prestamos_activos_semana': prestamos_activos_semana,
        'prestamos_devueltos_semana': prestamos_devueltos_semana,
        
        # Gráficos
        'dias_semana': dias_semana,
        'prestamos_por_dia': prestamos_por_dia,
        'ventas_por_dia': ventas_por_dia,
        'consumos_por_dia': consumos_por_dia,
        'danados_por_dia': danados_por_dia,  # ✅ NUEVO
        'perdidos_por_dia': perdidos_por_dia,  # ✅ NUEVO
        'consumos_por_tipo': consumos_por_tipo,
        
        # ✅ NUEVO: Herramientas afectadas
        'herramientas_danadas_perdidas_semana': herramientas_danadas_perdidas_semana,
        'devoluciones_detalladas': devoluciones_detalladas,
        
        # Navegación
        'semana_anterior': inicio_semana - timedelta(days=7),
        'semana_siguiente': inicio_semana + timedelta(days=7),
        
        # Título
        'title': f'Reporte Semanal - {inicio_semana.strftime("%d/%m/%Y")} al {fin_semana.strftime("%d/%m/%Y")}',
    }
    
    return render(request, 'prestamos/reporte_semanal.html', context)


@login_required
def comprobante_devolucion_prestamo(request, prestamo_id):
    """Vista para mostrar el comprobante de devolución de préstamo"""
    prestamo = get_object_or_404(Prestamo, id=prestamo_id)
    
    # Obtener los parámetros de la devolución
    buenos = Decimal(request.GET.get('buenos', 0))
    danados = Decimal(request.GET.get('danados', 0))
    perdidos = Decimal(request.GET.get('perdidos', 0))
    condicion = request.GET.get('condicion', '')
    observaciones = request.GET.get('observaciones', '')
    
    total_devuelto = buenos + danados + perdidos
    
    context = {
        'prestamo': prestamo,
        'buenos': buenos,
        'danados': danados,
        'perdidos': perdidos,
        'total_devuelto': total_devuelto,
        'condicion_devolucion': condicion,
        'observaciones': observaciones,
        'title': 'Comprobante de Devolución',
    }
    
    return render(request, 'prestamos/comprobante_devolucion_prestamo.html', context)


@login_required
def comprobante_devolucion_prestamo_print(request, prestamo_id):
    """Vista para imprimir el comprobante de devolución de préstamo"""
    prestamo = get_object_or_404(Prestamo, id=prestamo_id)
    
    # Obtener los parámetros de la devolución
    buenos = Decimal(request.GET.get('buenos', 0))
    danados = Decimal(request.GET.get('danados', 0))
    perdidos = Decimal(request.GET.get('perdidos', 0))
    condicion = request.GET.get('condicion', '')
    observaciones = request.GET.get('observaciones', '')
    
    total_devuelto = buenos + danados + perdidos
    
    context = {
        'prestamo': prestamo,
        'buenos': buenos,
        'danados': danados,
        'perdidos': perdidos,
        'total_devuelto': total_devuelto,
        'condicion_devolucion': condicion,
        'observaciones': observaciones,
        'title': 'Comprobante de Devolución - Kema Constructora',
    }
    
    return render(request, 'prestamos/comprobante_devolucion_prestamo_print.html', context)
