# references/urls.py
from django.urls import path
from . import views

app_name = 'references'

urlpatterns = [

    path('execution/references/citizenships/', views.citizenships_list, name='citizenships-list'),
    path('execution/references/aircraft_types/', views.aircraft_types_list, name='aircraft-types-list'),
    path('execution/references/professions/', views.professions_list, name='professions-list'),
]