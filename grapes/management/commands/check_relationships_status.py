"""
Management command to check how many grapes from a country don't have relationships calculated yet.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from grapes.models import Grape, Country


class Command(BaseCommand):
  help = 'Check how many grapes from a country don\'t have relationships calculated yet'

  def add_arguments(self, parser):
    parser.add_argument(
      'country',
      type=str,
      help='Country name or ISO code to check (e.g., "USA" or "US")',
    )

  def handle(self, *args, **options):
    country_input = options['country'].strip().upper()
    
    # Try to find country by ISO code first, then by name
    try:
      country = Country.objects.get(iso_code=country_input)
    except Country.DoesNotExist:  # type: ignore
      # Try finding by name (case-insensitive)
      try:
        country = Country.objects.filter(name__iexact=country_input).first()
        if not country:
          # Try partial match
          country = Country.objects.filter(name__icontains=country_input).first()
      except Exception:
        country = None
    
    if not country:
      self.stdout.write(self.style.ERROR(f'Country "{country_input}" not found in database.'))
      self.stdout.write('Available countries:')
      for c in Country.objects.all().order_by('name')[:20]:
        self.stdout.write(f'  - {c.name} ({c.iso_code})')
      return
    
    self.stdout.write(f'\nChecking grapes for: {country.name} ({country.iso_code})\n')
    
    # Get all grapes from this country
    all_usa_grapes = Grape.objects.filter(country_of_origin=country)
    total_grapes = all_usa_grapes.count()
    
    # Grapes that have relationships calculated:
    # - Have date_last_crawled set, OR
    # - Have parents (which implies children were already searched)
    grapes_with_relationships = all_usa_grapes.filter(
      Q(date_last_crawled__isnull=False) | Q(parents__isnull=False)
    ).distinct().count()
    
    # Grapes without relationships calculated:
    # - Don't have date_last_crawled set
    # - AND don't have any parents
    grapes_without_relationships = all_usa_grapes.filter(
      date_last_crawled__isnull=True,
      parents__isnull=True
    ).count()
    
    # Also get breakdown
    grapes_with_crawled_date = all_usa_grapes.filter(date_last_crawled__isnull=False).count()
    grapes_with_parents = all_usa_grapes.filter(parents__isnull=False).distinct().count()
    
    self.stdout.write(f'Total grapes: {total_grapes}')
    self.stdout.write(f'  - With relationships calculated: {grapes_with_relationships}')
    self.stdout.write(f'    • With date_last_crawled: {grapes_with_crawled_date}')
    self.stdout.write(f'    • With parents (implies children searched): {grapes_with_parents}')
    self.stdout.write(f'  - Without relationships calculated: {grapes_without_relationships}')
    
    if grapes_without_relationships > 0:
      self.stdout.write(self.style.WARNING(f'\n{grapes_without_relationships} grapes still need relationships calculated.'))
    else:
      self.stdout.write(self.style.SUCCESS('\nAll grapes have relationships calculated!'))
