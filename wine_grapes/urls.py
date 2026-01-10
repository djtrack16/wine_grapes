"""
URL configuration for wine_grapes project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
  path('admin/', admin.site.urls),
  path('', include(('grapes.urls', 'grapes'), namespace='grapes')),
]
