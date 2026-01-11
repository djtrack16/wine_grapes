from django.db import models
from django.urls import reverse


class Country(models.Model):
  name = models.CharField(max_length=100)
  iso_code = models.CharField(max_length=3, unique=True)
  vivc_search_url = models.URLField(blank=True)

  class Meta:
    verbose_name_plural = "Countries"
    ordering = ['name']
    db_table = 'country'

  def __str__(self):
    return self.name

  def native_grape_count(self):
    """Return the count of native grapes for this country."""
    return Grape.objects.filter(country_of_origin=self).count()  # type: ignore

  def get_absolute_url(self):
    return reverse('grapes:country_detail', kwargs={'iso_code': self.iso_code})


class Grape(models.Model):
  name = models.CharField(max_length=200)
  vivc_id = models.CharField(max_length=50, unique=True)
  vivc_url = models.URLField()
  berry_color = models.CharField(max_length=50)
  species = models.CharField(max_length=100, blank=True, help_text='Grape species (e.g., Vitis Vinifera)')
  year_of_crossing = models.CharField(max_length=50, blank=True, help_text='Year when the grape was crossed/bred')
  breeder = models.CharField(max_length=200, blank=True, help_text='Name of the breeder who created the grape')
  country_of_origin = models.ForeignKey(
    Country,
    on_delete=models.SET_NULL,
    null=True,
    blank=True
  )
  parents = models.ManyToManyField(
    'self',
    symmetrical=False,
    related_name='children',
    blank=True
  )
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)
  date_last_crawled = models.DateTimeField(null=True, blank=True, help_text='Date when relationships were last searched')

  class Meta:
    ordering = ['name']
    db_table = 'grape'

  def __str__(self):
    return self.name

  def get_absolute_url(self):
    return reverse('grapes:grape_detail', kwargs={'vivc_id': self.vivc_id})


class GrapePhoto(models.Model):
  grape = models.ForeignKey(
    Grape,
    on_delete=models.CASCADE,
    related_name='photos'
  )
  url = models.URLField(help_text='URL to the JPEG photo')
  source = models.TextField(help_text='Photo source/attribution')
  photo_type = models.CharField(
    max_length=20,
    choices=[('field', 'Cluster in the field'), ('laboratory', 'Cluster in the laboratory')],
    help_text='Type of photo'
  )
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ['photo_type', 'created_at']  # Prefer field over laboratory (field < laboratory alphabetically)
    db_table = 'grape_photo'
    # Prevent duplicate photos: same grape + same URL should be unique
    unique_together = [['grape', 'url']]

  def __str__(self):
    return f'{self.grape.name} - {self.photo_type}'
