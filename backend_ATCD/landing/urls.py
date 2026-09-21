# landing/urls.py
from django.urls import path
from . import api_views

app_name = 'landing'

urlpatterns = [
    path('api/landing/content/', api_views.landing_content, name='landing_content'),
]