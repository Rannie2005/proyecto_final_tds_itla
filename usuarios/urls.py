from django.urls import path, include
from . import views

app_name = 'usuarios'  

urlpatterns = [
    path('', views.tablero, name='tablero'),
    path('login/', views.iniciar_sesion, name='iniciar_sesion'),
    path('logout/', views.cerrar_sesion, name='cerrar_sesion'),
    path('inventario/', include('inventario.urls')),
    path('acciones/', include('prestamos.urls')),
]