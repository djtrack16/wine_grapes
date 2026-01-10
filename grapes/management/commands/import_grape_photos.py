"""
Management command to import grape photos from VIVC.
Scrapes both "cluster in the field" and "cluster in the laboratory" pages.
Prefers laboratory photos over field photos.
"""
import sys
import os
import time
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
from grapes.models import Grape, GrapePhoto
import requests
from bs4 import BeautifulSoup

# Import from native_grapes.py
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from native_grapes import VIVC_BASE_URL


class Command(BaseCommand):
  help = 'Import grape photos from VIVC photo pages'

  def add_arguments(self, parser):
    parser.add_argument(
      '--limit',
      type=int,
      help='Limit the number of pages to process (for testing)',
    )
    parser.add_argument(
      '--type',
      type=str,
      choices=['field', 'laboratory', 'both'],
      default='both',
      help='Which photo type to import (field, laboratory, or both)',
    )
    parser.add_argument(
      '--verbose',
      action='store_true',
      help='Show detailed debug output',
    )
    parser.add_argument(
      '--save-html',
      action='store_true',
      help='Save popup HTML to file for debugging (saves first popup only)',
    )

  def handle(self, *args, **options):
    limit = options.get('limit')
    photo_type = options.get('type', 'both')
    self.verbose = options.get('verbose', False)
    self.save_html = options.get('save_html', False)
    self.html_saved = False  # Track if we've saved HTML already
    
    self.stdout.write(self.style.SUCCESS('Starting photo import...'))
    
    photos_imported = 0
    photos_skipped = 0
    errors = 0
    
    # Process laboratory photos first (higher priority)
    if photo_type in ['laboratory', 'both']:
      self.stdout.write('\n=== Processing Laboratory Photos ===')
      lab_count, lab_skipped, lab_errors = self._process_photo_type('laboratory', 'Cluster+in+the+laboratory', limit)
      photos_imported += lab_count
      photos_skipped += lab_skipped
      errors += lab_errors
    
    # Process field photos (only if not already have laboratory photo)
    if photo_type in ['field', 'both']:
      self.stdout.write('\n=== Processing Field Photos ===')
      field_count, field_skipped, field_errors = self._process_photo_type('field', 'Cluster+in+the+field', limit)
      photos_imported += field_count
      photos_skipped += field_skipped
      errors += field_errors
    
    self.stdout.write(self.style.SUCCESS(f'\nCompleted!'))
    self.stdout.write(f'  Photos imported: {photos_imported}')
    self.stdout.write(f'  Photos skipped (already exist): {photos_skipped}')
    self.stdout.write(f'  Errors: {errors}')

  def _process_photo_type(self, photo_type, search_param, limit=None):
    """Process photos of a specific type."""
    photos_imported = 0
    photos_skipped = 0
    errors = 0
    grapes_not_in_db = 0
    page_num = 1
    pages_processed = 0
    
    while True:
      if limit and pages_processed >= limit:
        break
      
      url = f"{VIVC_BASE_URL}/index.php?r=fotoverweise%2Fresult&FotoverweiseSearch%5Bpartplant%5D={search_param}&page={page_num}"
      
      try:
        self.stdout.write(f'  Processing page {page_num}...')
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        page = BeautifulSoup(response.text, 'html.parser')
        
        # Find the table with photo data
        table = page.find('table')
        if not table:
          self.stdout.write(f'    No table found on page {page_num}')
          break
        
        rows = table.find_all('tr')
        if len(rows) <= 1:  # Only header row
          self.stdout.write(f'    Only {len(rows)} row(s) found (expected header + data rows)')
          break
        
        self.stdout.write(f'    Found table with {len(rows)} total rows')
        
        # Skip header row and filter rows
        # Filter rows typically have many select elements or lots of newlines
        photo_rows = []
        for row in rows[1:]:
          cells = row.find_all('td')
          if len(cells) < 3:
            continue
          # Check if this looks like a filter row (has selects or many newlines)
          cell_text = ' '.join([cell.get_text() for cell in cells[:3]])
          if row.find('select') or (cell_text.count('\n') > 5):
            continue
          photo_rows.append(row)
        
        if not photo_rows:
          self.stdout.write(f'    No valid photo rows found on page {page_num} (after filtering)')
          break
        
        self.stdout.write(f'    Found {len(photo_rows)} valid photo rows on page {page_num}')
        
        for row_idx, row in enumerate(photo_rows, 1):
          try:
            # Store row_idx for debugging in extraction methods
            self._current_row_idx = row_idx
            
            # Extract VIVC ID from the row
            vivc_id = self._extract_vivc_id_from_row(row)
            if not vivc_id:
              if self.verbose or row_idx <= 3:  # Debug first few rows or if verbose
                cells = row.find_all('td')
                cell_texts = [cell.get_text().strip()[:50] for cell in cells[:5]]
                self.stdout.write(f'      Row {row_idx}: Could not extract VIVC ID. Cells: {cell_texts}')
              continue
            
            # Check if grape exists in database
            try:
              grape = Grape.objects.get(vivc_id=vivc_id)
            except Grape.DoesNotExist:
              # Grape not in database, skip
              grapes_not_in_db += 1
              if self.verbose or row_idx <= 3:  # Debug first few rows or if verbose
                self.stdout.write(f'      Row {row_idx}: Grape with VIVC ID {vivc_id} not in database')
              continue
            
            # Check if we already have a laboratory photo (skip field if we do)
            if photo_type == 'field':
              if GrapePhoto.objects.filter(grape=grape, photo_type='laboratory').exists():
                continue
            
            # Extract photo URL, source, and popup URL from row (including onclick handler)
            photo_url, source, popup_url = self._extract_photo_and_source_from_row(row, vivc_id)
            
            if self.verbose or row_idx <= 3:
              self.stdout.write(f'      Row {row_idx}: photo_url={photo_url[:80] if photo_url else None}, source={source[:50] if source else None}, popup_url={popup_url[:80] if popup_url else None}')
            
            if not photo_url:
              if self.verbose or row_idx <= 3:  # Debug first few rows or if verbose
                self.stdout.write(f'      Row {row_idx}: Could not extract photo URL for {grape.name} (VIVC ID: {vivc_id})')
              continue
            
            # Try to get source from popup page (source only exists in popup)
            # Only try if we found a valid popup URL from onclick/data attributes
            if photo_url and not source:
              if popup_url:
                if self.verbose or row_idx <= 3:
                  self.stdout.write(f'      Row {row_idx}: Fetching source from popup URL: {popup_url}')
                _, source = self._get_photo_details(popup_url)
                if self.verbose or row_idx <= 3:
                  if source:
                    self.stdout.write(f'      Row {row_idx}: ✓ Found source from popup: {source[:100]}...')
                  else:
                    self.stdout.write(f'      Row {row_idx}: ✗ No source found in popup')
              else:
                if self.verbose or row_idx <= 3:
                  self.stdout.write(f'      Row {row_idx}: No popup URL found in onclick/data attributes, cannot fetch source')
            
            # Check if photo already exists
            existing_photo = GrapePhoto.objects.filter(grape=grape, url=photo_url).first()
            
            # Also check normalized URLs to catch variations
            normalized_url = self._normalize_url(photo_url)
            if not existing_photo:
              existing_photos = GrapePhoto.objects.filter(grape=grape)
              for existing in existing_photos:
                existing_normalized = self._normalize_url(existing.url)
                if normalized_url == existing_normalized:
                  existing_photo = existing
                  break
            
            # If photo exists but has no source, update it with source
            if existing_photo:
              if existing_photo.source and existing_photo.source.strip():
                # Photo exists with source, skip
                photos_skipped += 1
                self.stdout.write(f'      Skipped {grape.name} (VIVC ID: {vivc_id}) - photo already exists')
                continue
              else:
                # Photo exists but no source - fetch and update
                if not source:
                  # Try to get source from popup (only if we found popup URL)
                  if popup_url:
                    if self.verbose or row_idx <= 3:
                      self.stdout.write(f'      Row {row_idx}: Updating existing photo with source from popup: {popup_url}')
                    _, source = self._get_photo_details(popup_url)
                    if self.verbose or row_idx <= 3:
                      if source:
                        self.stdout.write(f'      Row {row_idx}: ✓ Found source for update: {source[:100]}...')
                      else:
                        self.stdout.write(f'      Row {row_idx}: ✗ No source found for update')
                  else:
                    if self.verbose or row_idx <= 3:
                      self.stdout.write(f'      Row {row_idx}: No popup URL found, cannot update source')
                
                if source:
                  existing_photo.source = source
                  existing_photo.save()
                  photos_imported += 1
                  self.stdout.write(f'      ✓ Updated source for existing photo: {grape.name} (VIVC ID: {vivc_id})')
                else:
                  if self.verbose or row_idx <= 3:
                    self.stdout.write(f'      Row {row_idx}: Could not find source for existing photo: {grape.name}')
                continue
            
            # Create photo record (database constraint will prevent duplicates if check fails)
            try:
              GrapePhoto.objects.create(
                grape=grape,
                url=photo_url,
                source=source or '',
                photo_type=photo_type
              )
              photos_imported += 1
              self.stdout.write(f'      ✓ Imported photo for {grape.name} (VIVC ID: {vivc_id})')
            except IntegrityError:
              # Duplicate caught by database constraint, skip
              photos_skipped += 1
              self.stdout.write(f'      Skipped {grape.name} (VIVC ID: {vivc_id}) - duplicate photo (database constraint)')
              continue
            
            # Small delay to be respectful
            time.sleep(0.5)
            
          except Exception as e:
            self.stdout.write(self.style.WARNING(f'    Error processing row: {str(e)}'))
            errors += 1
            continue
        
        pages_processed += 1
        page_num += 1
        
        # Check if there's a next page
        # Look for pagination links
        next_link = page.find('a', string='»')
        if not next_link:
          # Also check for "Next" or page number links
          pagination = page.find('div', class_='pagination') or page.find('ul', class_='pagination')
          if pagination:
            next_link = pagination.find('a', string=lambda x: x and ('next' in x.lower() or '»' in x))
          if not next_link:
            break
        
        # Small delay between pages
        time.sleep(1)
        
      except Exception as e:
        self.stdout.write(self.style.ERROR(f'  Error processing page {page_num}: {str(e)}'))
        errors += 1
        break
    
    if grapes_not_in_db > 0:
      self.stdout.write(f'  Note: {grapes_not_in_db} grapes found on photo pages but not in database (skipped)')
    
    return photos_imported, photos_skipped, errors

  def _extract_vivc_id_from_row(self, row):
    """Extract VIVC ID from a table row."""
    cells = row.find_all('td')
    if len(cells) < 3:
      return None
    
    # Skip rows that look like filter rows (contain select elements or have many newlines)
    cell_text = ' '.join([cell.get_text() for cell in cells[:3]])
    if '\n' in cell_text and cell_text.count('\n') > 5:
      # This looks like a filter row, skip
      return None
    
    # VIVC ID is typically in the third cell (index 2) based on the table structure
    # Column order: Prime name, Color, Variety number VIVC, Utilization, Country, Species, Photo, Part of plant
    vivc_cell = cells[2]  # Third column is "Variety number VIVC"
    
    # Look for link with VIVC ID
    link = vivc_cell.find('a')
    if link:
      # Check href for ID
      href = link.get('href', '')
      if 'kenn_nr=' in href:
        # Extract from query parameter
        parts = href.split('kenn_nr=')
        if len(parts) > 1:
          vivc_id = parts[1].split('&')[0].split('#')[0]
          if vivc_id.isdigit():
            return vivc_id
      
      # Check link text
      text = link.get_text().strip()
      if text.isdigit():
        return text
    
    # Also check cell text directly (remove whitespace/newlines)
    cell_text = vivc_cell.get_text().strip().replace('\n', '').replace('\r', '')
    if cell_text.isdigit():
      return cell_text
    
    return None

  def _extract_photo_and_source_from_row(self, row, vivc_id=None):
    """Extract photo URL, source text, and popup URL directly from the row (including onclick handler)."""
    # Store row_idx for debugging (will be set by caller if needed)
    self._current_row_idx = getattr(self, '_current_row_idx', None)
    row_idx = self._current_row_idx if hasattr(self, '_current_row_idx') else 0
    
    cells = row.find_all('td')
    if len(cells) < 7:
      return None, None, None
    
    photo_cell = cells[6] if len(cells) > 6 else cells[-2]
    photo_url = None
    source_text = None
    popup_url = None
    
    # Look for image with src attribute first
    img = photo_cell.find('img')
    if img:
      img_src = img.get('src', '')
      if img_src and img_src != '#' and not img_src.startswith('javascript:'):
        if img_src.startswith('http'):
          photo_url = img_src
        elif img_src.startswith('/'):
          photo_url = f"{VIVC_BASE_URL}{img_src}"
        else:
          photo_url = f"{VIVC_BASE_URL}/{img_src}"
      
      # Find parent link to check onclick
      link = img.find_parent('a')
      if link:
        # Check onclick handler for source text
        onclick = link.get('onclick', '')
        if onclick:
          # Extract source text from onclick - look for text after "Please note" or "quote the source"
          import re
          
          # Pattern: Look for text after "quote the source" or "source as indicated below"
          # The source text format: "Please note: This photo can be reproduced. Please quote the source as indicated below: [SOURCE TEXT]"
          source_patterns = [
            # Pattern 1: Text after "source as indicated below:" or "quote the source"
            r'(?:source as indicated below|quote the source)[:\s]*["\']([^"\']+)["\']',
            # Pattern 2: Text after "Please note" that contains source info
            r'Please note[^"\']*["\']([^"\']*(?:Institut|Institute|Research|Centre|Center|Breeding|Schneider|Kühn|JKI|Geilweilerhof)[^"\']*)["\']',
            # Pattern 3: Long quoted strings that look like source (contains keywords)
            r'["\']([^"\']{50,}(?:Institut|Institute|Research|Centre|Center|Breeding|Schneider|Kühn|JKI|Geilweilerhof)[^"\']*)["\']',
            # Pattern 4: Any long quoted string (fallback)
            r'["\']([^"\']{80,})["\']',
          ]
          
          for pattern in source_patterns:
            match = re.search(pattern, onclick, re.IGNORECASE | re.DOTALL)
            if match:
              source_text = match.group(1).strip()
              # Clean up the source text - handle escaped characters
              source_text = source_text.replace('\\n', ' ').replace('\\r', ' ').replace('\\t', ' ')
              source_text = source_text.replace('\\"', '"').replace("\\'", "'")
              # Remove HTML entities if any
              source_text = source_text.replace('&nbsp;', ' ').replace('&amp;', '&')
              # Normalize whitespace
              source_text = ' '.join(source_text.split())
              # Only use if it looks like a real source (has reasonable length and keywords)
              if len(source_text) > 20:
                break
          
          # If still no source, try extracting all quoted strings and pick the longest one that looks like source
          if not source_text or len(source_text) < 20:
            quote_matches = re.findall(r'["\']([^"\']+)["\']', onclick)
            for quote_text in sorted(quote_matches, key=len, reverse=True):
              cleaned = quote_text.replace('\\n', ' ').replace('\\r', ' ').strip()
              cleaned = ' '.join(cleaned.split())
              # Check if it looks like a source (has keywords or is reasonably long)
              if len(cleaned) > 30 and any(keyword in cleaned for keyword in ['Institut', 'Institute', 'Research', 'Centre', 'Center', 'Breeding', 'Schneider', 'Kühn', 'JKI', 'Geilweilerhof', 'GERMANY', 'Germany']):
                source_text = cleaned
                break
        
        # Extract popup URL from data attributes first (modern JavaScript)
        popup_url = link.get('data-url') or link.get('data-href') or link.get('data-popup') or link.get('data-modal')
        
        # Extract popup URL from onclick handler if available
        if not popup_url and onclick:
          import re
          
          # Debug: log onclick content if verbose
          if hasattr(self, 'verbose') and self.verbose and row_idx <= 3:
            self.stdout.write(f'        DEBUG onclick (first 300 chars): {onclick[:300]}...')
          
          # Look for URLs in onclick that might be popup URLs
          popup_patterns = [
            r'window\.open\(["\']([^"\']+)["\']',
            r'href\s*=\s*["\']([^"\']+)["\']',
            r'url["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'["\']([^"\']*foto[^"\']*view[^"\']*)["\']',
            r'["\']([^"\']*index\.php[^"\']*foto[^"\']*)["\']',
            r'["\']([^"\']*fotoverweise[^"\']*)["\']',
            # Look for full URLs in onclick
            r'(https?://[^"\'\s\)]+foto[^"\'\s\)]*)',
            r'(https?://[^"\'\s\)]+fotoverweise[^"\'\s\)]*)',
          ]
          for pattern in popup_patterns:
            match = re.search(pattern, onclick, re.IGNORECASE)
            if match:
              url = match.group(1)
              if url.startswith('http'):
                popup_url = url
              elif not url.startswith('http'):
                if url.startswith('/'):
                  popup_url = f"{VIVC_BASE_URL}{url}"
                else:
                  popup_url = f"{VIVC_BASE_URL}/{url}"
              if hasattr(self, 'verbose') and self.verbose and row_idx <= 3:
                self.stdout.write(f'        DEBUG: Found popup URL from onclick: {popup_url}')
              break
        
        # If we don't have photo_url yet, check href
        if not photo_url:
          href = link.get('href', '')
          if href and href != '#' and not href.startswith('javascript:'):
            if href.startswith('http'):
              photo_url = href
            elif href.startswith('/'):
              photo_url = f"{VIVC_BASE_URL}{href}"
            else:
              photo_url = f"{VIVC_BASE_URL}/{href}"
          # If href is #, the popup_url from onclick might be what we need
          elif href == '#' and popup_url:
            # Don't set photo_url to popup_url, but we'll use popup_url to get source
            pass
    
    # Also check for any link in photo cell
    if not photo_url:
      link = photo_cell.find('a')
      if link:
        href = link.get('href', '')
        if href and href != '#' and not href.startswith('javascript:'):
          if href.startswith('http'):
            photo_url = href
          elif href.startswith('/'):
            photo_url = f"{VIVC_BASE_URL}{href}"
          else:
            photo_url = f"{VIVC_BASE_URL}/{href}"
    
    return photo_url, source_text, popup_url

  def _extract_photo_link_from_row(self, row, vivc_id=None):
    """Extract the photo link from a table row."""
    cells = row.find_all('td')
    if len(cells) < 7:
      return None
    
    # Photo column is typically second to last (index -2 or around index 6)
    # Column order: Prime name, Color, VIVC ID, Utilization, Country, Species, Photo, Part of plant
    photo_cell = cells[6] if len(cells) > 6 else cells[-2]
    
    # Look for image with src attribute first (might be direct image)
    img = photo_cell.find('img')
    if img:
      img_src = img.get('src', '')
      if img_src and img_src != '#' and not img_src.startswith('javascript:'):
        if img_src.startswith('http'):
          return img_src
        elif img_src.startswith('/'):
          return f"{VIVC_BASE_URL}{img_src}"
        else:
          return f"{VIVC_BASE_URL}/{img_src}"
      
      # Find parent link
      link = img.find_parent('a')
      if link:
        href = link.get('href', '')
        # Skip JavaScript links (#) or empty links
        if href and href != '#' and not href.startswith('javascript:'):
          if href.startswith('http'):
            return href
          elif href.startswith('/'):
            return f"{VIVC_BASE_URL}{href}"
          else:
            return f"{VIVC_BASE_URL}/{href}"
        
        # If link is #, check for onclick or data attributes that might contain the real URL
        onclick = link.get('onclick', '')
        if onclick:
          # Try to extract URL from onclick - look for common patterns
          import re
          # Pattern 1: Look for URLs in quotes
          url_match = re.search(r'["\']([^"\']*(?:foto|photo|image|view)[^"\']*)["\']', onclick, re.IGNORECASE)
          if url_match:
            url = url_match.group(1)
            if url.startswith('http'):
              return url
            elif url.startswith('/'):
              return f"{VIVC_BASE_URL}{url}"
            else:
              return f"{VIVC_BASE_URL}/{url}"
          
          # Pattern 2: Look for ID parameter
          id_match = re.search(r'id[=:]\s*["\']?(\d+)["\']?', onclick, re.IGNORECASE)
          if id_match and vivc_id:
            # Construct URL from VIVC ID
            return f"{VIVC_BASE_URL}/index.php?r=fotoverweise%2Fview&id={vivc_id}"
        
        # Check data attributes
        data_href = link.get('data-href') or link.get('data-url') or link.get('data-src')
        if data_href:
          if data_href.startswith('http'):
            return data_href
          elif data_href.startswith('/'):
            return f"{VIVC_BASE_URL}{data_href}"
          else:
            return f"{VIVC_BASE_URL}/{data_href}"
    
    # Also check for any link in photo cell
    link = photo_cell.find('a')
    if link:
      href = link.get('href', '')
      if href and href != '#' and not href.startswith('javascript:'):
        if href.startswith('http'):
          return href
        elif href.startswith('/'):
          return f"{VIVC_BASE_URL}{href}"
        else:
          return f"{VIVC_BASE_URL}/{href}"
    
    return None

  def _get_photo_details(self, photo_link):
    """Get source text from the photo popup page."""
    try:
      response = requests.get(photo_link, timeout=30)
      response.raise_for_status()
      page = BeautifulSoup(response.text, 'html.parser')
      
      # Extract source text from popup page
      source_text = ''
      keywords = ['Institut', 'Institute', 'Research', 'Centre', 'Center', 'Breeding', 'Schneider', 'Kühn', 'JKI', 'Geilweilerhof', 'Siebeldingen', 'GERMANY', 'Germany']
      
      # Method 1: Look for panel structure (most common)
      # The source is typically in a <p> with class "panel-title" inside a div with class "panel-heading"
      # Look for any panel structure, not just "panel-danger"
      panel_headings = page.find_all('div', class_='panel-heading')
      for panel_heading in panel_headings:
        # Check if this panel contains "Please note"
        heading_text = panel_heading.get_text()
        if 'Please note' in heading_text and 'quote the source' in heading_text.lower():
          # Find all <p> elements with class "panel-title" in this heading
          panel_titles = panel_heading.find_all('p', class_='panel-title')
          # The source text is typically in the second <p> (after "Please note" paragraph)
          # But could be in any <p> that contains source keywords
          for p_elem in panel_titles:
            p_text = p_elem.get_text().strip()
            # Skip the "Please note" paragraph itself
            if 'Please note' in p_text and 'quote the source' in p_text.lower():
              continue
            # Check if this paragraph looks like a source
            if any(keyword in p_text for keyword in keywords) and len(p_text) > 30:
              source_text = p_text
              source_text = ' '.join(source_text.split())
              break
          if source_text:
            break
      
      # Method 2: Look for <p> elements that come after "Please note" text (anywhere in page)
      if not source_text:
        please_note_paras = page.find_all('p', string=lambda text: text and 'Please note' in str(text))
        for para in please_note_paras:
          # Find next sibling <p> that contains source keywords
          next_p = para.find_next_sibling('p')
          if next_p:
            next_text = next_p.get_text().strip()
            # Check if it looks like a source (has keywords and reasonable length)
            if any(keyword in next_text for keyword in keywords) and len(next_text) > 30:
              source_text = next_text
              source_text = ' '.join(source_text.split())
              break
          
          # Also check parent's next sibling
          if not source_text:
            parent = para.find_parent(['div', 'td', 'tr'])
            if parent:
              next_sibling = parent.find_next_sibling(['div', 'p', 'td'])
              if next_sibling:
                next_text = next_sibling.get_text().strip()
                if any(keyword in next_text for keyword in keywords) and len(next_text) > 30:
                  source_text = next_text
                  source_text = ' '.join(source_text.split())
                  break
      
      # Method 3: Extract from panel-heading text using regex
      if not source_text:
        panel_headings = page.find_all('div', class_='panel-heading')
        for heading in panel_headings:
          heading_text = heading.get_text()
          if 'Please note' in heading_text and 'quote the source' in heading_text.lower():
            # Extract text after "quote the source as indicated below:"
            import re
            # Pattern: text after "quote the source as indicated below:" up to "Download" or end
            source_match = re.search(r'quote the source as indicated below[:\s]+(.+?)(?:\n\s*Download|$)', heading_text, re.IGNORECASE | re.DOTALL)
            if source_match:
              source_text = source_match.group(1).strip()
              source_text = ' '.join(source_text.split())
              # Verify it looks like a source
              if len(source_text) > 20 and any(keyword in source_text for keyword in keywords):
                break
      
      # Method 4: Look for any element containing source keywords that's near "Please note"
      if not source_text:
        please_note_elements = page.find_all(string=lambda text: text and 'Please note' in str(text))
        for elem in please_note_elements:
          # Look in nearby elements
          parent = elem.find_parent(['div', 'p', 'td', 'tr'])
          if parent:
            # Check all text nodes in parent and siblings
            all_text = parent.get_text()
            # Extract text after "quote the source"
            import re
            source_match = re.search(r'quote the source[^:]*:[:\s]+(.+?)(?:\n\s*Download|$)', all_text, re.IGNORECASE | re.DOTALL)
            if source_match:
              potential_source = source_match.group(1).strip()
              potential_source = ' '.join(potential_source.split())
              if len(potential_source) > 20 and any(keyword in potential_source for keyword in keywords):
                source_text = potential_source
                break
      
      # Method 5: Fallback - look for text blocks with source keywords in full page text
      if not source_text or len(source_text) < 20:
        page_text = page.get_text()
        # Find text blocks that contain source-related keywords
        lines = page_text.split('\n')
        for i, line in enumerate(lines):
          if any(keyword in line for keyword in keywords) and len(line.strip()) > 30:
            # Take this line and next few lines (but stop before "Download")
            source_lines = []
            for j in range(i, min(i+5, len(lines))):
              line_text = lines[j].strip()
              if 'Download' in line_text.lower():
                break
              if line_text:
                source_lines.append(line_text)
            if source_lines:
              source_text = ' '.join(source_lines).strip()
              if len(source_text) > 30:
                break
      
      # Debug output if verbose
      if hasattr(self, 'verbose') and self.verbose and not source_text:
        # Log a snippet of the page to help debug
        page_text_full = page.get_text()
        page_snippet = page_text_full[:1000]
        if 'Please note' in page_text_full:
          self.stdout.write(f'        DEBUG: Found "Please note" in page but couldn\'t extract source.')
          self.stdout.write(f'        DEBUG: Page text snippet (first 500 chars): {page_text_full[:500]}...')
          # Also check HTML structure
          please_note_elements = page.find_all(string=lambda text: text and 'Please note' in str(text))
          if please_note_elements:
            self.stdout.write(f'        DEBUG: Found {len(please_note_elements)} elements containing "Please note"')
            for i, elem in enumerate(please_note_elements[:2]):
              parent = elem.find_parent()
              if parent:
                self.stdout.write(f'        DEBUG: Element {i} parent tag: {parent.name}, text: {parent.get_text()[:200]}...')
      
      return None, source_text  # Return None for photo URL since we already have it
      
    except Exception as e:
      return None, None

  def _normalize_url(self, url):
    """Normalize URL for duplicate checking."""
    if not url:
      return url
    
    # Remove query parameters and fragments
    url = url.split('?')[0].split('#')[0]
    
    # Remove trailing slash
    url = url.rstrip('/')
    
    return url

