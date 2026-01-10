from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from .models import Grape, Country


def index(request):
  """Home page listing all countries with native grape counts."""
  countries = Country.objects.annotate(
    grape_count=Count('grape')
  ).order_by('-grape_count', 'name')
  
  context = {
    'countries': countries,
  }
  return render(request, 'grapes/index.html', context)


def grape_detail(request, vivc_id):
  """Display detailed information about a specific grape."""
  grape = get_object_or_404(Grape.objects.select_related('country_of_origin'), vivc_id=vivc_id)
  
  # Get parents (direct ancestors) with their country of origin
  parents = grape.parents.select_related('country_of_origin').all()
  
  # Get children (direct descendants) with their other parent and countries
  children_data = []
  for child in grape.children.select_related('country_of_origin').all():
    # Find the other parent (the one that's not the current grape)
    other_parents = child.parents.exclude(vivc_id=vivc_id).select_related('country_of_origin')
    other_parent = other_parents.first() if other_parents.exists() else None
    children_data.append({
      'child': child,
      'other_parent': other_parent,
    })
  
  # Get first photo for this grape (if available)
  # Prioritize laboratory photos over field photos
  # The model's Meta ordering already handles this, but we'll be explicit
  first_photo = grape.photos.filter(photo_type='laboratory').first()
  if not first_photo:
    first_photo = grape.photos.filter(photo_type='field').first()
  if not first_photo:
    # Fallback to any photo if types don't match expected values
    first_photo = grape.photos.first()

  context = {
    'grape': grape,
    'parents': parents,
    'children_data': children_data,
    'first_photo': first_photo,
  }
  return render(request, 'grapes/grape_detail.html', context)


def country_detail(request, iso_code):
  """Display detailed information about a specific country."""
  country = get_object_or_404(Country, iso_code=iso_code)
  
  # Get all grapes for this country
  grapes = Grape.objects.filter(country_of_origin=country).order_by('name')
  
  # Count grapes by berry color
  color_counts = {}
  for grape in grapes:
    color = grape.berry_color or 'NOT SPECIFIED'
    color_counts[color] = color_counts.get(color, 0) + 1
  
  context = {
    'country': country,
    'grapes': grapes,
    'total_grapes': grapes.count(),
    'color_counts': color_counts,
  }
  return render(request, 'grapes/country_detail.html', context)
