import requests
from pprint import pprint
import json

ao_url = 'https://europe.albion-online-data.com'

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

def refresh_prices():
  with open('items.json', 'r') as file:
    items_data = json.load(file)
    consumable_items = items_data['items']['consumableitem']

    potions = [ item for item in consumable_items if item['@shopsubcategory1'] == 'potions']
    potions_names = [ potion['@uniquename'] for potion in potions ]
    enchanted_potions_names = [f"{name}@{i}" for name in potions_names for i in range(1, 4)]

    needed_prices = find_all_values(potions, '@uniquename') # find all potions and ingredients
    needed_prices = list(dict.fromkeys(needed_prices)) # removes dups
    needed_prices += enchanted_potions_names

    r = requests.get(f"{ao_url}/api/v2/stats/prices/{','.join(needed_prices)}.json?locations=Lymhurst,Caerleon,Martlock,Bridgewatch,Thetford,FortSterling,Brecilien&qualities=1")
    print(r.status_code)

    if r.status_code == 200:
      item_prices = r.json()
      with open('prices.json', 'w') as file:
        json.dump(item_prices, file, indent=2)
    else:
      return False

    r = requests.get(f"{ao_url}/api/v2/stats/history/{','.join(needed_prices)}.json?time-scale=1&locations=Lymhurst,Caerleon,Martlock,Bridgewatch,Thetford,FortSterling,Brecilian&qualities=1")
    print(r.status_code)

    if r.status_code == 200:
      item_prices = r.json()
      with open('hist_prices.json', 'w') as file:
        json.dump(item_prices, file, indent=2)
    else:
      return False
  return True
