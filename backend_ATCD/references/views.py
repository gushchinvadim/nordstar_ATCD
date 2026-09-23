# references/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Citizenship, AircraftType, StudentProfession

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def citizenships_list(request):
    """Список гражданств"""
    citizenships = Citizenship.objects.all().order_by('name')
    data = [{'id': c.id, 'name': c.name} for c in citizenships]
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def aircraft_types_list(request):
    """Список типов ВС"""
    aircraft_types = AircraftType.objects.all().order_by('name')
    data = [{'id': a.id, 'name': a.name} for a in aircraft_types]
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def professions_list(request):
    """Список профессий"""
    professions = StudentProfession.objects.all().order_by('name')
    data = [{'id': p.id, 'name': p.name} for p in professions]
    return Response(data)