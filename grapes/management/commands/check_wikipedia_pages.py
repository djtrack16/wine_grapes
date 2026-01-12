"""
Management command to check how many grapes have Wikipedia pages.
"""
import time
from django.core.management.base import BaseCommand
from grapes.models import Grape
from grapes.utils import check_wikipedia_page_exists


class Command(BaseCommand):
  help = 'Check how many grapes have Wikipedia pages'

  def add_arguments(self, parser):
    parser.add_argument(
      '--limit',
      type=int,
      default=None,
      help='Limit the number of grapes to check (for testing)',
    )
    parser.add_argument(
      '--sample',
      type=int,
      default=None,
      help='Check a random sample of N grapes',
    )
    parser.add_argument(
      '--delay',
      type=float,
      default=0.1,
      help='Delay in seconds between requests (default: 0.1s = ~10 req/s, safe for anonymous Wikipedia API)',
    )
    parser.add_argument(
      '--no-api',
      action='store_true',
      help='Use HTML scraping instead of Wikipedia REST API (slower, less efficient)',
    )

  def handle(self, *args, **options):
    limit = options.get('limit')
    sample = options.get('sample')
    delay = options.get('delay', 0.1)
    use_api = not options.get('no_api', False)
    
    grapes = Grape.objects.all().order_by('name')
    
    if sample:
      import random
      total_count = grapes.count()
      if sample > total_count:
        sample = total_count
      grapes = random.sample(list(grapes), sample)
      self.stdout.write(f'Checking random sample of {sample} grapes...')
    elif limit:
      grapes = grapes[:limit]
      self.stdout.write(f'Checking first {limit} grapes...')
    else:
      self.stdout.write('Checking all grapes (this may take a while)...')
    
    # Filter out grapes with numbers (they're skipped automatically)
    grapes_list = list(grapes)
    grapes_without_numbers = [g for g in grapes_list if not any(c.isdigit() for c in g.name)]
    skipped_count = len(grapes_list) - len(grapes_without_numbers)
    
    if skipped_count > 0:
      self.stdout.write(f'  Skipping {skipped_count} grapes with numbers in name')
    
    total = 0
    found = 0
    not_found = 0
    start_time = time.time()
    
    method = 'REST API' if use_api else 'HTML scraping'
    self.stdout.write(f'  Using {method} with {delay}s delay between requests')
    
    # Estimate time
    estimated_time = len(grapes_without_numbers) * (delay + 0.2)  # 0.2s for network overhead
    if estimated_time > 60:
      self.stdout.write(f'  Estimated time: ~{estimated_time/60:.1f} minutes')
    else:
      self.stdout.write(f'  Estimated time: ~{estimated_time:.0f} seconds')
    
    for grape in grapes_without_numbers:
      total += 1
      if total % 100 == 0:
        elapsed = time.time() - start_time
        rate = total / elapsed if elapsed > 0 else 0
        remaining = len(grapes_without_numbers) - total
        eta = remaining / rate if rate > 0 else 0
        self.stdout.write(f'  Processed {total}/{len(grapes_without_numbers)} grapes... ({found} found, {not_found} not found) | Rate: {rate:.1f} req/s | ETA: {eta/60:.1f} min')
      
      wikipedia_url = check_wikipedia_page_exists(grape.name, use_api=use_api, delay=delay)
      if wikipedia_url:
        found += 1
        if total <= 10:  # Show first 10 examples
          self.stdout.write(f'  ✓ {grape.name}: {wikipedia_url}')
      else:
        not_found += 1
    
    elapsed_time = time.time() - start_time
    actual_rate = total / elapsed_time if elapsed_time > 0 else 0
    
    self.stdout.write(self.style.SUCCESS(f'\nResults:'))
    self.stdout.write(f'  Total checked: {total}')
    self.stdout.write(f'  Wikipedia pages found: {found} ({found/total*100:.1f}%)')
    self.stdout.write(f'  No Wikipedia page: {not_found} ({not_found/total*100:.1f}%)')
    self.stdout.write(f'  Time elapsed: {elapsed_time/60:.1f} minutes')
    self.stdout.write(f'  Average rate: {actual_rate:.2f} requests/second')