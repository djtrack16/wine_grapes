"""
Management command to add missing countries from COUNTRIES_NAME_TO_ISO_CODE to the database.
"""
import sys
from pathlib import Path
from django.core.management.base import BaseCommand
from grapes.models import Country
from grapes.utils import normalize_name

# Import from native_grapes.py
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Read COUNTRIES_NAME_TO_ISO_CODE directly from native_grapes.py to avoid syntax issues
# Extract just the dict using regex since the file has Python 3.10+ syntax
import re
native_grapes_path = project_root / 'native_grapes.py'
with open(native_grapes_path, 'r') as f:
  content = f.read()
  # Find the dict definition
  match = re.search(r"COUNTRIES_NAME_TO_ISO_CODE\s*=\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}", content, re.DOTALL)
  if match:
    dict_content = match.group(1)
    # Parse the dict manually
    COUNTRIES_NAME_TO_ISO_CODE = {}
    for line in dict_content.split('\n'):
      line = line.strip()
      if line and not line.startswith('#'):
        # Match: 'key': 'VALUE',
        m = re.match(r"['\"]([^'\"]+)['\"]:\s*['\"]([^'\"]+)['\"]", line)
        if m:
          COUNTRIES_NAME_TO_ISO_CODE[m.group(1)] = m.group(2)
  else:
    # Fallback: manually define the dict from what we see
    COUNTRIES_NAME_TO_ISO_CODE = {
      'afghanistan': 'AFG', 'albania': 'ALB', 'algeria': 'DZA', 'andorra': 'AND',
      'argentina': 'ARG', 'armenia': 'ARM', 'austria': 'AUT', 'azerbaijan': 'AZE',
      'belarus': 'BLR', 'belgium': 'BEL', 'bosnia and herzegovina': 'BIH', 'bulgaria': 'BGR',
      'canada': 'CAN', 'china': 'CHN', 'croatia': 'HRV', 'cyprus': 'CYP', 'czechia': 'CZE',
      'daghestan': 'DAG', 'denmark': 'DNK', 'estonia': 'EST', 'finland': 'FIN',
      'france': 'FRA', 'georgia': 'GEO', 'germany': 'DEU', 'greece': 'GRC',
      'hungary': 'HUN', 'iceland': 'ISL', 'india': 'IND', 'iraq': 'IRQ',
      'iran': 'IRN', 'israel': 'ISR', 'japan': 'JPN', 'ireland': 'IRL',
      'italy': 'ITA', 'kazakhstan': 'KAZ', 'kosovo': 'XKX', 'latvia': 'LVA',
      'liechtenstein': 'LIE', 'lithuania': 'LTU', 'luxembourg': 'LUX', 'malta': 'MLT',
      'moldova': 'MDA', 'monaco': 'MCO', 'montenegro': 'MNE', 'mexico': 'MEX',
      'morocco': 'MAR', 'netherlands': 'NLD', 'north macedonia': 'MKD', 'norway': 'NOR',
      'poland': 'POL', 'portugal': 'PRT', 'romania': 'ROU', 'russia': 'RUS',
      'san marino': 'SMR', 'serbia': 'SRB', 'slovakia': 'SVK', 'slovenia': 'SVN',
      'spain': 'ESP', 'ussr': 'SUN', 'sweden': 'SWE', 'switzerland': 'CHE',
      'tajikistan': 'TJK', 'turkey': 'TUR', 'turkmenistan': 'TKM', 'ukraine': 'UKR',
      'united kingdom': 'GBR', 'united states of america': 'USA', 'uzbekistan': 'UZB',
      'vatican city': 'VAT', 'yugoslavia': 'YUG'
    }

VIVC_BASE_URL = 'https://www.vivc.de'


class Command(BaseCommand):
  help = 'Add missing countries from COUNTRIES_NAME_TO_ISO_CODE to the database'

  def handle(self, *args, **options):
    self.stdout.write(self.style.SUCCESS('Checking for missing countries...'))
    
    # Get existing countries
    existing_iso_codes = set(Country.objects.values_list('iso_code', flat=True))
    
    # Find missing countries
    missing_countries = []
    for country_name, iso_code in COUNTRIES_NAME_TO_ISO_CODE.items():
      if iso_code not in existing_iso_codes:
        normalized_name = normalize_name(country_name.capitalize())
        missing_countries.append({
          'name': normalized_name,
          'iso_code': iso_code,
          'vivc_search_url': f"{VIVC_BASE_URL}/index.php?r=species%2Fcountry&SpeciesSearch[landescode22]={iso_code}"
        })
    
    if not missing_countries:
      self.stdout.write(self.style.SUCCESS('No missing countries found. All countries are already in the database.'))
      return
    
    self.stdout.write(self.style.SUCCESS(f'Found {len(missing_countries)} missing countries:'))
    for country in missing_countries:
      self.stdout.write(f'  - {country["name"]} ({country["iso_code"]})')
    
    # Add missing countries
    added_count = 0
    for country_data in missing_countries:
      country, created = Country.objects.get_or_create(
        iso_code=country_data['iso_code'],
        defaults={
          'name': country_data['name'],
          'vivc_search_url': country_data['vivc_search_url']
        }
      )
      if created:
        added_count += 1
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added: {country.name} ({country.iso_code})'))
      else:
        self.stdout.write(f'  - Already exists: {country.name} ({country.iso_code})')
    
    self.stdout.write(self.style.SUCCESS(f'\nCompleted! Added {added_count} new countries.'))

