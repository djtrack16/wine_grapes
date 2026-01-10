from django.urls import path
from . import views

app_name = 'grapes'

urlpatterns = [
  path('', views.index, name='index'),
  path('grape/<str:vivc_id>/', views.grape_detail, name='grape_detail'),
  path('country/<str:iso_code>/', views.country_detail, name='country_detail'),
]
