"""
Management command to import parent/child relationships for grapes in a specific country.
This only imports relationships, not the grape data itself.
Skips grapes that already have date_last_crawled timestamp or have parents (indicating children were already searched).
Only processes grapes from the specified country and will not touch grapes from other countries.
"""
import sys
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.utils import timezone
from grapes.models import Grape, Country

# Import from native_grapes.py
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from native_grapes import NativeGrapes, COUNTRIES_NAME_TO_ISO_CODE


class Command(BaseCommand):
  help = 'Import parent/child relationships for grapes in a specific country, skipping those with complete data'

  def add_arguments(self, parser):
    parser.add_argument(
      '--country',
      type=str,
      required=True,
      help='Country name to import relationships for',
    )
    parser.add_argument(
      '--force',
      action='store_true',
      help='Force update even if relationships already exist',
    )

  def handle(self, *args, **options):
    country_name = options.get('country')
    force = options.get('force', False)
    
    if country_name.lower() not in COUNTRIES_NAME_TO_ISO_CODE:
      self.stdout.write(self.style.ERROR(f'Country "{country_name}" not found'))
      return
    
    iso_code = COUNTRIES_NAME_TO_ISO_CODE[country_name.lower()]
    
    try:
      country = Country.objects.get(iso_code=iso_code)
    except Country.DoesNotExist:  # type: ignore
      self.stdout.write(self.style.ERROR(f'Country "{country_name}" not found in database. Import grapes first.'))
      return
    
    # Only get grapes from this specific country
    grapes = Grape.objects.filter(country_of_origin=country)
    total_grapes = grapes.count()
    
    self.stdout.write(self.style.SUCCESS(f'\nProcessing relationships for {total_grapes} grapes in {country.name} ({iso_code})...'))
    self.stdout.write('Note: Only grapes from this country will be processed. Grapes from other countries will be skipped.\n')
    
    skipped = 0
    processed = 0
    relationships_added = 0
    errors = 0
    
    for idx, grape in enumerate(grapes, 1):
      if idx % 50 == 0:
        self.stdout.write(f'  Progress: {idx}/{total_grapes} (Processed: {processed}, Skipped: {skipped}, Errors: {errors})')
      
      # Skip if already crawled (unless forcing)
      if not force and grape.date_last_crawled:
        self.stdout.write(f'  {grape.name} was skipped (already crawled)')
        skipped += 1
        continue
      
      # Skip if grape has parents (indicating children were already searched)
      has_parents = grape.parents.exists()
      if not force and has_parents:
        self.stdout.write(f'  {grape.name} was skipped (has parents, children already searched)')
        skipped += 1
        # Mark as crawled if not already marked
        if not grape.date_last_crawled:
          grape.date_last_crawled = timezone.now()
          grape.save()
        continue
      
      processed += 1
      
      try:
        # Import parents
        parents_added = self._import_parents(grape)
        relationships_added += parents_added
        
        # Import children
        children_added = self._import_children(grape)
        relationships_added += children_added
        
        # Mark as crawled
        grape.date_last_crawled = timezone.now()
        grape.save()
          
      except Exception as e:
        self.stdout.write(self.style.WARNING(f'    Error processing {grape.name} (ID: {grape.vivc_id}): {str(e)}'))
        errors += 1
        continue
    
    self.stdout.write(self.style.SUCCESS(f'\nCompleted!'))
    self.stdout.write(f'  Total grapes in {country.name}: {total_grapes}')
    self.stdout.write(f'  Processed: {processed}')
    self.stdout.write(f'  Skipped (already complete): {skipped}')
    self.stdout.write(f'  Relationships added: {relationships_added}')
    self.stdout.write(f'  Errors: {errors}')

  def _import_parents(self, grape):
    """Import parent relationships for a grape."""
    parents_added = 0
    try:
      ancestry = NativeGrapes.get_grape_ancestry(grape.vivc_id)
      if ancestry and ancestry.get('parents'):
        for parent_data in ancestry['parents']:
          parent_id = parent_data.get('id')
          if parent_id:
            try:
              parent_grape = Grape.objects.get(vivc_id=parent_id)
              if parent_grape not in grape.parents.all():
                grape.parents.add(parent_grape)
                parents_added += 1
            except Grape.DoesNotExist:  # type: ignore
              # Parent grape not in database, skip
              pass
    except Exception as e:
      # Silently skip if ancestry lookup fails
      pass
    return parents_added

  def _import_children(self, grape):
    """Import child relationships for a grape."""
    children_added = 0
    try:
      children = NativeGrapes.find_grape_children(grape.name)
      for child_data in children:
        child_id = child_data.get('id')
        if child_id:
          try:
            child_grape = Grape.objects.get(vivc_id=child_id)
            # Add parent relationship (children is the reverse relation)
            if grape not in child_grape.parents.all():
              child_grape.parents.add(grape)
              children_added += 1
          except Grape.DoesNotExist:  # type: ignore
            # Child grape not in database, skip
            pass
    except Exception as e:
      # Silently skip if children lookup fails
      pass
    return children_added

