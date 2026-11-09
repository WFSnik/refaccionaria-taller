from .models import AlertaReorden


def alertas_pendientes(request):
    if not request.user.is_authenticated:
        return {}
    return {"alertas_pendientes": AlertaReorden.objects.filter(estado=AlertaReorden.Estado.PENDIENTE).count()}
