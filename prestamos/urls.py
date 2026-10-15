from django.urls import path, include
from . import views

app_name = 'prestamos'

urlpatterns = [
    # URLs para Préstamos
    path('inventario/', include('inventario.urls')),
    path('prestamo/crear/', views.crear_prestamo, name='crear_prestamo'),
    path('prestamo/crear/<int:herramienta_id>/', views.crear_prestamo, name='crear_prestamo_herramienta'),
    path('prestamo/<int:prestamo_id>/comprobante/', views.comprobante_prestamo, name='comprobante_prestamo'),
    path('prestamo/<int:prestamo_id>/descargar-pdf/', views.descargar_pdf_prestamo, name='descargar_pdf_prestamo'),
    path('prestamos/', views.listar_prestamos, name='listar_prestamos'),
    path('comprobante-devolucion/<int:prestamo_id>/', views.comprobante_devolucion_prestamo, name='comprobante_devolucion_prestamo'),
    path('comprobante-devolucion/<int:prestamo_id>/print/', views.comprobante_devolucion_prestamo_print, name='comprobante_devolucion_prestamo_print'),
    
    # URLs para Ventas
    path('venta/crear/', views.crear_venta, name='crear_venta'),
    path('venta/crear/<int:herramienta_id>/', views.crear_venta, name='crear_venta_herramienta'),
    path('venta/<int:venta_id>/factura/', views.factura_venta, name='factura_venta'),
    path('venta/<int:venta_id>/descargar-pdf/', views.descargar_pdf_venta, name='descargar_pdf_venta'),
    path('ventas/', views.listar_ventas, name='listar_ventas'),
    
    # URLs para Consumos
    path('consumo/crear/', views.crear_consumo, name='crear_consumo'),
    path('consumo/crear/<int:herramienta_id>/', views.crear_consumo, name='crear_consumo_herramienta'),
    path('consumo/<int:consumo_id>/comprobante/', views.comprobante_consumo, name='comprobante_consumo'),
    path('consumo/<int:consumo_id>/devolver/', views.devolver_consumo, name='devolver_consumo'),
    path('consumos/', views.listar_consumos, name='listar_consumos'),
    
    # URLs para Devoluciones
    path('prestamo/<int:prestamo_id>/devolver/', views.devolver_prestamo, name='devolver_prestamo'),
    path('devoluciones/menu/', views.devoluciones_menu, name='devoluciones_menu'),
    path('devoluciones/dashboard/', views.dashboard_devoluciones, name='dashboard_devoluciones'),
    
    
    # URLs para Reportes y Estadísticas
    path('estadisticas/', views.estadisticas_generales, name='estadisticas_generales'),
    path('reporte/semanal/', views.reporte_semanal, name='reporte_semanal'),
    path('reporte/semanal-consumos/', views.reporte_semanal_consumos, name='reporte_semanal_consumos'),
]