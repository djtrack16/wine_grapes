# Static Site Generation for GitHub Pages

## Minimum Changes Made

To convert this Django site to a static site for GitHub Pages, the following minimal changes were made:

### 1. **Build Command** (`grapes/management/commands/build_static.py`)
   - New management command that generates static HTML files
   - Creates folder-based routing (`country/USA/index.html`, `grape/123/index.html`)
   - Adds `.url` attributes to model instances for static URLs
   - Creates `.nojekyll` file for GitHub Pages

### 2. **Template Updates** (Backward Compatible)
   - Templates now check for `.url` attribute first (static mode), then fall back to Django's `{% url %}` (development mode)
   - Modified templates:
     - `grapes/templates/grapes/base.html` - Added `index_url` variable support
     - `grapes/templates/grapes/index.html` - Uses `country.url` if available
     - `grapes/templates/grapes/country_detail.html` - Uses `grape.url` if available  
     - `grapes/templates/grapes/grape_detail.html` - Uses static URLs for all links if available

### 3. **No Changes Needed To:**
   - Models
   - Views (still work for localhost development)
   - URL routing (still works for localhost)
   - Database

## How to Build Static Site

```bash
# Build static site to _site directory
python manage.py build_static

# Or specify output directory
python manage.py build_static --output-dir docs
```

## GitHub Pages Setup

1. **Build the static site:**
   ```bash
   python manage.py build_static --output-dir docs
   ```

2. **Commit and push:**
   ```bash
   git add docs/
   git commit -m "Build static site for GitHub Pages"
   git push
   ```

3. **Enable GitHub Pages:**
   - Go to repository Settings → Pages
   - Source: Deploy from a branch
   - Branch: `main` (or your branch)
   - Folder: `/docs`
   - Save

4. **Access your site:**
   - Your site will be available at: `https://YOUR_USERNAME.github.io/wine_grapes/`

## File Structure Generated

```
_site/ (or docs/)
├── .nojekyll
├── index.html
├── country/
│   ├── usa/
│   │   └── index.html
│   ├── fra/
│   │   └── index.html
│   └── ...
└── grape/
    ├── 123/
    │   └── index.html
    ├── 456/
    │   └── index.html
    └── ...
```

## Development vs Static

- **Development (localhost):** Continue using `python manage.py runserver` - all Django features work normally
- **Static Site:** Run `python manage.py build_static` to generate static files for GitHub Pages

The templates are backward compatible - they work in both modes!
