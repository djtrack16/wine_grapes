import requests, sys
from bs4 import BeautifulSoup
from collections import defaultdict
from pprint import pprint

ARMENIAN_GRAPE_BASE_URL = 'http://www.vitis.am'
VIVC_BASE_URL = 'https://www.vivc.de'

COUNTRIES_NAME_TO_ISO_CODE = {
  'albania': 'ALB',
  'andorra': 'AND',
  'armenia': 'ARM',
  'austria': 'AUT',
  'azerbaijan': 'AZE',
  'belarus': 'BLR',
  'belgium': 'BEL',
  'bosnia and herzegovina': 'BIH',
  'bulgaria': 'BGR',
  'croatia': 'HRV',
  'cyprus': 'CYP',
  'czechia': 'CZE',
  'denmark': 'DNK',
  'estonia': 'EST',
  'finland': 'FIN',
  'france': 'FRA',
  'georgia': 'GEO',
  'germany': 'DEU',
  'greece': 'GRC',
  'hungary': 'HUN',
  'iceland': 'ISL',
  'ireland': 'IRL',
  'italy': 'ITA',
  'kazakhstan': 'KAZ',
  'kosovo': 'XKX',
  'latvia': 'LVA',
  'liechtenstein': 'LIE',
  'lithuania': 'LTU',
  'luxembourg': 'LUX',
  'malta': 'MLT',
  'moldova': 'MDA',
  'monaco': 'MCO',
  'montenegro': 'MNE',
  'netherlands': 'NLD',
  'north macedonia': 'MKD',
  'norway': 'NOR',
  'poland': 'POL',
  'portugal': 'PRT',
  'romania': 'ROU',
  'russia': 'RUS',
  'san marino': 'SMR',
  'serbia': 'SRB',
  'slovakia': 'SVK',
  'slovenia': 'SVN',
  'spain': 'ESP',
  'sweden': 'SWE',
  'switzerland': 'CHE',
  'turkey': 'TUR',
  'ukraine': 'UKR',
  'united kingdom': 'GBR',
  'vatican city': 'VAT'
}

class NativeGrapes:
  
  @staticmethod
  def grape_list_by_country(country_name):
    if country_name not in COUNTRIES_NAME_TO_ISO_CODE:
      print("Country not found. Sorry. Please make sure spelling is exact")
      return
    
    list, grape_color_count, non_vinifera_crossings = NativeGrapes.grape_data_by_country_iso_code(COUNTRIES_NAME_TO_ISO_CODE[country_name])
    return list, grape_color_count, non_vinifera_crossings
  
  @staticmethod
  def grape_info_for_all_countries():
    grape_counts = []
    print("Grape Data per European Country (per https://www.vivc.de)")
    print("COUNTRY NAME, LIKELY NATIVE GRAPE COUNT, Non-vinifera crossings")
    for country_name, iso_code in COUNTRIES_NAME_TO_ISO_CODE.items():
      _, grape_color_count, non_vinifera_crossings = NativeGrapes.grape_data_by_country_iso_code(iso_code)
      total_count = sum(grape_color_count.values())
      hybrid_count = sum(non_vinifera_crossings.values())
      estimated_native_grape_count = total_count - hybrid_count
      grape_counts.append([
        country_name.capitalize(),
        estimated_native_grape_count,
        hybrid_count]
      )
      print(f"{country_name.capitalize()} is done")
    grape_counts.sort(key=lambda x: x[1])
    grape_counts.reverse() # in descending order of estimated native grape count
    return grape_counts


  @staticmethod
  def grape_data_by_country_iso_code(iso_code):
    """Crawl grape names from VIVC German database with pagination."""
    all_grapes = []
    page_num = 1
    per_page = 500  # Max results per page
    grape_color_count = defaultdict(int)
    non_vinifera_crossings = defaultdict(int)
    
    while True:
      url = f"{VIVC_BASE_URL}/index.php?per-page={per_page}&page={page_num}&SpeciesSearch[landescode22]={iso_code}&r=species%2Fcountry"
      response = requests.get(url)
      page = BeautifulSoup(response.text, 'html.parser')
      
      tbody = page.select('tbody')
      if not tbody:
        break
      
      rows = tbody[0].find_all('tr')
      if not rows:  # No more results
        break
      
      for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 4:
          link_tag = cells[0].find('a')
          if link_tag:
            name = link_tag.text
            url = f"{VIVC_BASE_URL}/{link_tag['href']}"
            species = cells[2].text.strip()
            color_tag = cells[3].find('a')
            color = color_tag.text if color_tag.text else 'NOT SPECIFIED'
            all_grapes.append([name, url, color])
            grape_color_count[color] += 1
            if 'VINIFERA' not in species and species != "":
              non_vinifera_crossings[species] += 1 
      # Check if there are more pages by looking for pagination controls
      # or if we got fewer results than per_page
      if len(rows) < per_page:
        break
      
      page_num += 1
    
    return all_grapes, grape_color_count, non_vinifera_crossings
  
  @staticmethod
  def vitis_am_crawl():
    """Crawl grape names from Armenian VITIS database."""
    url = f"{ARMENIAN_GRAPE_BASE_URL}/eng/search/index/"
    response = requests.get(url, allow_redirects=False)
    page = BeautifulSoup(response.text, 'html.parser')
    
    grape_data = []  # List of tuples: (href, name)
    
    # Find the table by id
    table = page.find('table', id='search_table')
    
    if table:
      # Find all rows in tbody
      rows = table.find('tbody').find_all('tr')
      
      for row in rows:
        link = row.find('a')
        if link:
          name = link.get_text().strip()
          href = link.get('href')
          grape_data.append([name, f"{ARMENIAN_GRAPE_BASE_URL}{href}"])
    
    return grape_data
  
  @staticmethod
  def get_grape_ancestry(grape_id, visited=None):
    """
    Recursively build the ancestral lineage of a grape variety.
    
    Args:
      grape_id: The VIVC ID of the grape
      visited: Set of already visited IDs to avoid circular references
    
    Returns:
      Dictionary with grape info and parents
    """
    if visited is None:
      visited = set()
    
    # Avoid circular references
    if grape_id in visited:
      return None
    
    visited.add(grape_id)
    
    url = f"{VIVC_BASE_URL}/index.php?r=passport%2Fview&id={grape_id}"
    response = requests.get(url)
    page = BeautifulSoup(response.text, 'html.parser')
    
    # Extract grape information from the table
    grape_info = {
      'id': grape_id,
      'url': url,
      'name': None,
      'full_pedigree': False,
      'parents': []
    }
    
    # Find all table rows
    rows = page.select('div.passport-view table tr')
    
    for row in rows:
      cells = row.find_all('th') + row.find_all('td')
      if len(cells) >= 2:
        key = cells[0].get_text().strip()

        #print(key)
        value_cell = cells[1]
        if 'prime name' in key.lower() and 'parent' not in key.lower():
          grape_info['name'] = value_cell.get_text().strip()
        elif 'full pedigree' in key.lower():
          
          value = value_cell.get_text().strip().lower()
          grape_info['full_pedigree'] = (value == 'yes')
        elif 'prime name of parent 1' in key.lower():
          parent_link = value_cell.find('a')
          if parent_link and parent_link.get('href'):
            parent_href = parent_link['href']
            # Extract parent ID from URL like "index.php?r=passport%2Fview&id=12345"
            if 'id=' in parent_href:
              parent_id = parent_href.split('id=')[-1]
              parent_name = parent_link.get_text().strip()
              #print(parent_name)
              print(f" Found parent 1 of {grape_info['name']}: {parent_name} (ID: {parent_id})")
              parent_data = NativeGrapes.get_grape_ancestry(parent_id, visited)
              if parent_data:
                grape_info['parents'].append(parent_data)
        
        elif 'prime name of parent 2' in key.lower():
          parent_link = value_cell.find('a')
          if parent_link and parent_link.get('href'):
            parent_href = parent_link['href']
            if 'id=' in parent_href:
              parent_id = parent_href.split('id=')[-1]
              parent_name = parent_link.get_text().strip()
              print(f" Found parent 2 of {grape_info['name']}: {parent_name} (ID: {parent_id})")
              parent_data = NativeGrapes.get_grape_ancestry(parent_id, visited)
              if parent_data:
                grape_info['parents'].append(parent_data)
        elif 'country or region of origin' in key.lower():
          grape_info['country_of_origin'] = value_cell.get_text().strip()
    
    return grape_info

  @staticmethod
  def print_ancestry_tree(grape_data, indent=0):
    """Pretty print the ancestry tree."""
    if not grape_data:
      return
    
    prefix = "    " * indent
    name = grape_data.get('name', 'Unknown')
    grape_id = grape_data.get('id', 'Unknown')
    full_ped = grape_data.get('full_pedigree', False)
    country = grape_data['country_of_origin'] or "Unknown"
    
    print(f"{prefix}{name} (ID: {grape_id}, Country Of Origin: {country})")
    
    for parent in grape_data.get('parents', []):
      NativeGrapes.print_ancestry_tree(parent, indent + 1)

  @staticmethod
  def find_grape_id_by_name(grape_name, show_all=False):
    """
    Search for a grape by name and return its VIVC ID.
    
    Args:
      grape_name: Name of the grape variety
      show_all: If True, show all results and let user choose
    
    Returns:
      Tuple of (grape_id, prime_name, url) or None if not found
    """
    search_url = f"{VIVC_BASE_URL}/index.php?r=cultivarname%2Findex&CultivarnameSearch%5Bcultivarnames%5D=&CultivarnameSearch%5Bcultivarnames%5D=leitname&CultivarnameSearch%5Btext%5D={grape_name}"
    response = requests.get(search_url)
    page = BeautifulSoup(response.text, 'html.parser')
    
    tbody = page.select('tbody')
    if not tbody:
      print(f"No results found for '{grape_name}'")
      return None
    
    rows = tbody[0].find_all('tr')
    if not rows:
      print(f"No results found for '{grape_name}'")
      return None
    
    # Collect all results
    results = []
    for row in rows:
      cells = row.find_all('td')
      if len(cells) >= 2:
        link = cells[0].find('a')
        if link and 'href' in link.attrs:
          href = link['href']
          prime_name = link.get_text().strip()
          
          if 'id=' in href:
            grape_id = href.split('id=')[-1].split('&')[0]
            full_url = f"{VIVC_BASE_URL}/{href}" if not href.startswith('http') else href
            results.append((grape_id, prime_name, full_url))
    
    if not results:
      print(f"Could not extract grape ID from results for '{grape_name}'")
      return None
    
    if show_all and len(results) > 1:
      print(f"Found {len(results)} results for '{grape_name}':")
      for i, (gid, name, _) in enumerate(results, 1):
        print(f"  {i}. {name} (ID: {gid})")
      return results
    
    # Return first result
    grape_id, prime_name, full_url = results[0]
    print(f"Found: {prime_name} (ID: {grape_id})")
    return grape_id

  @staticmethod
  def find_grape_children(grape_name):
    """
    Find all offspring/children of a grape variety.
    
    Args:
      grape_name: Name of the grape variety
    
    Returns:
      List of dictionaries with child grape info
    """
    search_url = f"{VIVC_BASE_URL}/index.php?r=pedigree%2Findex&PedigreeSearch%5Btext%5D={grape_name}"
    response = requests.get(search_url)
    page = BeautifulSoup(response.text, 'html.parser')
    
    children = []
    
    # Find the results table
    tbody = page.select('tbody')
    if not tbody:
      print(f"No children found for '{grape_name}'")
      return children
    
    rows = tbody[0].find_all('tr')
    if not rows:
      print(f"No children found for '{grape_name}'")
      return children
    
    # Parse each row
    for row in rows:
      cells = row.find_all('td')
      if len(cells) >= 3:
        # First cell: child name
        child_link = cells[0].find('a')
        #print(child_link)
        if not child_link:
          continue
        
        child_name = child_link.get_text().strip()
        child_href = child_link.get('href', '')
        child_id = child_href.split('id=')[-1].split('&')[0] if 'id=' in child_href else None
        
        # Second cell: parent 1
        parent1_link = cells[2].find('a')
        parent1_name = parent1_link.get_text().strip() if parent1_link else cells[2].get_text().strip()
        #print("name", parent1_name)
        
        # Third cell: parent 2
        parent2_link = cells[3].find('a')
        parent2_name = parent2_link.get_text().strip() if parent2_link else cells[3].get_text().strip()
        
        # Filter: only include if grape_name matches parent1 or parent2 exactly
        # (case-insensitive comparison to handle variations)
        if (grape_name.lower() == parent1_name.lower() or 
            grape_name.lower() == parent2_name.lower()):
          
          child_info = {
            'name': child_name,
            'id': child_id,
            'url': f"{VIVC_BASE_URL}/{child_href}" if child_href else None,
            'parent1': parent1_name,
            'parent2': parent2_name
          }
          children.append(child_info)
    
    print(f"Found {len(children)} children for '{grape_name}'")
    return children

  @staticmethod
  def print_children(children):
    """Pretty print the list of children."""
    if not children:
      print("No children found.")
      return
    
    print(f"\n{'Child Name':<40} {'Parent 1':<30} {'Parent 2':<30}")
    print("=" * 100)
    
    for child in children:
      print(f"{child['name']:<40} {child['parent1']:<30} {child['parent2']:<30}")

if __name__ == '__main__':

  method = sys.argv[1]
  arg = sys.argv[2].lower()
  match method:
    case 'show_count_for_country':
      if arg in COUNTRIES_NAME_TO_ISO_CODE:
        pprint(NativeGrapes.grape_list_by_country(arg))
    case 'show_ancestry':
      grape_name = " ".join(arg.split('+'))
      vivc_id = NativeGrapes.find_grape_id_by_name(grape_name)
      if vivc_id:
        ancestry = NativeGrapes.get_grape_ancestry(vivc_id)
        if ancestry and ancestry['parents']:
          # Print the tree
          print("\nAncestry Tree:")
          print("=" * 75)
          NativeGrapes.print_ancestry_tree(ancestry)
          print("=" * 75)
          print("To find the official VIVC page for a given grape, copy-paste this url in the browser with the grape ID")
          print("For example, if the ID is 4419: https://www.vivc.de/index.php?r=passport%2Fview&id=4419")
        else:
          print("No ancestry was found for this grape. Please try another grape!")
      else:
        print("This grape variety name was not matched to a valid ID in the VIVC database. Please try again")

    case 'show_countries_grape_count':
      pprint(NativeGrapes.grape_info_for_all_countries())
    case "show_children":
      grape_name = " ".join(arg.split('+'))
      children = NativeGrapes.find_grape_children(grape_name)
      NativeGrapes.print_children(children)
