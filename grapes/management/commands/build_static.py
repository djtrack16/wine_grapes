"""
Management command to build a static version of the site for GitHub Pages.
Generates all HTML files from Django templates.
"""
import json
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import reverse
from grapes.models import Grape, Country


class Command(BaseCommand):
  help = 'Build static HTML files for GitHub Pages deployment'

  def add_arguments(self, parser):
    parser.add_argument(
      '--output-dir',
      type=str,
      default='_site',
      help='Output directory for static files (default: _site)',
    )

  def handle(self, *args, **options):
    output_dir = Path(options['output_dir'])
    output_dir.mkdir(exist_ok=True)
    
    self.stdout.write(self.style.SUCCESS(f'Building static site to {output_dir}...'))
    
    # Create .nojekyll file for GitHub Pages
    (output_dir / '.nojekyll').touch()
    
    # Build index page
    self.stdout.write('Building index page...')
    self._build_index(output_dir)
    
    # Build all country pages
    self.stdout.write('Building country pages...')
    self._build_country_pages(output_dir)
    
    # Build all grape pages
    self.stdout.write('Building grape pages...')
    self._build_grape_pages(output_dir)
    
    # Build search results page
    self.stdout.write('Building search results page...')
    self._build_search_results(output_dir)
    
    # Generate grapes JSON file for autocomplete
    self.stdout.write('Generating grapes JSON file...')
    self._generate_grapes_json(output_dir)
    
    self.stdout.write(self.style.SUCCESS(f'\nStatic site built successfully to {output_dir}/'))
    self.stdout.write(f'Total pages: {self._count_pages(output_dir)}')

  def _build_index(self, output_dir):
    """Build the home/index page."""
    countries = Country.objects.all()
    
    # Add grape counts and static URLs to country objects
    for country in countries:
      country.grape_count = country.native_grape_count()
      country.url = f'country/{country.iso_code.lower()}/index.html'
    
    # Sort by grape count descending
    countries_list = sorted(countries, key=lambda c: c.grape_count, reverse=True)
    
    # Render template with index_url for base template (root level)
    html = render_to_string('grapes/index.html', {
      'countries': countries_list,
      'index_url': 'index.html',
    }, request=None)
    
    # Write to index.html
    (output_dir / 'index.html').write_text(html, encoding='utf-8')

  def _build_country_pages(self, output_dir):
    """Build all country detail pages."""
    countries_dir = output_dir / 'country'
    countries_dir.mkdir(exist_ok=True)
    
    countries = Country.objects.all()
    for country in countries:
      # Get all grapes for this country
      grapes = Grape.objects.filter(country_of_origin=country).order_by('name')
      
      # Count grapes by berry color
      color_counts = {}
      for grape in grapes:
        color = grape.berry_color or 'NOT SPECIFIED'
        color_counts[color] = color_counts.get(color, 0) + 1
        # Add static URL to grape object
        grape.url = f'../../grape/{grape.vivc_id}/index.html'
      
      # Add static URL to country object  
      country.url = '../index.html'
      
      # Render template (country pages are 2 levels deep: country/{iso_code}/)
      html = render_to_string('grapes/country_detail.html', {
        'country': country,
        'grapes': grapes,
        'total_grapes': grapes.count(),
        'color_counts': color_counts,
        'index_url': '../../index.html',
      }, request=None)
      
      # Create country directory and write index.html
      country_dir = countries_dir / country.iso_code.lower()
      country_dir.mkdir(exist_ok=True)
      (country_dir / 'index.html').write_text(html, encoding='utf-8')
      
      self.stdout.write(f'  Built country: {country.name} ({country.iso_code})')

  def _build_grape_pages(self, output_dir):
    """Build all grape detail pages."""
    grape_dir = output_dir / 'grape'
    grape_dir.mkdir(exist_ok=True)
    
    grapes = Grape.objects.select_related('country_of_origin').prefetch_related('parents__country_of_origin', 'children__country_of_origin').all()
    total = grapes.count()
    
    for idx, grape in enumerate(grapes, 1):
      if idx % 100 == 0:
        self.stdout.write(f'  Processed {idx}/{total} grapes...')
      
      # Add static URL to country_of_origin if it exists
      if grape.country_of_origin:
        grape.country_of_origin.url = f'../../country/{grape.country_of_origin.iso_code.lower()}/index.html'
      
      # Get parents and add static URLs
      parents = grape.parents.select_related('country_of_origin').all()
      for parent in parents:
        parent.url = f'../../grape/{parent.vivc_id}/index.html'
        if parent.country_of_origin:
          if not grape.country_of_origin or parent.country_of_origin.iso_code != grape.country_of_origin.iso_code:
            parent.country_of_origin.url = f'../../country/{parent.country_of_origin.iso_code.lower()}/index.html'
      
      # Get children with their other parent and add static URLs
      children_data = []
      for child in grape.children.select_related('country_of_origin').all():
        # Find the other parent
        other_parents = child.parents.exclude(vivc_id=grape.vivc_id).select_related('country_of_origin')
        other_parent = other_parents.first() if other_parents.exists() else None
        
        # Add URLs to child
        child.url = f'../../grape/{child.vivc_id}/index.html'
        if child.country_of_origin:
          if not grape.country_of_origin or child.country_of_origin.iso_code != grape.country_of_origin.iso_code:
            child.country_of_origin.url = f'../../country/{child.country_of_origin.iso_code.lower()}/index.html'
        
        # Add URLs to other parent if it exists
        if other_parent:
          other_parent.url = f'../../grape/{other_parent.vivc_id}/index.html'
          if other_parent.country_of_origin:
            if not grape.country_of_origin or other_parent.country_of_origin.iso_code != grape.country_of_origin.iso_code:
              other_parent.country_of_origin.url = f'../../country/{other_parent.country_of_origin.iso_code.lower()}/index.html'
        
        children_data.append({
          'child': child,
          'other_parent': other_parent,
        })
      
      # Get first photo (prioritize field photos over laboratory photos)
      first_photo = grape.photos.filter(photo_type='field').first()
      if not first_photo:
        first_photo = grape.photos.filter(photo_type='laboratory').first()
      if not first_photo:
        first_photo = grape.photos.first()
      
      # Render template (grape pages are 2 levels deep: grape/{vivc_id}/)
      html = render_to_string('grapes/grape_detail.html', {
        'grape': grape,
        'parents': parents,
        'children_data': children_data,
        'first_photo': first_photo,
        'index_url': '../../index.html',
      }, request=None)
      
      # Create grape directory and write index.html
      grape_page_dir = grape_dir / grape.vivc_id
      grape_page_dir.mkdir(exist_ok=True)
      (grape_page_dir / 'index.html').write_text(html, encoding='utf-8')
    
    self.stdout.write(f'  Built {total} grape pages')


  def _build_search_results(self, output_dir):
    """Build the search results page."""
    search_dir = output_dir / 'search'
    search_dir.mkdir(exist_ok=True)
    
    # Render search results template (search pages are 1 level deep: search/)
    html = render_to_string('grapes/search_results.html', {
      'query': '',
      'grapes': [],
      'results_count': 0,
      'index_url': '../index.html',
    }, request=None)
    
    (search_dir / 'index.html').write_text(html, encoding='utf-8')
    self.stdout.write('  Built search results page')

  def _generate_grapes_json(self, output_dir):
    """Generate JSON file with all grape names and VIVC IDs for autocomplete."""
    grapes = Grape.objects.all().order_by('name').values('name', 'vivc_id')
    
    grapes_list = [
      {
        'name': grape['name'],
        'vivc_id': grape['vivc_id'],
      }
      for grape in grapes
    ]
    
    json_path = output_dir / 'grapes.json'
    json_path.write_text(json.dumps(grapes_list, indent=2), encoding='utf-8')
    
    self.stdout.write(f'  Generated grapes.json with {len(grapes_list)} grapes')

  def _count_pages(self, output_dir):
    """Count total HTML pages built."""
    count = 0
    for path in output_dir.rglob('index.html'):
      count += 1
    return count
