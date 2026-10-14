from django import forms
from django.utils import timezone
from .models import Prestamo, Venta, Consumo, DevolucionConsumo
from inventario.models import Herramienta

# ==================== PRÉSTAMOS ====================

# prestamos/forms.py
class PrestamoForm(forms.ModelForm):
    # ✅ AÑADE ESTOS CAMPOS NUEVOS
    TIPO_CLIENTE_CHOICES = [
        ('empleado', 'Empleado'),
        ('externo', 'Cliente Externo'),
    ]
    
    tipo_cliente = forms.ChoiceField(
        choices=TIPO_CLIENTE_CHOICES,
        initial='empleado',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='Tipo de Cliente'
    )
    
    cedula_externo = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Cédula o identificación'
        }),
        label='Cédula Cliente Externo'
    )
    
    class Meta:
        model = Prestamo
        fields = [
            'herramienta', 'empleado', 'cliente_externo', 'cedula_externo',
            'cantidad_prestada', 'condicion_prestamo', 'observaciones', 'fecha_devolucion_estimada'  # ✅ COMA AÑADIDA
        ]
        widgets = {
            'condicion_prestamo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describa el estado de la herramienta al prestarla'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones adicionales (opcional)'
            }),
            'herramienta': forms.Select(attrs={
                'class': 'form-control',
                'onchange': 'actualizarDisponible(this.value)'
            }),
            'empleado': forms.Select(attrs={'class': 'form-control'}),
            'cliente_externo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre completo del cliente externo'
            }),
            'cantidad_prestada': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'fecha_devolucion_estimada': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'min': timezone.now().date().isoformat()
            }),
        }
        labels = {
            'fecha_devolucion_estimada': 'Fecha estimada de devolución',
            'cantidad_prestada': 'Cantidad a prestar',
            'cliente_externo': 'Nombre Cliente Externo',
        }
    
    # ... (el resto de tu código está bien)
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # ✅ Inicializar tipo_cliente según datos existentes
        if self.instance and self.instance.pk:
            if self.instance.empleado:
                self.initial['tipo_cliente'] = 'empleado'
            elif self.instance.cliente_externo:
                self.initial['tipo_cliente'] = 'externo'
        
        # ✅ Filtrar herramientas con stock disponible
        if 'herramienta' in self.fields:
            self.fields['herramienta'].queryset = Herramienta.objects.filter(
                estado='disponible'
            ).order_by('nombre')
        
        # ✅ Hacer que cedula_externo no sea requerido inicialmente
        self.fields['cedula_externo'].required = False
        
        # ✅ Configurar campos según tipo de cliente
        if self.initial.get('tipo_cliente', 'empleado') == 'empleado':
            self.fields['cliente_externo'].required = False
            self.fields['cedula_externo'].required = False
        else:
            self.fields['empleado'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        herramienta = cleaned_data.get('herramienta')
        cantidad = cleaned_data.get('cantidad_prestada')
        empleado = cleaned_data.get('empleado')
        cliente_externo = cleaned_data.get('cliente_externo')
        cedula_externo = cleaned_data.get('cedula_externo')
        tipo_cliente = cleaned_data.get('tipo_cliente')
        
        # ✅ Validar tipo de cliente
        if not tipo_cliente:
            raise forms.ValidationError('Debe seleccionar un tipo de cliente')
        
        if tipo_cliente == 'empleado' and not empleado:
            raise forms.ValidationError({
                'empleado': 'Debe seleccionar un empleado cuando el tipo es "Empleado"'
            })
        
        if tipo_cliente == 'externo':
            if not cliente_externo:
                raise forms.ValidationError({
                    'cliente_externo': 'Debe ingresar el nombre del cliente externo'
                })
            # Cédula es opcional para externos, pero si se ingresa, validar formato
            if cedula_externo and not cedula_externo.strip().isdigit():
                raise forms.ValidationError({
                    'cedula_externo': 'La cédula debe contener solo números'
                })
        
        # ✅ Validar que haya al menos un destinatario
        if not empleado and not cliente_externo:
            raise forms.ValidationError(
                'Debe especificar un empleado o un cliente externo'
            )
        
        # ✅ Validar stock disponible
        if herramienta and cantidad:
            if cantidad <= 0:
                raise forms.ValidationError({
                    'cantidad_prestada': 'La cantidad debe ser mayor a 0'
                })
            
            disponible = herramienta.stock_disponible
            if cantidad > disponible:
                raise forms.ValidationError({
                    'cantidad_prestada': f'Stock insuficiente. Disponible: {disponible}'
                })
        
        # ✅ Validar fecha de devolución
        fecha_devolucion = cleaned_data.get('fecha_devolucion_estimada')
        if fecha_devolucion and fecha_devolucion < timezone.now().date():
            raise forms.ValidationError({
                'fecha_devolucion_estimada': 'La fecha de devolución no puede ser en el pasado'
            })
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # ✅ Asignar prestado_por
        if self.user:
            instance.prestado_por = self.user
        
        # ✅ Limpiar campos según tipo de cliente
        tipo_cliente = self.cleaned_data.get('tipo_cliente')
        if tipo_cliente == 'empleado':
            instance.cliente_externo = None
            instance.cedula_externo = None
        elif tipo_cliente == 'externo':
            instance.empleado = None
        
        if commit:
            instance.save()
        
        return instance

class DevolucionPrestamoForm(forms.ModelForm):
    class Meta:
        model = Prestamo
        fields = ['condicion_devolucion', 'estado', 'observaciones']
        widgets = {
            'condicion_devolucion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Condición en que se devuelve la herramienta'
            }),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones adicionales'
            }),
        }

# ==================== VENTAS ====================
class VentaForm(forms.ModelForm):
    precio_unitario = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    class Meta:
        model = Venta
        fields = [
            'herramienta', 'cantidad_vendida', 'precio_unitario',
            'cliente_nombre', 'cliente_cedula', 'cliente_telefono'
        ]
        widgets = {
            'herramienta': forms.Select(attrs={
                'class': 'form-control',
                'onchange': 'actualizarPrecio(this.value)'
            }),
            'cantidad_vendida': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'cliente_nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre completo del cliente'
            }),
            'cliente_cedula': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Cédula/RUC'
            }),
            'cliente_telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Teléfono de contacto'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if 'herramienta' in self.fields:
            self.fields['herramienta'].queryset = Herramienta.objects.filter(
                estado='disponible'
            ).order_by('nombre')
    
    def clean(self):
        cleaned_data = super().clean()
        herramienta = cleaned_data.get('herramienta')
        cantidad = cleaned_data.get('cantidad_vendida')
        precio = cleaned_data.get('precio_unitario')
        
        if herramienta and cantidad:
            if cantidad <= 0:
                raise forms.ValidationError({
                    'cantidad_vendida': 'La cantidad debe ser mayor a 0'
                })
            
            disponible = herramienta.stock_disponible
            if cantidad > disponible:
                raise forms.ValidationError({
                    'cantidad_vendida': f'Stock insuficiente. Disponible: {disponible}'
                })
        
        if precio and precio <= 0:
            raise forms.ValidationError({
                'precio_unitario': 'El precio debe ser mayor a 0'
            })
        
        return cleaned_data

# ==================== CONSUMOS ====================
class ConsumoForm(forms.ModelForm):
    class Meta:
        model = Consumo
        fields = [
            'herramienta', 'proyecto', 'empleado_responsable',
            'cantidad_consumida', 'tipo_consumo', 'descripcion'
        ]
        widgets = {
            'herramienta': forms.Select(attrs={
                'class': 'form-control',
                'onchange': 'actualizarDisponibleConsumo(this.value)'
            }),
            'proyecto': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del proyecto o área'
            }),
            'empleado_responsable': forms.Select(attrs={'class': 'form-control'}),
            'cantidad_consumida': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'tipo_consumo': forms.Select(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Detalle del uso del material'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if 'herramienta' in self.fields:
            self.fields['herramienta'].queryset = Herramienta.objects.filter(
                estado='disponible'
            ).order_by('nombre')
    
    def clean(self):
        cleaned_data = super().clean()
        herramienta = cleaned_data.get('herramienta')
        cantidad = cleaned_data.get('cantidad_consumida')
        
        if herramienta and cantidad:
            if cantidad <= 0:
                raise forms.ValidationError({
                    'cantidad_consumida': 'La cantidad debe ser mayor a 0'
                })
            
            disponible = herramienta.stock_disponible
            if cantidad > disponible:
                raise forms.ValidationError({
                    'cantidad_consumida': f'Stock insuficiente. Disponible: {disponible}'
                })
        
        return cleaned_data

class DevolucionConsumoForm(forms.ModelForm):
    class Meta:
        model = DevolucionConsumo
        fields = ['cantidad_devuelta', 'motivo', 'observaciones']
        widgets = {
            'cantidad_devuelta': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'motivo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Motivo de la devolución'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones adicionales'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.consumo = kwargs.pop('consumo', None)
        super().__init__(*args, **kwargs)
        
        if self.consumo:
            # Establecer máximo que se puede devolver
            max_devolucion = self.consumo.cantidad_actual
            self.fields['cantidad_devuelta'].widget.attrs['max'] = max_devolucion
            self.fields['cantidad_devuelta'].help_text = f'Máximo a devolver: {max_devolucion}'
    
    def clean_cantidad_devuelta(self):
        cantidad = self.cleaned_data['cantidad_devuelta']
        
        if self.consumo:
            if cantidad <= 0:
                raise forms.ValidationError('La cantidad debe ser mayor a 0')
            
            if cantidad > self.consumo.cantidad_actual:
                raise forms.ValidationError(
                    f'No puede devolver más de {self.consumo.cantidad_actual}'
                )
        
        return cantidad

# ==================== FILTROS ====================
class FiltroPrestamosForm(forms.Form):
    ESTADO_CHOICES = [
        ('', 'Todos'),
        ('activo', 'Activos'),
        ('devuelto', 'Devueltos'),
        ('vencido', 'Vencidos'),
        ('danado', 'Dañados'),
    ]
    
    estado = forms.ChoiceField(
        choices=ESTADO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    herramienta = forms.ModelChoiceField(
        queryset=Herramienta.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        fecha_desde = cleaned_data.get('fecha_desde')
        fecha_hasta = cleaned_data.get('fecha_hasta')
        
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            raise forms.ValidationError(
                'La fecha "desde" no puede ser mayor a la fecha "hasta"'
            )
        
        return cleaned_data

class FiltroVentasForm(forms.Form):
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    cliente_nombre = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre del cliente'
        })
    )
    
    herramienta = forms.ModelChoiceField(
        queryset=Herramienta.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class FiltroConsumosForm(forms.Form):
    TIPO_CHOICES = [
        ('', 'Todos'),
        ('obra', 'Obra/Proyecto'),
        ('mantenimiento', 'Mantenimiento'),
        ('reparacion', 'Reparación'),
        ('otro', 'Otro'),
    ]
    
    ESTADO_CHOICES = [
        ('', 'Todos'),
        ('activo', 'Activos'),
        ('parcial_devuelto', 'Parcialmente Devueltos'),
        ('total_devuelto', 'Totalmente Devueltos'),
    ]
    
    tipo_consumo = forms.ChoiceField(
        choices=TIPO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    estado = forms.ChoiceField(
        choices=ESTADO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    proyecto = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre del proyecto'
        })
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )