from django.contrib import admin

from .models import EntregaEPP, Incidente, Inspeccion, Protocolo

admin.site.register(Protocolo)
admin.site.register(Inspeccion)
admin.site.register(Incidente)
admin.site.register(EntregaEPP)
