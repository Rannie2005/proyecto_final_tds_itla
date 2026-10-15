# prestamos/utils.py
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import os
from django.conf import settings
from django.utils import timezone

def generar_pdf_prestamo(prestamo):
    """Genera un PDF profesional para préstamos"""
    try:
        # Crear nombre de archivo
        filename = f"comprobante_prestamo_{prestamo.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(settings.MEDIA_ROOT, 'pdfs', filename)
        
        # Asegurarse de que el directorio existe
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Crear documento
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        
        # ... (todo el contenido del PDF que ya tienes)
        
        # Generar PDF
        doc.build(story)
        
        print(f"PDF de préstamo generado exitosamente: {filepath}")
        return filepath, filename
        
    except Exception as e:
        print(f"Error en generar_pdf_prestamo: {str(e)}")
        # Crear un archivo de error temporal
        error_filename = f"error_prestamo_{prestamo.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.txt"
        error_filepath = os.path.join(settings.MEDIA_ROOT, 'pdfs', error_filename)
        os.makedirs(os.path.dirname(error_filepath), exist_ok=True)
        
        with open(error_filepath, 'w') as f:
            f.write(f"Error generando PDF: {str(e)}")
        
        return error_filepath, error_filename

def generar_pdf_venta(venta):
    """Genera un PDF profesional para ventas"""
    try:
        # Crear nombre de archivo
        filename = f"factura_venta_{venta.numero_factura}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(settings.MEDIA_ROOT, 'pdfs', filename)
        
        # Asegurarse de que el directorio existe
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Crear documento
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        
        # ... (todo el contenido del PDF que ya tienes)
        
        # Generar PDF
        doc.build(story)
        
        print(f"PDF de venta generado exitosamente: {filepath}")
        return filepath, filename
        
    except Exception as e:
        print(f"Error en generar_pdf_venta: {str(e)}")
        # Crear un archivo de error temporal
        error_filename = f"error_venta_{venta.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.txt"
        error_filepath = os.path.join(settings.MEDIA_ROOT, 'pdfs', error_filename)
        os.makedirs(os.path.dirname(error_filepath), exist_ok=True)
        
        with open(error_filepath, 'w') as f:
            f.write(f"Error generando PDF: {str(e)}")
        
        return error_filepath, error_filename