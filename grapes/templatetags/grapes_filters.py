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


@register.filter
def break_long_text(text, max_chars=65):
  """
  Break text into multiple lines, never exceeding max_chars per line.
  If a word would be split in the middle, hyphenate it.
  
  Example:
    "university" split at position 4 -> "univ-" on first line, "ersity" on second
  """
  if not text or len(text) <= max_chars:
    return text
  
  lines = []
  current_line = []
  current_length = 0
  
  words = text.split()
  
  for word in words:
    word_len = len(word)
    
    # If word fits on current line, add it
    if current_length == 0:
      # First word on line
      if word_len <= max_chars:
        current_line.append(word)
        current_length = word_len
      else:
        # Word is too long, need to hyphenate
        while word_len > max_chars:
          # Take max_chars - 1 (for hyphen) from word
          part = word[:max_chars - 1]
          lines.append(part + '-')
          word = word[max_chars - 1:]
          word_len = len(word)
        if word:
          current_line.append(word)
          current_length = word_len
    else:
      # Check if word fits with a space
      if current_length + 1 + word_len <= max_chars:
        current_line.append(word)
        current_length += 1 + word_len
      else:
        # Word doesn't fit, finish current line
        if current_line:
          lines.append(' '.join(current_line))
        current_line = []
        current_length = 0
        
        # Now add the word (might need hyphenation)
        if word_len <= max_chars:
          current_line.append(word)
          current_length = word_len
        else:
          # Word is too long, need to hyphenate
          while word_len > max_chars:
            # Take max_chars - 1 (for hyphen) from word
            part = word[:max_chars - 1]
            lines.append(part + '-')
            word = word[max_chars - 1:]
            word_len = len(word)
          if word:
            current_line.append(word)
            current_length = word_len
  
  # Add remaining line
  if current_line:
    lines.append(' '.join(current_line))
  
  return '<br>'.join(lines)
