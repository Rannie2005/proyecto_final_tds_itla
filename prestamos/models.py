from django.db import models
from inventario.models import Herramienta
# ❌ QUITA esta línea: from empleados.models import Empleado
from django.utils import timezone

from django.db import models
from django.utils import timezone

class Prestamo(models.Model):
    ESTADOS = [
        ('activo', 'Activo'),
        ('devuelto', 'Devuelto'),
        ('vencido', 'Vencido'),
        # ❌ ELIMINAR 'danado' y 'perdido' de aquí
    ]
    
    herramienta = models.ForeignKey('inventario.Herramienta', on_delete=models.PROTECT)
    empleado = models.ForeignKey('empleados.Empleado', on_delete=models.PROTECT, blank=True, null=True)
    cliente_externo = models.CharField(max_length=100, blank=True, null=True)
    cedula_externo = models.CharField(max_length=20, blank=True, null=True)
    cantidad_prestada = models.DecimalField(max_digits=10, decimal_places=2)
    
    fecha_prestamo = models.DateTimeField(auto_now_add=True)
    fecha_devolucion_estimada = models.DateField()
    fecha_devolucion_real = models.DateTimeField(blank=True, null=True)
    
    condicion_prestamo = models.TextField(blank=True, null=True)
    condicion_devolucion = models.TextField(blank=True, null=True)
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='activo')
    observaciones = models.TextField(blank=True, null=True)
    
    # ✅ NUEVOS CAMPOS PARA DEVOLUCIÓN DETALLADA
    cantidad_devuelta_buen_estado = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    cantidad_devuelta_danada = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    cantidad_devuelta_perdida = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    
    prestado_por = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    
    def __str__(self):
        if self.empleado:
            return f"Préstamo {self.id} - {self.herramienta} a {self.empleado}"
        else:
            return f"Préstamo {self.id} - {self.herramienta} a {self.cliente_externo}"
    
    def save(self, *args, **kwargs):
        # Si es un nuevo préstamo activo
        if not self.id and self.estado == 'activo':
            # Verificar stock disponible
            disponible = self.herramienta.stock_disponible
            if self.cantidad_prestada > disponible:
                raise ValueError(f'Stock insuficiente. Disponible: {disponible}')
        
        super().save(*args, **kwargs)

    def quien_recibe(self):
        """Devuelve quién recibió el préstamo"""
        if self.empleado:
            return f"{self.empleado.nombre} (Empleado)"
        else:
            return f"{self.cliente_externo} (Externo)"
    
    @property
    def cantidad_total_devuelta(self):
        """Total de artículos devueltos en cualquier estado"""
        return (
            self.cantidad_devuelta_buen_estado +
            self.cantidad_devuelta_danada +
            self.cantidad_devuelta_perdida
        )
    
    @property
    def pendiente_por_devolver(self):
        """Cantidad que aún no ha sido devuelta"""
        return self.cantidad_prestada - self.cantidad_total_devuelta
    
    @property
    def afecta_stock_permanentemente(self):
        """
        Determina si este préstamo afecta el stock disponible permanentemente
        Solo los dañados/perdidos afectan permanentemente
        """
        return self.cantidad_devuelta_danada > 0 or self.cantidad_devuelta_perdida > 0
    
    @property
    def cantidad_a_descontar(self):
        """
        Cantidad que debe descontarse permanentemente del stock
        """
        return self.cantidad_devuelta_danada + self.cantidad_devuelta_perdida
    
    @property
    def es_completamente_devuelto(self):
        """Verifica si todo fue devuelto"""
        return self.cantidad_total_devuelta >= self.cantidad_prestada
    
    def marcar_devuelto_detallado(self, buenos=0, danados=0, perdidos=0, 
                                condicion_devolucion="", observaciones=""):
        """
        Registra una devolución con cantidades específicas para cada estado
        """
        if self.estado != 'activo':
            return False, "El préstamo no está activo"
        
        # Validar que las cantidades sean positivas
        if any(x < 0 for x in [buenos, danados, perdidos]):
            return False, "Las cantidades no pueden ser negativas"
        
        # Validar que no se devuelva más de lo prestado
        total_devolucion = buenos + danados + perdidos
        pendiente = self.pendiente_por_devolver
        
        if total_devolucion > pendiente:
            return False, f"No puedes devolver más de {pendiente} unidades"
        
        # Actualizar cantidades
        self.cantidad_devuelta_buen_estado += buenos
        self.cantidad_devuelta_danada += danados
        self.cantidad_devuelta_perdida += perdidos
        
        # Actualizar fecha de devolución real si es la primera devolución
        if self.fecha_devolucion_real is None:
            self.fecha_devolucion_real = timezone.now()
        
        # Actualizar campos adicionales
        if condicion_devolucion:
            self.condicion_devolucion = condicion_devolucion
        if observaciones:
            if self.observaciones:
                self.observaciones += f"\n---\n{observaciones}"
            else:
                self.observaciones = observaciones
        
        # Si todo fue devuelto, marcar como devuelto
        if self.es_completamente_devuelto:
            self.estado = 'devuelto'
        
        self.save()
        return True, "Devolución registrada exitosamente"

class Venta(models.Model):
    herramienta = models.ForeignKey(Herramienta, on_delete=models.PROTECT)
    cantidad_vendida = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    cliente_nombre = models.CharField(max_length=100)
    cliente_cedula = models.CharField(max_length=20, blank=True, null=True)
    cliente_telefono = models.CharField(max_length=15, blank=True, null=True)
    
    fecha_venta = models.DateTimeField(auto_now_add=True)
    numero_factura = models.CharField(max_length=20, unique=True)
    
    vendedor = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    
    def save(self, *args, **kwargs):
        # Calcular el total
        self.total = self.cantidad_vendida * self.precio_unitario
        
        # Generar número de factura automático si no existe
        if not self.numero_factura:
            from django.db.models import Max
            ultimo_numero = Venta.objects.aggregate(
                max_id=Max('id')
            )['max_id'] or 0
            self.numero_factura = f"FACT-{ultimo_numero + 1:04d}"
        
        # Verificar stock disponible antes de guardar
        disponible = self.herramienta.stock_disponible
        if self.cantidad_vendida > disponible:
            raise ValueError(f'Stock insuficiente. Disponible: {disponible}')
        
        # Guardar la venta
        super().save(*args, **kwargs)
        
    
    def __str__(self):
        return f"Venta {self.numero_factura} - {self.cliente_nombre}"
    
    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'

# prestamos/models.py (agregar al final)

# prestamos/models.py (agregar después del modelo Venta)
from django.db import models
from django.utils import timezone

class Consumo(models.Model):
    """Modelo para registrar consumo interno de materiales NO retornables"""
    ESTADOS_CONSUMO = [
        ('activo', 'Consumido'),  # Material consumido
        ('parcial_devuelto', 'Parcialmente Devuelto'),  # Se devolvió parte
        ('total_devuelto', 'Totalmente Devuelto'),  # Se devolvió todo
    ]
    
    TIPOS_CONSUMO = [
        ('obra', 'Para Obra/Proyecto'),
        ('mantenimiento', 'Mantenimiento'),
        ('reparacion', 'Reparación'),
        ('otro', 'Otro'),
    ]
    
    herramienta = models.ForeignKey('inventario.Herramienta', on_delete=models.PROTECT)
    proyecto = models.CharField(max_length=100, help_text="Nombre del proyecto o área de trabajo")
    empleado_responsable = models.ForeignKey(
        'empleados.Empleado', 
        on_delete=models.PROTECT,
        blank=True, 
        null=True,
        help_text="Empleado que consume el material"
    )
    
    cantidad_consumida = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad_devuelta = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # consumida - devuelta
    
    tipo_consumo = models.CharField(max_length=20, choices=TIPOS_CONSUMO, default='obra')
    descripcion = models.TextField(help_text="Descripción del consumo o uso")
    observaciones = models.TextField(blank=True, null=True)
    
    fecha_consumo = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    estado = models.CharField(max_length=20, choices=ESTADOS_CONSUMO, default='activo')
    
    registrado_por = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    
    def save(self, *args, **kwargs):
        # Si es nuevo
        if not self.id:
            # Verificar stock disponible
            disponible = self.herramienta.stock_disponible
            if self.cantidad_consumida > disponible:
                raise ValueError(f'Stock insuficiente. Disponible: {disponible}')
            
            # Inicializar cantidad_actual
            self.cantidad_actual = self.cantidad_consumida
        else:
            # Si ya existe, recalcular cantidad_actual
            self.cantidad_actual = self.cantidad_consumida - self.cantidad_devuelta
        
        # Calcular estado basado en cantidades
        if self.cantidad_devuelta == 0:
            self.estado = 'activo'
        elif self.cantidad_devuelta < self.cantidad_consumida:
            self.estado = 'parcial_devuelto'
        else:
            self.estado = 'total_devuelto'
        
        # Guardar el consumo
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = 'Consumo Interno'
        verbose_name_plural = 'Consumos Internos'
        ordering = ['-fecha_consumo']
    
    def __str__(self):
        return f"Consumo {self.id} - {self.herramienta} ({self.proyecto})"
    
    
    
    @property
    def porcentaje_devuelto(self):
        """Porcentaje devuelto del consumo"""
        if self.cantidad_consumida > 0:
            return (self.cantidad_devuelta / self.cantidad_consumida) * 100
        return 0
    
    @property
    def costo_estimado(self):
        """Calcula el costo estimado basado en precio unitario"""
        if hasattr(self.herramienta, 'precio_referencia') and self.herramienta.precio_referencia:
            return self.cantidad_actual * self.herramienta.precio_referencia
        return 0
    
    def puede_devolver(self):
        """Verifica si se puede devolver más material"""
        return self.cantidad_actual > 0

class DevolucionConsumo(models.Model):

    """Modelo para registrar devoluciones de consumo"""
    consumo = models.ForeignKey(Consumo, on_delete=models.PROTECT, related_name='devoluciones')
    cantidad_devuelta = models.DecimalField(max_digits=10, decimal_places=2)
    motivo = models.TextField(help_text="Motivo de la devolución")
    observaciones = models.TextField(blank=True, null=True)
    
    fecha_devolucion = models.DateTimeField(auto_now_add=True)
    devuelto_por = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    
    class Meta:
        verbose_name = 'Devolución de Consumo'
        verbose_name_plural = 'Devoluciones de Consumo'
        ordering = ['-fecha_devolucion']
    
    def __str__(self):
        return f"Devolución {self.id} - {self.cantidad_devuelta} de Consumo {self.consumo.id}"
    

# En models.py, después de definir los modelos
from django.db.models.signals import post_delete
from django.dispatch import receiver

