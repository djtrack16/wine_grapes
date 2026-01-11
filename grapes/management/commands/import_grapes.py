import sys
import os
import time
import re
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction, connection
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
      '--start-from',
      type=str,
      help='Start processing from a specific country (by name) and continue alphabetically through remaining countries',
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
    start_from = options.get('start_from')
    skip_relationships = options.get('skip_relationships', False) or bool(fields_to_import)  # Skip relationships when doing partial field updates
    
    # Fields that come from listing page (can be scraped efficiently)
    listing_page_fields = {'name', 'berry_color', 'species'}
    # Fields that come from individual grape detail pages (require individual page requests)
    detail_page_fields = {'year_of_crossing', 'breeder'}
    
    # Determine which fields need detail page scraping
    needs_detail_pages = bool(fields_to_import & detail_page_fields) or (not fields_to_import)
    
    # Get countries to process
    if country_filter and start_from:
      self.stdout.write(self.style.ERROR('Cannot use both --country and --start-from. Use one or the other.'))
      return
    
    if country_filter:
      if country_filter.lower() not in COUNTRIES_NAME_TO_ISO_CODE:
        self.stdout.write(self.style.ERROR(f'Country "{country_filter}" not found'))
        return
      countries_to_process = [(country_filter.lower(), COUNTRIES_NAME_TO_ISO_CODE[country_filter.lower()])]
    elif start_from:
      # Find the starting country and process from there onwards
      start_country_lower = start_from.lower()
      
      if start_country_lower not in COUNTRIES_NAME_TO_ISO_CODE:
        self.stdout.write(self.style.ERROR(f'Country "{start_from}" not found'))
        self.stdout.write('Available countries:')
        for country_name in sorted(COUNTRIES_NAME_TO_ISO_CODE.keys())[:20]:
          self.stdout.write(f'  - {country_name}')
        return
      
      # Get all countries sorted alphabetically by name
      all_countries = sorted(COUNTRIES_NAME_TO_ISO_CODE.items(), key=lambda x: x[0])
      
      # Find the starting index
      start_index = None
      for idx, (country_name, iso_code) in enumerate(all_countries):
        if country_name == start_country_lower:
          start_index = idx
          break
      
      if start_index is None:
        self.stdout.write(self.style.ERROR(f'Could not find starting country "{start_from}"'))
        return
      
      # Get countries from start index onwards
      countries_to_process = all_countries[start_index:]
      self.stdout.write(self.style.SUCCESS(f'Starting from "{start_from}" (will process {len(countries_to_process)} countries):'))
      for i, (name, code) in enumerate(countries_to_process, 1):
        self.stdout.write(f'  {i}. {name.capitalize()} ({code})')
    else:
      # Process all countries, sorted alphabetically
      countries_to_process = sorted(COUNTRIES_NAME_TO_ISO_CODE.items(), key=lambda x: x[0])
    
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
          year_of_crossing = None
          breeder = None
          if needs_detail_pages:
            # Close database connection before making HTTP request to prevent stale locks
            connection.close()
            
            # Fetch detail page (this can take time)
            detail_fields = self._extract_detail_page_fields(vivc_id)
            
            # Re-fetch grape from database after HTTP request to get fresh connection
            if not created:
              try:
                grape = Grape.objects.get(vivc_id=vivc_id)
              except Grape.DoesNotExist:  # type: ignore
                error_count += 1
                self.stdout.write(self.style.ERROR(f'    ✗ Grape {grape_name} (VIVC ID: {vivc_id}) not found after detail fetch'))
                continue
            
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
            saved_successfully = False
            max_retries = 3
            
            for retry_attempt in range(max_retries):
              try:
                # Close any stale database connections before saving on retry
                if retry_attempt > 0:
                  connection.close()
                  time.sleep((retry_attempt) * 0.5)  # Exponential backoff: 0.5s, 1s, 1.5s
                  # Re-fetch grape from database to get fresh connection
                  if not created:
                    grape = Grape.objects.get(vivc_id=vivc_id)
                    # Re-apply the field updates
                    if 'name' in fields_updated:
                      grape.name = normalize_name(grape_name)
                    if 'berry_color' in fields_updated:
                      grape.berry_color = normalize_color(berry_color)
                    if 'species' in fields_updated:
                      grape.species = normalize_name(species) if species else ''
                    if 'year_of_crossing' in fields_updated and year_of_crossing is not None:
                      grape.year_of_crossing = year_of_crossing
                    if 'breeder' in fields_updated and breeder is not None:
                      grape.breeder = breeder
                
                # Use update_fields to only update changed fields (more efficient and reduces lock time)
                update_fields = None
                if created:
                  update_fields = None  # Update all fields for new records
                else:
                  update_fields = fields_updated
                  if grape.vivc_url != (grape_url if grape_url.startswith('http') else f"{VIVC_BASE_URL}/{grape_url}"):
                    update_fields.append('vivc_url')
                    grape.vivc_url = grape_url if grape_url.startswith('http') else f"{VIVC_BASE_URL}/{grape_url}"
                  if grape.country_of_origin != country:
                    update_fields.append('country_of_origin')
                    grape.country_of_origin = country
                
                with transaction.atomic():
                  grape.save(update_fields=update_fields)
                
                saved_successfully = True
                if created:
                  imported_count += 1
                  if len(grape_list) < 1000 or imported_count % 10 == 0 or imported_count == 1:
                    self.stdout.write(f'      ✓ Imported: {grape.name} (VIVC ID: {vivc_id})')
                else:
                  updated_count += 1
                  if grape_idx % progress_interval == 0 or grape_idx == 1:
                    updated_fields_str = ', '.join(fields_updated)
                    self.stdout.write(f'      ↻ Updated {updated_fields_str} for: {grape.name} (VIVC ID: {vivc_id})')
                
                # Close connection periodically to prevent stale locks (every 50 grapes)
                if grape_idx % 50 == 0:
                  connection.close()
                  time.sleep(0.1)
                
                break  # Success, exit retry loop
                
              except Exception as save_error:
                error_msg = str(save_error)
                
                # Check if it's a readonly database error
                if 'readonly' in error_msg.lower() or 'database is locked' in error_msg.lower() or 'locked' in error_msg.lower():
                  if retry_attempt < max_retries - 1:
                    # Will retry on next iteration
                    if retry_attempt == 0:  # Only log once
                      self.stdout.write(self.style.WARNING(f'    ⚠ Database lock/readonly error for {grape_name} (VIVC ID: {vivc_id}), retrying...'))
                  else:
                    # Last retry attempt failed
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f'    ✗ Error saving {grape_name} (VIVC ID: {vivc_id}): {error_msg}'))
                    # Try to close connection and continue
                    try:
                      connection.close()
                    except:
                      pass
                else:
                  # Other errors - don't retry
                  error_count += 1
                  self.stdout.write(self.style.ERROR(f'    ✗ Error saving {grape_name} (VIVC ID: {vivc_id}): {error_msg}'))
                  break
            
            if not saved_successfully:
              # Final attempt failed, skip this grape
              continue
          else:
            skipped_count += 1
          
          # Import relationships if not skipping and not in partial field mode
          if not skip_relationships and not fields_to_import:
            self._import_grape_relationships(grape)
            
        except Exception as e:
          error_msg = str(e)
          error_count += 1
          
          # Don't double-count errors that were already handled in the save retry loop
          if 'readonly' not in error_msg.lower() and 'database is locked' not in error_msg.lower():
            self.stdout.write(self.style.ERROR(f'    ✗ Error processing {grape_name}: {error_msg}'))
          
          # Close connection and continue
          try:
            connection.close()
          except:
            pass
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
          
          # Look for year of crossing
          if 'year of crossing' in key or 'crossing year' in key or 'year crossed' in key:
            value = value_cell.get_text().strip()
            fields['year_of_crossing'] = value
          # Look for breeder - be specific to avoid matching "breeder contact address" or "breeder institute code"
          elif key == 'breeder' or key == 'breeder name' or key == 'breeder(s)':
            # For breeder, we want the actual breeder name (not contact address)
            # The breeder field is usually a link, so get the text from the link
            link = value_cell.find('a')
            if link:
              value = link.get_text().strip()
            else:
              value = value_cell.get_text().strip()
            fields['breeder'] = value
          # Also check for "breeder contact address" - this might have multiple lines separated by <br/>
          elif 'breeder contact address' in key:
            # Replace <br/> and <br> tags with newlines before extracting text
            for br in value_cell.find_all(['br', 'BR']):
              br.replace_with('\n')
            # Get text and preserve newlines
            value = value_cell.get_text(separator='\n')
            # Replace multiple consecutive newlines/whitespace with a single space
            value = re.sub(r'\n\s*\n+', ' ', value)
            # Replace remaining single newlines with space
            value = value.replace('\n', ' ').strip()
            # Clean up multiple spaces
            value = re.sub(r'\s+', ' ', value)
            # Only use breeder contact address if breeder field wasn't already found
            if 'breeder' not in fields:
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
