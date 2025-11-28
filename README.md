# wine_grapes
Useful ampelographic info about native wine grapes in different European Countries
All data has been scraped from https://www.vivc.de with `BeautifulSoup` library in Python.

## Usage

### Get native grape counts per country

```
python native_grapes.py show_count_for_country <put_country_name_here>
```

Example

```
python native_grapes.py show_count_for_country armenia
```

Note: If country name is more than one word, use `+` to join them. For example, `North+Macedonia`

### Show ancestry tree for a given grape name

```
python native_grapes.py show_ancestry <put_grape_name_here>
```

Example

```
python native_grapes.py show_ancestry abbuoto
```

Note: If grape name is more than one word, use `+` to join them. For example, `Pinot+Noir`

### Show general grape data for all countries

```
python native_grapes.py show_countries_grape_count
```

### Show direct descendants (i.e. no grandchildren or below) of a given grape cultivar

```
python native_grapes.py show_children <put_grape_name_here>
```

Example

```
python native_grapes.py show_ancestry chardonnay
```

Note: If grape name is more than one word, use `+` to join them. For example, `Pinot+Noir`
