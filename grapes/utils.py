"""
Utility functions for normalizing grape data.
"""
import requests
import time
from urllib.parse import quote


def normalize_color(color):
  """
  Normalize berry color strings.
  Maps: rouge -> Red, noir -> Black, rose -> Pink, blanc -> White, not specified -> Unknown
  """
  if not color:
    return 'Unknown'
  
  color_lower = color.lower().strip()
  
  color_map = {
    'rouge': 'Red',
    'noir': 'Black',
    'rose': 'Pink',
    'blanc': 'White',
    'not specified': 'Unknown',
    'not_specified': 'Unknown',
    'notspecified': 'Unknown',
  }
  
  # Check exact matches first
  if color_lower in color_map:
    return color_map[color_lower]
  
  # Check if it contains any of the mapped values
  for key, value in color_map.items():
    if key in color_lower:
      return value
  
  # If it's all caps, convert to title case
  if color.isupper():
    return color.title()
  
  # Otherwise return title case
  return color.title()


def normalize_name(name):
  """
  Normalize grape names - convert from ALL CAPS to Title Case.
  """
  if not name:
    return name
  
  # If it's all caps or mostly caps, convert to title case
  if name.isupper() or (len(name) > 3 and name.isupper()):
    return name.title()
  
  # If it has mixed case but seems to be mostly uppercase, convert to title
  uppercase_count = sum(1 for c in name if c.isupper())
  if len(name) > 0 and uppercase_count / len(name) > 0.7:
    return name.title()
  
  # Otherwise return as-is (already properly formatted)
  return name


def get_wikipedia_url(grape_name):
  """
  Generate Wikipedia URL for a grape name.
  Converts multi-word names to use underscores.
  """
  if not grape_name:
    return None
  
  # Replace spaces with underscores
  wiki_name = grape_name.replace(' ', '_')
  # URL encode the name
  wiki_name = quote(wiki_name, safe='_')
  return f"https://en.wikipedia.org/wiki/{wiki_name}"


def get_wikipedia_categories(grape_name):
  """
  Get Wikipedia categories for a page using MediaWiki API.
  Returns list of category titles, or None if page doesn't exist.
  """
  if not grape_name:
    return None
  
  wiki_name = grape_name.replace(' ', '_')
  api_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=categories&titles={quote(wiki_name, safe='_')}&cllimit=50&format=json&redirects=1"
  
  try:
    headers = {
      'User-Agent': 'WineGrapesBot/1.0 (https://github.com/djtrack16/wine_grapes; contact: see GitHub)'
    }
    response = requests.get(api_url, headers=headers, timeout=5)
    
    if response.status_code == 200:
      data = response.json()
      pages = data.get('query', {}).get('pages', {})
      if pages:
        page_data = list(pages.values())[0]
        # Check if page is missing (doesn't exist)
        if 'missing' in page_data:
          return None
        categories = [c.get('title', '') for c in page_data.get('categories', [])]
        return categories
    return None
  except (requests.RequestException, requests.Timeout):
    return None


def is_wikipedia_page_about_grape(data, grape_name=None):
  """
  Validate that a Wikipedia page is actually about a grape/wine variety.
  Uses Wikipedia categories for the most reliable check, falls back to text analysis.
  Returns True if the page appears to be about a grape, False otherwise.
  """
  if not data:
    return False
  
  # Skip disambiguation pages
  if data.get('type') == 'disambiguation':
    return False
  
  # Primary method: Check categories (most reliable)
  if grape_name:
    categories = get_wikipedia_categories(grape_name)
    if categories is not None:
      # Check for grape/wine-related categories
      grape_category_keywords = [
        'grape', 'wine', 'vitis', 'variety', 'cultivar', 'vinifera',
        'wine grape', 'grape variety', 'red wine grape', 'white wine grape'
      ]
      grape_categories = [c for c in categories if any(kw in c.lower() for kw in grape_category_keywords)]
      
      if grape_categories:
        # Found grape/wine categories - definitely a grape page
        return True
      elif len(categories) > 0:
        # Has categories but none are grape-related - likely not a grape page
        # But check text as fallback for edge cases
        pass
  
  # Fallback method: Check extract and description text
  extract = data.get('extract', '').lower()
  description = data.get('description', '').lower()
  combined_text = f'{extract} {description}'
  
  # Positive keywords that indicate it's about grapes/wine
  positive_keywords = [
    'grape', 'wine', 'vitis', 'vinifera', 'variety', 'cultivar',
    'viticulture', 'vineyard', 'winemaking', 'vintage', 'harvest',
    'berry', 'cluster', 'vine', 'wine grape', 'grape variety',
    'red wine', 'white wine', 'rosé', 'sparkling wine'
  ]
  
  # Negative keywords that indicate it's NOT about grapes (false positives)
  negative_keywords = [
    'banana', 'musa', 'hemp', 'fiber', 'textile', 'plant species',
    'tree', 'fruit tree', 'ornamental', 'herb', 'spice', 'vegetable'
  ]
  
  # Check for negative keywords first (stronger signal)
  for keyword in negative_keywords:
    if keyword in combined_text:
      # But allow if it's clearly about grapes (e.g., "grape tree" in context of viticulture)
      if 'grape' in combined_text and 'wine' in combined_text:
        continue
      return False
  
  # Check for positive keywords
  positive_matches = sum(1 for keyword in positive_keywords if keyword in combined_text)
  
  # Need at least 2 positive keyword matches to be confident
  # Or at least one strong match like "grape variety" or "wine grape"
  strong_matches = ['grape variety', 'wine grape', 'vitis vinifera', 'grape cultivar']
  has_strong_match = any(phrase in combined_text for phrase in strong_matches)
  
  if has_strong_match or positive_matches >= 2:
    return True
  
  return False


def get_wikipedia_image(grape_name, use_api=True, delay=0.1):
  """
  Get Wikipedia image URL for a grape name.
  Returns a dict with 'url' (image URL) and 'source' ('wikipedia') if found, None otherwise.
  Prefers original image over thumbnail.
  Validates that the Wikipedia page is actually about a grape/wine variety.
  """
  if not grape_name:
    return None
  
  # Skip grape names with numbers
  if any(char.isdigit() for char in grape_name):
    return None
  
  wiki_name = grape_name.replace(' ', '_')
  api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(wiki_name, safe='_')}"
  
  if delay > 0:
    time.sleep(delay)
  
  try:
    headers = {
      'User-Agent': 'WineGrapesBot/1.0 (https://github.com/djtrack16/wine_grapes; contact: see GitHub)'
    }
    
    if use_api:
      response = requests.get(api_url, headers=headers, timeout=5, allow_redirects=True)
      
      if response.status_code == 200:
        data = response.json()
        
        # Validate that the page is actually about a grape (pass grape_name for category checking)
        if not is_wikipedia_page_about_grape(data, grape_name=grape_name):
          return None
        
        # Prefer original image over thumbnail
        if 'originalimage' in data and 'source' in data['originalimage']:
          return {
            'url': data['originalimage']['source'],
            'source': 'wikipedia',
            'title': data.get('title', grape_name)
          }
        elif 'thumbnail' in data and 'source' in data['thumbnail']:
          return {
            'url': data['thumbnail']['source'],
            'source': 'wikipedia',
            'title': data.get('title', grape_name)
          }
    
    return None
  except (requests.RequestException, requests.Timeout):
    return None


def check_wikipedia_page_exists(grape_name, use_api=True, delay=0.1):
  """
  Check if a Wikipedia page exists for a grape name AND is actually about a grape/wine variety.
  Returns the Wikipedia URL if the page exists and is about grapes, None otherwise.
  Skips grape names that contain numbers (e.g., "Grape 6", "Variety 9") as they're unlikely to have Wikipedia pages.
  
  Args:
    grape_name: The name of the grape to check
    use_api: If True, use Wikipedia REST API (more efficient). If False, scrape HTML page.
    delay: Delay in seconds between requests to avoid rate limiting (default: 0.1s = 10 requests/second)
  
  Wikipedia rate limits:
    - Anonymous: 500 requests/hour (~8.3 requests/second)
    - Authenticated: 5,000 requests/hour (~83 requests/second)
    Default delay of 0.1s = 10 req/s is safe for anonymous requests.
  """
  if not grape_name:
    return None
  
  # Skip grape names with numbers (e.g., "Grape 6", "Variety 9")
  # These are unlikely to have Wikipedia pages
  if any(char.isdigit() for char in grape_name):
    return None
  
  wiki_url = get_wikipedia_url(grape_name)
  
  # Add delay to avoid rate limiting (respectful to Wikipedia's servers)
  if delay > 0:
    time.sleep(delay)
  
  try:
    headers = {
      'User-Agent': 'WineGrapesBot/1.0 (https://github.com/djtrack16/wine_grapes; contact: see GitHub)'
    }
    
    if use_api:
      # Use Wikipedia REST API - more efficient and better rate limits
      # API endpoint: https://en.wikipedia.org/api/rest_v1/page/summary/{title}
      wiki_name = grape_name.replace(' ', '_')
      api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(wiki_name, safe='_')}"
      
      response = requests.get(api_url, headers=headers, timeout=5, allow_redirects=True)
      
      # API returns 200 if page exists, 404 if it doesn't
      if response.status_code == 200:
        data = response.json()
        # Validate that the page is actually about a grape/wine variety (pass grape_name for category checking)
        if is_wikipedia_page_about_grape(data, grape_name=grape_name):
          return wiki_url
        else:
          # Page exists but is not about grapes (e.g., "Abaca" = banana plant)
          return None
      elif response.status_code == 404:
        return None
      elif response.status_code == 429:
        # Rate limited - wait longer and retry once
        time.sleep(2)
        response = requests.get(api_url, headers=headers, timeout=5, allow_redirects=True)
        if response.status_code == 200:
          data = response.json()
          if is_wikipedia_page_about_grape(data):
            return wiki_url
        return None
      else:
        return None
    else:
      # Fallback: scrape HTML page (less efficient, harder to validate)
      response = requests.get(wiki_url, headers=headers, timeout=5, allow_redirects=True)
      
      if response.status_code == 200:
        # Check if the page content indicates the page doesn't exist
        if 'does not exist' not in response.text.lower()[:5000]:
          # For HTML scraping, we can't easily validate it's about grapes
          # So we'll return it, but this is less reliable
          return wiki_url
      elif response.status_code == 429:
        # Rate limited - wait and retry once
        time.sleep(2)
        response = requests.get(wiki_url, headers=headers, timeout=5, allow_redirects=True)
        if response.status_code == 200 and 'does not exist' not in response.text.lower()[:5000]:
          return wiki_url
      return None
      
  except (requests.RequestException, requests.Timeout):
    # If request fails, assume page doesn't exist
    return None

