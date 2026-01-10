"""
Management command to normalize existing grape data:
- Convert colors: rouge->Red, noir->Black, rose->Pink, blanc->White, not specified->Unknown
- Convert ALL CAPS names to Title Case
"""
from django.core.management.base import BaseCommand
from grapes.models import Grape, Country
from grapes.utils import normalize_color, normalize_name


class Command(BaseCommand):
  help = 'Normalize existing grape data: colors and names'

  def add_arguments(self, parser):
    parser.add_argument(
      '--dry-run',
      action='store_true',
      help='Show what would be changed without making changes',
    )

  def handle(self, *args, **options):
    dry_run = options.get('dry_run', False)
    
    if dry_run:
      self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
    
    # Normalize grape colors
    self.stdout.write('\nNormalizing grape colors...')
    grapes_updated = 0
    for grape in Grape.objects.all():
      old_color = grape.berry_color
      new_color = normalize_color(old_color)
      
      if old_color != new_color:
        if not dry_run:
          grape.berry_color = new_color
          grape.save()
        self.stdout.write(f'  {grape.name}: "{old_color}" -> "{new_color}"')
        grapes_updated += 1
    
    self.stdout.write(self.style.SUCCESS(f'  Updated {grapes_updated} grape colors'))
    
    # Normalize grape names
    self.stdout.write('\nNormalizing grape names...')
    names_updated = 0
    for grape in Grape.objects.all():
      old_name = grape.name
      new_name = normalize_name(old_name)
      
      if old_name != new_name:
        if not dry_run:
          grape.name = new_name
          grape.save()
        self.stdout.write(f'  "{old_name}" -> "{new_name}"')
        names_updated += 1
    
    self.stdout.write(self.style.SUCCESS(f'  Updated {names_updated} grape names'))
    
    # Normalize country names
    self.stdout.write('\nNormalizing country names...')
    countries_updated = 0
    for country in Country.objects.all():
      old_name = country.name
      new_name = normalize_name(old_name)
      
      if old_name != new_name:
        if not dry_run:
          country.name = new_name
          country.save()
        self.stdout.write(f'  "{old_name}" -> "{new_name}"')
        countries_updated += 1
    
    self.stdout.write(self.style.SUCCESS(f'  Updated {countries_updated} country names'))
    
    if dry_run:
      self.stdout.write(self.style.WARNING('\nThis was a dry run. Run without --dry-run to apply changes.'))
    else:
      self.stdout.write(self.style.SUCCESS('\nNormalization completed!'))

