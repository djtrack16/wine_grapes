# Native Wine Grapes Database

A comprehensive Django web application that provides detailed information about native wine grapes from around the world. The site displays grape profiles, country statistics, family relationships, and photos sourced from the Vitis International Variety Catalogue (VIVC).

## Overview

This website serves as a searchable database of native wine grapes, featuring:

- **Grape Profiles**: Detailed information about individual grape varieties including species, berry color, breeding information, and family relationships
- **Country Profiles**: Statistics and listings of native grapes by country of origin
- **Family Trees**: Visual representation of parent-child relationships between grape varieties
- **Photo Gallery**: Grape cluster photos from field and laboratory settings
- **Search Functionality**: Autocomplete search to quickly find grapes by name

## Data Source

All grape data is sourced from the **Vitis International Variety Catalogue (VIVC)** at [www.vivc.de](https://www.vivc.de), a comprehensive database maintained by the Julius Kühn-Institut (JKI) in Germany. The data includes:

- Grape names and VIVC identification numbers
- Berry colors (Red, Black, Pink, White, Unknown)
- Species information (e.g., Vitis Vinifera)
- Country of origin
- Breeding information (year of crossing, breeder name)
- Parent-child relationships (ancestry and descendants)
- Grape cluster photos with attribution

The data is scraped and imported into a SQLite database using Django management commands, which can be updated periodically to reflect new information from VIVC.

## Features and Capabilities

### Grape Profile Pages

Each grape has a detailed profile page showing:

- **Basic Information**:
  - Grape name
  - Berry color
  - Country of origin (with link to country page)
  - Species (if available)
  - Year of crossing (if available)
  - Breeder name (if available)
  - Link to VIVC page

- **Visual Content**:
  - Grape cluster photo (prioritizes "cluster in the field" over "cluster in the laboratory")
  - Photo credit information
  - Responsive photo positioning that adapts to screen size

- **Family Relationships**:
  - **Parents**: Direct ancestor grapes (both parents if known)
  - **Children**: Direct descendant grapes in a table format showing:
    - Child grape name
    - Other parent (the grape crossed with the current grape)
  - Country of origin is shown for parents/children only when different from the current grape's country

### Country Profile Pages

Country pages display:

- Country name (properly capitalized)
- Total number of native grapes
- **Grapes by Color**: A table showing the count of grapes for each berry color:
  - Colors sorted by count (descending)
  - "Unknown" always appears last
- Complete list of all native grapes for that country
- Link to VIVC search page for that country

### Search Functionality

- **Autocomplete Search**: 
  - Real-time search as you type
  - Dropdown list of matching grapes (up to 20 results)
  - Keyboard navigation (arrow keys, Enter, Escape)
  - Click or press Enter to navigate directly to grape page
  - Works on both local Django site and static GitHub Pages deployment

- **Search Results Page**:
  - Displays all grapes matching the search query
  - Shows grape name, berry color, and country of origin
  - Links to individual grape profiles

### Responsive Design

- Mobile-friendly layout
- Photo positioning adapts to screen size
- Tables and content reflow for smaller screens
- Search functionality works across all devices

## Technical Details

### Technology Stack

- **Backend**: Django (Python web framework)
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript
- **Data Scraping**: BeautifulSoup, requests

### Database Schema

The application uses three main models:

1. **Country**: Stores country information (name, ISO code, VIVC search URL)
2. **Grape**: Stores grape data (name, VIVC ID, berry color, species, breeder, year of crossing, country of origin, relationships)
3. **GrapePhoto**: Stores photo URLs and metadata (grape reference, photo type, source attribution)

### Management Commands

The application includes several Django management commands for data import and maintenance:

- `import_grapes`: Import grape data from VIVC for specified countries
  - Supports selective field import (`--fields` argument)
  - Can resume from a specific country (`--start-from` argument)
  - Skips countries that already have grapes (unless updating)

- `import_relationships`: Import parent-child relationships for grapes in a specific country
  - Only processes grapes from the specified country
  - Skips grapes that already have relationships

- `import_all_relationships`: Import missing relationships for all grapes
  - Skips grapes that have already been processed
  - Marks grapes with `date_last_crawled` timestamp

- `import_grape_photos`: Import grape cluster photos from VIVC
  - Prioritizes "cluster in the field" photos
  - Imports both field and laboratory photos
  - Skips duplicate photos

- `check_relationships_status`: Check how many grapes in a country lack relationship data

- `normalize_data`: Normalize existing data (colors, names) in the database

- `build_static`: Generate a static HTML version of the site for GitHub Pages deployment

### Static Site Generation

The site can be converted to a static HTML website for deployment on platforms like GitHub Pages. The `build_static` command:

- Generates all HTML pages from Django templates
- Creates a `grapes.json` file for search autocomplete
- Maintains the same URL structure and functionality
- Produces a fully functional static site without requiring a server

See `STATIC_SITE_GUIDE.md` for detailed instructions on building and deploying the static site.

## Usage

### Browsing the Site

1. **Home Page**: Lists all countries with their native grape counts, sorted by number of grapes
2. **Country Pages**: Click on any country to see its native grapes and color statistics
3. **Grape Pages**: Click on any grape name to view its detailed profile
4. **Search**: Use the search bar in the navigation to quickly find grapes by name

### Searching for Grapes

1. Type a grape name (or partial name) in the search box
2. Select a grape from the autocomplete dropdown, or
3. Press Enter to see all matching results
4. Click on any result to view the grape's profile

### Understanding Grape Relationships

- **Parents**: The two grapes that were crossed to create this grape
- **Children**: Grapes that were created by crossing this grape with another grape
- **Other Parent**: When viewing children, this shows the grape that was crossed with the current grape to create the child

Country information is only shown for parents/children when it differs from the current grape's country of origin, to avoid redundant information.

## Development

### Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Run migrations: `python manage.py migrate`
3. Import data: `python manage.py import_grapes`
4. Run development server: `python manage.py runserver`

### Data Import Workflow

1. Import countries: `python manage.py add_missing_countries` (if needed)
2. Import grapes: `python manage.py import_grapes`
3. Import relationships: `python manage.py import_relationships <country_name>`
4. Import photos: `python manage.py import_grape_photos`

### File Structure

- `grapes/`: Main Django app
  - `models.py`: Database models
  - `views.py`: View functions
  - `templates/`: HTML templates
  - `management/commands/`: Django management commands
  - `templatetags/`: Custom template filters
- `native_grapes.py`: Original scraping script (not modified by this project)
- `wine_grapes/`: Django project settings

## License

See LICENSE file for details.

## Acknowledgments

- **VIVC (Vitis International Variety Catalogue)**: Primary data source
- **Julius Kühn-Institut (JKI)**: Maintainers of the VIVC database
- Photo credits are attributed to VIVC and individual photographers as provided by the source

## Native Grape Resources

### International:

- [Wine Grapes](https://www.amazon.com/Wine-Grapes-Complete-Varieties-Including/dp/0062206362)

### By Country

- **Switzerland**: [Swiss Grapes](https://www.amazon.com/Swiss-Grapes-History-Jose-Vouillamoz/dp/1729157440/)
- **Italy**: [Native Wine Grapes of Italy](https://www.amazon.com/Native-Wine-Grapes-Italy-DAgata/dp/0520272269/)
- **Georgia**: 
  - [Georgian Ampelography definitive botanical text](https://dspace.nplg.gov.ge/handle/1234/4976)
- **Armenia**: [Vitis.am](http://www.vitis.am/)
