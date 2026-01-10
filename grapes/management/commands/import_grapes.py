import sys
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from grapes.models import Grape, Country
from grapes.utils import normalize_color, normalize_name
import requests
from bs4 import BeautifulSoup
from collections import defaultdict

# Import from native_grapes.py
# Add project root to path to import native_grapes
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from native_grapes import NativeGrapes, COUNTRIES_NAME_TO_ISO_CODE, VIVC_BASE_URL


class Command(BaseCommand):
  help = 'Import grape data from VIVC database using NativeGrapes class'

  def add_arguments(self, parser):
    parser.add_argument(
      '--country',
      type=str,
      help='Import grapes for a specific country only',
    )
    parser.add_argument(
      '--skip-relationships',
      action='store_true',
      help='Skip importing parent/child relationships (faster)',
    )
    parser.add_argument(
      '--fields',
      type=str,
      help='Comma-separated list of fields to import/update (e.g., "species,breeder,year_of_crossing"). If not specified, all fields are imported. Available fields: name, berry_color, species, year_of_crossing, breeder',
    )

  def handle(self, *args, **options):
    fields_arg = options.get('fields')
    
    # Parse fields to import
    fields_to_import = set()
    if fields_arg:
      fields_to_import = {f.strip().lower() for f in fields_arg.split(',')}
      # Validate field names
      valid_fields = {'name', 'berry_color', 'species', 'year_of_crossing', 'breeder'}
      invalid_fields = fields_to_import - valid_fields
      if invalid_fields:
        self.stdout.write(self.style.ERROR(f'Invalid field names: {", ".join(invalid_fields)}'))
        self.stdout.write(self.style.ERROR(f'Valid fields: {", ".join(valid_fields)}'))
        return
      self.stdout.write(self.style.SUCCESS(f'Starting partial import (fields: {", ".join(fields_to_import)})...'))
    else:
      self.stdout.write(self.style.SUCCESS('Starting full grape import (all fields)...'))
    
    country_filter = options.get('country')
    skip_relationships = options.get('skip_relationships', False) or bool(fields_to_import)  # Skip relationships when doing partial field updates
    
    # Fields that come from listing page (can be scraped efficiently)
    listing_page_fields = {'name', 'berry_color', 'species'}
    # Fields that come from individual grape detail pages (require individual page requests)
    detail_page_fields = {'year_of_crossing', 'breeder'}
    
    # Determine which fields need detail page scraping
    needs_detail_pages = bool(fields_to_import & detail_page_fields) or (not fields_to_import)
    
    # Get countries to process
    if country_filter:
      if country_filter.lower() not in COUNTRIES_NAME_TO_ISO_CODE:
        self.stdout.write(self.style.ERROR(f'Country "{country_filter}" not found'))
        return
      countries_to_process = [(country_filter.lower(), COUNTRIES_NAME_TO_ISO_CODE[country_filter.lower()])]
    else:
      countries_to_process = list(COUNTRIES_NAME_TO_ISO_CODE.items())
    
    total_countries = len(countries_to_process)
    
    for idx, (country_name, iso_code) in enumerate(countries_to_process, 1):
      self.stdout.write(f'\n[{idx}/{total_countries}] Processing {country_name.capitalize()} ({iso_code})...')
      
      # Create or get country (only if importing all fields or if country-related fields are needed)
      if not fields_to_import:
        normalized_country_name = normalize_name(country_name.capitalize())
        country, created = Country.objects.get_or_create(
          iso_code=iso_code,
          defaults={
            'name': normalized_country_name,
            'vivc_search_url': f"{VIVC_BASE_URL}/index.php?r=species%2Fcountry&SpeciesSearch[landescode22]={iso_code}"
          }
        )
        if not created and country.name != normalized_country_name:
          country.name = normalized_country_name
          country.save()
        if created:
          self.stdout.write(f'  Created country: {country.name}')
      else:
        # In partial import mode, we still need the country object for lookups
        try:
          country = Country.objects.get(iso_code=iso_code)
        except Country.DoesNotExist:  # type: ignore
          self.stdout.write(self.style.WARNING(f'  Country {iso_code} not found in database. Skipping this country for partial import.'))
          continue
      
      # Scrape grapes for this country
      grape_list = self._scrape_grapes_for_country(iso_code)
      self.stdout.write(f'  Found {len(grape_list)} grapes')
      
      # Process each grape
      imported_count = 0
      updated_count = 0
      skipped_count = 0
      error_count = 0
      not_found_count = 0
      
      for grape_idx, grape_data in enumerate(grape_list, 1):
        # Unpack grape data: name, url, color, species
        if len(grape_data) >= 4:
          grape_name, grape_url, berry_color, species = grape_data[:4]
        else:
          grape_name, grape_url, berry_color = grape_data[:3]
          species = ''
        
        # Show progress
        progress_interval = 50 if fields_to_import else 10
        if grape_idx % progress_interval == 0 or grape_idx == 1 or grape_idx == len(grape_list):
          self.stdout.write(f'    Processing grape {grape_idx}/{len(grape_list)}: {grape_name}')
        
        try:
          # Find VIVC ID from the URL
          vivc_id = self._extract_vivc_id_from_url(grape_url)
          if not vivc_id:
            skipped_count += 1
            continue
          
          # Get or create grape
          try:
            grape = Grape.objects.get(vivc_id=vivc_id)
            created = False
          except Grape.DoesNotExist:  # type: ignore
            # In partial import mode, don't create new grapes
            if fields_to_import:
              not_found_count += 1
              continue
            # Full import mode: create new grape
            grape = Grape(vivc_id=vivc_id)
            created = True
          
          # Track if any fields were updated
          fields_updated = []
          
          # Update fields based on what's requested
          if not fields_to_import or 'name' in fields_to_import:
            normalized_name = normalize_name(grape_name)
            if created or grape.name != normalized_name:
              grape.name = normalized_name
              if not created:
                fields_updated.append('name')
          
          if not fields_to_import or 'berry_color' in fields_to_import:
            normalized_color = normalize_color(berry_color)
            if created or grape.berry_color != normalized_color:
              grape.berry_color = normalized_color
              if not created:
                fields_updated.append('berry_color')
          
          if not fields_to_import or 'species' in fields_to_import:
            normalized_species = normalize_name(species) if species else ''
            if created or grape.species != normalized_species:
              grape.species = normalized_species
              if not created:
                fields_updated.append('species')
          
          # Fields from listing page
          if created:
            grape.vivc_url = grape_url if grape_url.startswith('http') else f"{VIVC_BASE_URL}/{grape_url}"
            grape.country_of_origin = country
          elif not fields_to_import:
            # Update URL and country in full import mode
            grape.vivc_url = grape_url if grape_url.startswith('http') else f"{VIVC_BASE_URL}/{grape_url}"
            grape.country_of_origin = country
          
          # Extract fields from individual grape detail pages if needed
          if needs_detail_pages:
            detail_fields = self._extract_detail_page_fields(vivc_id)
            
            if not fields_to_import or 'year_of_crossing' in fields_to_import:
              year_of_crossing = normalize_name(detail_fields.get('year_of_crossing', ''))
              if created or grape.year_of_crossing != year_of_crossing:
                grape.year_of_crossing = year_of_crossing
                if not created:
                  fields_updated.append('year_of_crossing')
            
            if not fields_to_import or 'breeder' in fields_to_import:
              breeder = normalize_name(detail_fields.get('breeder', ''))
              if created or grape.breeder != breeder:
                grape.breeder = breeder
                if not created:
                  fields_updated.append('breeder')
          
          # Save if there were any changes or if it's a new grape
          if created or fields_updated:
            grape.save()
            if created:
              imported_count += 1
              if len(grape_list) < 1000 or imported_count % 10 == 0 or imported_count == 1:
                self.stdout.write(f'      ✓ Imported: {grape.name} (VIVC ID: {vivc_id})')
            else:
              updated_count += 1
              if grape_idx % progress_interval == 0 or grape_idx == 1:
                updated_fields_str = ', '.join(fields_updated)
                self.stdout.write(f'      ↻ Updated {updated_fields_str} for: {grape.name} (VIVC ID: {vivc_id})')
          else:
            skipped_count += 1
          
          # Import relationships if not skipping and not in partial field mode
          if not skip_relationships and not fields_to_import:
            self._import_grape_relationships(grape)
            
        except Exception as e:
          error_count += 1
          self.stdout.write(self.style.ERROR(f'    ✗ Error processing {grape_name}: {str(e)}'))
          continue
      
      # Summary
      mode_label = f'({", ".join(fields_to_import)})' if fields_to_import else '(all fields)'
      self.stdout.write(self.style.SUCCESS(f'\n  Completed {country_name.capitalize()} {mode_label}:'))
      if not fields_to_import:
        self.stdout.write(f'    Imported: {imported_count} new grapes')
      if updated_count > 0:
        self.stdout.write(f'    Updated: {updated_count} existing grapes')
      if skipped_count > 0:
        self.stdout.write(f'    Skipped (no change): {skipped_count} grapes')
      if not_found_count > 0:
        self.stdout.write(self.style.WARNING(f'    Not found in database: {not_found_count} grapes (skipped in partial import mode)'))
      if error_count > 0:
        self.stdout.write(self.style.ERROR(f'    Errors: {error_count} grapes'))
    
    self.stdout.write(self.style.SUCCESS('\nImport completed!'))

  def _scrape_grapes_for_country(self, iso_code):
    """Scrape grape list for a country from VIVC."""
    all_grapes = []
    page_num = 1
    per_page = 500
    
    while True:
      url = f"{VIVC_BASE_URL}/index.php?per-page={per_page}&page={page_num}&SpeciesSearch[landescode22]={iso_code}&r=species%2Fcountry"
      try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        page = BeautifulSoup(response.text, 'html.parser')
        
        tbody = page.select('tbody')
        if not tbody:
          break
        
        rows = tbody[0].find_all('tr')
        if not rows:
          break
        
        for row in rows:
          cells = row.find_all('td')
          if len(cells) >= 4:
            link_tag = cells[0].find('a')
            if link_tag:
              name = link_tag.text.strip()
              href = link_tag.get('href', '')
              url = f"{VIVC_BASE_URL}/{href}" if href and not href.startswith('http') else href
              # Extract species from cells[2] (third column, 0-indexed)
              species = cells[2].text.strip() if len(cells) > 2 else ''
              color_tag = cells[3].find('a')
              color = color_tag.text.strip() if color_tag and color_tag.text else 'not specified'
              all_grapes.append([name, url, color, species])
        
        if len(rows) < per_page:
          break
        
        page_num += 1
      except Exception as e:
        self.stdout.write(self.style.WARNING(f'    Error scraping page {page_num}: {str(e)}'))
        break
    
    return all_grapes

  def _extract_detail_page_fields(self, vivc_id):
    """Extract fields from individual grape detail page (breeder, year_of_crossing)."""
    fields = {}
    try:
      url = f"{VIVC_BASE_URL}/index.php?r=passport%2Fview&id={vivc_id}"
      response = requests.get(url, timeout=30)
      response.raise_for_status()
      page = BeautifulSoup(response.text, 'html.parser')
      
      # Find all table rows
      rows = page.select('div.passport-view table tr')
      
      for row in rows:
        cells = row.find_all('th') + row.find_all('td')
        if len(cells) >= 2:
          key = cells[0].get_text().strip().lower()
          value_cell = cells[1]
          value = value_cell.get_text().strip()
          
          # Look for year of crossing
          if 'year of crossing' in key or 'crossing year' in key or 'year crossed' in key:
            fields['year_of_crossing'] = value
          # Look for breeder
          elif 'breeder' in key and 'parent' not in key:
            fields['breeder'] = value
          elif 'breeder name' in key or 'breeder(s)' in key:
            fields['breeder'] = value
      
    except Exception as e:
      # Silently fail if detail page can't be accessed
      pass
    
    return fields

  def _extract_vivc_id_from_url(self, url):
    """Extract VIVC ID from a grape URL."""
    if not url:
      return None
    if 'id=' in url:
      return url.split('id=')[-1].split('&')[0]
    return None

  def _import_grape_relationships(self, grape):
    """Import parent and child relationships for a grape."""
    try:
      # Get parents (ancestors)
      ancestry = NativeGrapes.get_grape_ancestry(grape.vivc_id)
      if ancestry and ancestry.get('parents'):
        for parent_data in ancestry['parents']:
          parent_id = parent_data.get('id')
          if parent_id:
            try:
              parent_grape = Grape.objects.get(vivc_id=parent_id)
              grape.parents.add(parent_grape)
            except Grape.DoesNotExist:  # type: ignore
              # Parent grape not in database yet, skip for now
              pass
      
      # Get children (descendants)
      children = NativeGrapes.find_grape_children(grape.name)
      for child_data in children:
        child_id = child_data.get('id')
        if child_id:
          try:
            child_grape = Grape.objects.get(vivc_id=child_id)
            # Add parent relationship (children is the reverse relation)
            child_grape.parents.add(grape)
          except Grape.DoesNotExist:  # type: ignore
            # Child grape not in database yet, skip for now
            pass
    except Exception as e:
      # Silently skip relationship errors to avoid stopping import
      pass
