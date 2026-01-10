"""
Management command to mark grapes that already have parents with date_last_crawled timestamp.
This indicates that children were already searched for these grapes.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from grapes.models import Grape


class Command(BaseCommand):
  help = 'Mark grapes with parents as already crawled (children already searched)'

  def add_arguments(self, parser):
    parser.add_argument(
      '--dry-run',
      action='store_true',
      help='Show what would be marked without making changes',
    )

  def handle(self, *args, **options):
    dry_run = options.get('dry_run', False)
    
    if dry_run:
      self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
    
    # Find grapes that have parents but no date_last_crawled
    all_grapes = Grape.objects.all()
    grapes_to_mark = []
    
    for grape in all_grapes:
      # Check if grape has parents and no date_last_crawled
      if grape.parents.exists() and not grape.date_last_crawled:
        grapes_to_mark.append(grape)
    
    total = len(grapes_to_mark)
    self.stdout.write(f'\nFound {total} grapes with parents that need to be marked...')
    
    if total == 0:
      self.stdout.write(self.style.SUCCESS('No grapes to mark. All grapes with parents are already marked.'))
      return
    
    marked = 0
    for grape in grapes_to_mark:
      if not dry_run:
        grape.date_last_crawled = timezone.now()
        grape.save()
      self.stdout.write(f'  Marked: {grape.name} (has {grape.parents.count()} parent(s))')
      marked += 1
    
    if dry_run:
      self.stdout.write(self.style.WARNING(f'\nDRY RUN: Would mark {marked} grapes. Run without --dry-run to apply.'))
    else:
      self.stdout.write(self.style.SUCCESS(f'\nMarked {marked} grapes as already crawled.'))

