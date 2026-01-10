"""
Management command to import parent/child relationships for all grapes.
Skips grapes that already have date_last_crawled timestamp or have parents (indicating children were already searched).
"""
import sys
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from grapes.models import Grape

# Import from native_grapes.py
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from native_grapes import NativeGrapes


class Command(BaseCommand):
  help = 'Import parent/child relationships for all grapes, skipping those with complete data'

  def add_arguments(self, parser):
    parser.add_argument(
      '--force',
      action='store_true',
      help='Force update even if relationships already exist',
    )
    parser.add_argument(
      '--limit',
      type=int,
      help='Limit the number of grapes to process (for testing)',
    )

  def handle(self, *args, **options):
    force = options.get('force', False)
    limit = options.get('limit')
    
    # Get all grapes
    all_grapes = Grape.objects.all()
    if limit:
      all_grapes = all_grapes[:limit]
    
    total_grapes = all_grapes.count()
    self.stdout.write(self.style.SUCCESS(f'Processing {total_grapes} grapes...'))
    
    skipped = 0
    processed = 0
    relationships_added = 0
    errors = 0
    
    for idx, grape in enumerate(all_grapes, 1):
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
    self.stdout.write(f'  Total grapes: {total_grapes}')
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
            except Grape.DoesNotExist:
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
          except Grape.DoesNotExist:
            # Child grape not in database, skip
            pass
    except Exception as e:
      # Silently skip if children lookup fails
      pass
    return children_added

