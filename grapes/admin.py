from django.contrib import admin
from .models import Grape, Country, GrapePhoto


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
  list_display = ('name', 'iso_code', 'native_grape_count')
  search_fields = ('name', 'iso_code')


@admin.register(Grape)
class GrapeAdmin(admin.ModelAdmin):
  list_display = ('name', 'vivc_id', 'berry_color', 'country_of_origin')
  list_filter = ('berry_color', 'country_of_origin')
  search_fields = ('name', 'vivc_id')
  filter_horizontal = ('parents',)


@admin.register(GrapePhoto)
class GrapePhotoAdmin(admin.ModelAdmin):
  list_display = ('grape', 'photo_type', 'url', 'created_at')
  list_filter = ('photo_type', 'created_at')
  search_fields = ('grape__name', 'grape__vivc_id')
  readonly_fields = ('created_at',)
