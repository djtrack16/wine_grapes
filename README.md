# Native Wine Grapes
Useful ampelographic info about native wine grapes in different European Countries. All data has been scraped from https://www.vivc.de with `BeautifulSoup` library in Python.

## Usage

Python version used: `3.12.4`

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
python native_grapes.py show_children chardonnay
```

Note: If grape name is more than one word, use `+` to join them. For example, `Pinot+Noir`

## Postscript

If there is a grape ID in the any output, to see the full link to the grape name, simply insert the ID at the last part of the url and paste in the browser:

For example, the grape ID for `Aglianico`, an Italian native grape, is `121`. Here is the full link:

```
https://www.vivc.de/index.php?r=passport%2Fview&id=121
```

### Native Grape Resources

# International:

[Wine Grapes](https://www.amazon.com/Wine-Grapes-Complete-Varieties-Including/dp/0062206362)

# By Country

* [Switzerland](https://www.amazon.com/Swiss-Grapes-History-Jose-Vouillamoz/dp/1729157440/)
* [Italy](https://www.amazon.com/Native-Wine-Grapes-Italy-DAgata/dp/0520272269/)
* [Georgia](https://www.google.com/search?q=Georgian+Ampelography+book&oq=Georgian+Ampelography+book&gs_lcrp=EgZjaHJvbWUyBggAEEUYOTIKCAEQABiABBiiBDIHCAIQABjvBTIKCAMQABiABBiiBDIKCAQQABiABBiiBDIGCAUQRRg8MgYIBhBFGDzSAQg0MzEzajBqNKgCALACAQ&sourceid=chrome&ie=UTF-8)
  + [Georgian Ampelography definitive botanical text](https://dspace.nplg.gov.ge/handle/1234/4976)
* [Armenia](http://www.vitis.am/)

