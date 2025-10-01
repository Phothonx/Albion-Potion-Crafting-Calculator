import requests
from pprint import pprint
import json

ao_rendered_url = 'https://render.albiononline.com/v1/item/'

def find_all_values(data, target_key):
  results = []
  if isinstance(data, dict):
    for key, value in data.items():
      if key == target_key:
        results.append(value)
      results.extend(find_all_values(value, target_key))
  elif isinstance(data, list):
     for item in data:
       results.extend(find_all_values(item, target_key))
  return results

with open('items.json', 'r') as file:
  items_data = json.load(file)
  consumable_items = items_data['items']['consumableitem']

  potions = [ item for item in consumable_items if item['@shopsubcategory1'] == 'potions']
  potions_names = [ potion['@uniquename'] for potion in potions ]
  enchanted_potions_names = [f"{name}@{i}" for name in potions_names for i in range(1, 4)]

  needed_prices = find_all_values(potions, '@uniquename') # find all potions and ingredients
  needed_prices = list(dict.fromkeys(needed_prices)) # removes dups
  needed_prices += enchanted_potions_names

  for potion_id in needed_prices:
    r = requests.get(f"{ao_rendered_url}{potion_id}.png")
    print(r.status_code)
    if r.status_code == 200:
      with open(f'images/{potion_id}.png', 'wb') as file:
        file.write(r.content)
