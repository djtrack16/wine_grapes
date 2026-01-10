"""
Utility functions for normalizing grape data.
"""


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

