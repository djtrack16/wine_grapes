"""
Template filters for the grapes app.
"""
from django import template

register = template.Library()


@register.filter
def title_country(country_name):
  """
  Title-case country names, keeping prepositions lowercase.
  Examples:
    - "united states of america" -> "United States of America"
    - "united kingdom" -> "United Kingdom"
    - "south africa" -> "South Africa"
  """
  if not country_name:
    return country_name
  
  # Prepositions and articles to keep lowercase (unless first word)
  lowercase_words = {'of', 'and', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'with', 'by'}
  
  words = country_name.split()
  result = []
  
  for i, word in enumerate(words):
    if i == 0:
      # Always capitalize first word
      result.append(word.capitalize())
    elif word.lower() in lowercase_words:
      # Keep prepositions lowercase
      result.append(word.lower())
    else:
      # Capitalize other words
      result.append(word.capitalize())
  
  return ' '.join(result)
