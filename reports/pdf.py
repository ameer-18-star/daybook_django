"""
PDF export helper — renders a Django template to a downloadable PDF
using xhtml2pdf (pure Python, no system-level dependencies like
wkhtmltopdf/Cairo, so it installs cleanly via pip on any host).
"""
from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa


def render_to_pdf(template_name: str, context: dict, filename: str) -> HttpResponse:
    html = render_to_string(template_name, context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse(
            'We hit an error generating this PDF. Please try again or use the web report instead.',
            status=500,
        )
    return response
