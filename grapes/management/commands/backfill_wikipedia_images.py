"""
Management command to backfill Wikipedia image URLs for grapes without VIVC photos.
"""
import time
from django.core.management.base import BaseCommand
from django.db import transaction
from grapes.models import Grape
from grapes.utils import get_wikipedia_image


class Command(BaseCommand):
  help = 'Backfill Wikipedia image URLs for grapes without VIVC photos'

  def add_arguments(self, parser):
    parser.add_argument(
      '--limit',
      type=int,
      default=None,
      help='Limit the number of grapes to process (for testing)',
    )
    parser.add_argument(
      '--delay',
      type=float,
      default=0.1,
      help='Delay in seconds between requests (default: 0.1s = ~10 req/s, safe for anonymous Wikipedia API)',
    )
    parser.add_argument(
      '--skip-existing',
      action='store_true',
      help='Skip grapes that already have wikipedia_image_url set',
    )
    parser.add_argument(
      '--update-existing',
      action='store_true',
      help='Update grapes that already have wikipedia_image_url (re-check Wikipedia)',
    )

  def handle(self, *args, **options):
    limit = options.get('limit')
    delay = options.get('delay', 0.1)
    skip_existing = options.get('skip_existing', False)
    update_existing = options.get('update_existing', False)
    
    # Get grapes without VIVC photos
    grapes = Grape.objects.filter(photos__isnull=True)
    
    # Filter by wikipedia_image_url based on flags
    if skip_existing:
      grapes = grapes.filter(wikipedia_image_url='')
    elif not update_existing:
      # Default: only process grapes without wikipedia_image_url
      grapes = grapes.filter(wikipedia_image_url='')
    
    # Filter out grapes with numbers in name (they're unlikely to have Wikipedia pages)
    grapes_list = list(grapes)
    grapes_without_numbers = [g for g in grapes_list if not any(c.isdigit() for c in g.name)]
    
    if limit:
      grapes_without_numbers = grapes_without_numbers[:limit]
    
    total = len(grapes_without_numbers)
    self.stdout.write(f'Processing {total} grapes without VIVC photos...')
    self.stdout.write(f'  Using {delay}s delay between requests')
    
    # Estimate time
    estimated_time = total * (delay + 0.2)  # 0.2s for network overhead
    if estimated_time > 60:
      self.stdout.write(f'  Estimated time: ~{estimated_time/60:.1f} minutes')
    else:
      self.stdout.write(f'  Estimated time: ~{estimated_time:.0f} seconds')
    
    found = 0
    not_found = 0
    errors = 0
    skipped = 0
    start_time = time.time()
    
    # Track consecutive "not found" for batch messages
    consecutive_not_found = 0
    consecutive_start_idx = None
    
    for idx, grape in enumerate(grapes_without_numbers, 1):
      if idx % 100 == 0:
        elapsed = time.time() - start_time
        rate = idx / elapsed if elapsed > 0 else 0
        remaining = total - idx
        eta = remaining / rate if rate > 0 else 0
        self.stdout.write(f'  Processed {idx}/{total}... ({found} found, {not_found} not found, {errors} errors) | Rate: {rate:.1f} req/s | ETA: {eta/60:.1f} min')
      
      try:
        # Check if already has Wikipedia image and we're not updating
        if grape.wikipedia_image_url and not update_existing:
          skipped += 1
          # Reset consecutive counter when skipping (has image already)
          consecutive_not_found = 0
          consecutive_start_idx = None
          continue
        
        # Get Wikipedia image
        wiki_image = get_wikipedia_image(grape.name, use_api=True, delay=delay)
        
        if wiki_image:
          # Save to database
          with transaction.atomic():
            grape.wikipedia_image_url = wiki_image['url']
            grape.save(update_fields=['wikipedia_image_url'])
          found += 1
          
          # Reset consecutive "not found" counter when we find an image
          if consecutive_not_found >= 20:
            # Print message for the batch we just completed
            end_idx = idx - 1
            self.stdout.write(f'  Processing grapes {consecutive_start_idx}-{end_idx}, no images found')
          consecutive_not_found = 0
          consecutive_start_idx = None
          
          if found <= 10:  # Show first 10 examples
            self.stdout.write(f'  ✓ {grape.name}: {wiki_image["url"][:80]}...')
        else:
          not_found += 1
          
          # Track consecutive "not found"
          if consecutive_start_idx is None:
            consecutive_start_idx = idx
          consecutive_not_found += 1
          
          # Print message every 20 consecutive "not found"
          if consecutive_not_found == 20:
            self.stdout.write(f'  Processing grapes {consecutive_start_idx}-{idx}, no images found')
            consecutive_not_found = 0
            consecutive_start_idx = None
          
      except Exception as e:
        errors += 1
        # Reset consecutive counter on error
        consecutive_not_found = 0
        consecutive_start_idx = None
        self.stdout.write(self.style.WARNING(f'  Error processing {grape.name}: {str(e)}'))
    
    # Print final batch if we ended with consecutive "not found"
    if consecutive_not_found >= 20:
      self.stdout.write(f'  Processing grapes {consecutive_start_idx}-{total}, no images found')
    
    elapsed_time = time.time() - start_time
    actual_rate = total / elapsed_time if elapsed_time > 0 else 0
    
    self.stdout.write(self.style.SUCCESS(f'\nResults:'))
    self.stdout.write(f'  Total processed: {total}')
    self.stdout.write(f'  Wikipedia images found: {found} ({found/total*100:.1f}%)')
    self.stdout.write(f'  No Wikipedia image: {not_found} ({not_found/total*100:.1f}%)')
    self.stdout.write(f'  Errors: {errors}')
    if skipped > 0:
      self.stdout.write(f'  Skipped (already had image): {skipped}')
    self.stdout.write(f'  Time elapsed: {elapsed_time/60:.1f} minutes')
    self.stdout.write(f'  Average rate: {actual_rate:.2f} requests/second')
