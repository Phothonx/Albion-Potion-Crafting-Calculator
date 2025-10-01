import json
from nicegui import ui
from pprint import pprint
from datetime import datetime, timedelta
from matplotlib import pyplot as plt
from get_prices import refresh_prices

# TODO
# 1 - data validation non None for prices etc..
# 2 - auto calculate on change

def remove_outliers(y, m=2):
  mean = sum(y) / len(y)
  std = (sum((val - mean) ** 2 for val in y) / len(y)) ** 0.5
  return [val if abs(val - mean) < m * std else mean for val in y]

def lissage_moyenne_glissante(y, window_size=3):
  if window_size % 2 == 0:
    raise ValueError("window_size must be odd for centered moving average")
  half_window = window_size // 2
  y_smoothed = []
  for i in range(len(y)):
    if i < half_window or i >= len(y) - half_window:
      # Keep original values at edges (or choose to drop or interpolate)
      y_smoothed.append(y[i])
    else:
      window = y[i - half_window : i + half_window + 1]
      average = sum(window) / window_size
      y_smoothed.append(average)

  return y_smoothed

class RessourceRow:
  def __init__(self, ressource:dict, price, parent=None):
    self.amount = int(ressource['@count'])
    self.unique_name = ressource['@uniquename']
    self.artifact = '@maxreturnamount' in ressource
    with parent:
      with ui.row().classes('items-center gap-2 bg-stone-900 p-2'):
        ui.image(f'images/{self.unique_name}.png').style('width: 64px; height: 64px;')
        ui.label(self.unique_name).classes('whitespace-nowrap w-52 text-sm')
        ui.label(f"x {self.amount}").classes('whitespace-nowrap w-24 text-sm')
        self.checkbox = ui.checkbox(value=self.artifact).classes('whitespace-nowrap w-24 text-sm')
        self.price_input = ui.input(value = price, label='Price', placeholder='Missing price')

class PotionsCraft:
  def __init__(self):
    with open('items.json', 'r') as file:
      self.items = json.load(file)
    with open('prices.json', 'r') as file:
      self.prices = json.load(file)
    with open('hist_prices.json', 'r') as file:
      self.hist_prices = json.load(file)

    self.potion = None

    consumable_items = self.items['items']['consumableitem']
    self.potions = [ item for item in consumable_items if item['@shopsubcategory1'] == 'potions']
    potions_names = [ potion['@uniquename'] for potion in self.potions ]
    potions_names.sort()

    with ui.row().classes('w-full h-full'):
      with ui.column().classes('bg-stone-800 rounded-lg p-4 h-full'):
        ui.label('Albion Potion Crafting Calculator').classes('text-2xl')
        self.city_input = ui.toggle(["Lymhurst", "Caerleon", "Martlock", "Bridgewatch", "Thetford", "Fort Sterling", "Brecilien"], value="Lymhurst", on_change=self.show)
        with ui.row():
          self.selling_tax_input = ui.number(label='Selling tax (%)', value=6.5)
          self.return_rate_input = ui.number(label='Return Rate (%)', value=15)
          self.usage_fee_input = ui.number(label='Usage fee', value=600)
        with ui.row().classes('items-center gap-2'):
          self.potion_input = ui.select(potions_names, with_input=True, label="Potion", on_change=self.show)
          self.enchant_input = ui.toggle([0, 1, 2, 3], value=0, on_change=self.show)
        with ui.row():
          ui.button('Calculate', on_click=self.calculate)
          ui.button('Refresh', on_click=refresh_prices)

        with ui.column().classes('h-fill justify-end'):
          with ui.row().classes('items-center gap-2'):
            self.potion_image = ui.image('images/DEFAULT.png').style('width: 64px; height: 64px;')
            self.price_input_potion = ui.input(label='Price')

          with ui.row().classes('items-center gap-2'):
            ui.label(' ').classes('whitespace-nowrap w-16 text-sm')
            ui.label('Ingredients').classes('whitespace-nowrap w-52 text-sm')
            ui.label('Quantités').classes('whitespace-nowrap w-24 text-sm')
            ui.label('Artefacts').classes('whitespace-nowrap w-24 text-sm')
            ui.label('Prix').classes('whitespace-nowrap w-16 text-sm')

          self.ressources_inputs = []
          with ui.row():
            self.ressources_ui_container = ui.column()

      with ui.column().classes('flex-grow items-center bg-stone-800 rounded-lg p-4 h-full'):
        with ui.row().classes('items-center gap-2'):
          self.potion_image_output = ui.image().style('width: 64px; height: 64px;')
          self.potion_label = ui.label('')
        with ui.row().classes('items-center gap-2'):
          ui.label('Tax: ').classes('text-xl')
          self.craft_tax_price = ui.label().classes('text-xl')
          ui.label(' ').classes('w-16')
          ui.label('Craft Price: ').classes('text-xl')
          self.potion_craft_cost = ui.label().classes('text-xl')
          ui.label(' ').classes('w-16')
          ui.label('Rentabilité: ').classes('text-xl')
          self.rentability = ui.label().classes('text-xl')
          ui.label('% (with selling tax)').classes('text-xl')

        self.plot_col = ui.column()
        self.plot_ui_prices = None
        self.plot_ui_amouts = None


  def run(self):
    ui.dark_mode().enable()
    ui.run()

  def get_current_item_price(self, item_id:str):
    item_price = next(item for item in self.prices if item['item_id'] == item_id and item['city'] == self.city_input.value)
    sell_price_min = int(item_price['sell_price_min'])
    if sell_price_min == 0:
      hist_price = self.get_historical_item_price(item_id)
      sell_price_min = int(hist_price[-1]['avg_price']) if hist_price else None # most recent average price
    return sell_price_min if sell_price_min != 0 else None


  def get_historical_item_price(self, item_id:str):
    item = next((item for item in self.hist_prices if item['item_id'] == item_id and item['location'] == self.city_input.value), None)
    return item['data'] if item else None

  def add_materials(self):
    if self.enchant_input.value == 0:
      craft_ressources = self.potion['craftingrequirements']['craftresource']
    else:
      craft_ressources = self.potion['enchantments']['enchantment'][self.enchant_input.value - 1]['craftingrequirements']['craftresource']
    if '@count' in craft_ressources:
      row = RessourceRow(craft_ressources, self.get_current_item_price(craft_ressources['@uniquename'] + ( f"@{self.enchant_input.value}" if self.enchant_input.value != 0 else "" )), parent=self.ressources_ui_container)
      self.ressources_inputs.append(row)
    else:
      for ressource in craft_ressources:
        row = RessourceRow(ressource, self.get_current_item_price(ressource['@uniquename']), parent=self.ressources_ui_container)
        self.ressources_inputs.append(row)

  def clear_materials(self):
    self.ressources_ui_container.clear()
    self.ressources_inputs.clear()

  def plot_data(self):
    self.plot_ui_prices = None
    self.plot_ui_amouts = None
    self.plot_col.clear()
    potion_id = self.potion['@uniquename'] + ( f"@{self.enchant_input.value}" if self.enchant_input.value != 0 else "" )
    print(potion_id)
    data = self.get_historical_item_price(potion_id)
    if data:
      price = self.get_current_item_price(potion_id)
      # only last 14 days
      two_week_ago = datetime.now() - timedelta(days=14)
      filtered_data = [item for item in data if datetime.fromisoformat(item['timestamp']) >= two_week_ago]
      raw_y = [ int(item['avg_price']) for item in filtered_data ]
      y = lissage_moyenne_glissante(remove_outliers(raw_y), 7)
      x = [ datetime.fromisoformat(item['timestamp']) for item in filtered_data ]
      with self.plot_col:
        self.plot_ui_prices = ui.pyplot(figsize=(8, 4.5))
        with self.plot_ui_prices:
          plt.plot(x, y, "-b", label="Prix moyen")
          plt.plot([x[0], x[-1]], [price, price], "-g", label="Prix Actuel")
          plt.plot([x[0], x[-1]], [int(self.potion_craft_cost.text), int(self.potion_craft_cost.text)], "-r", label="Coût du craft")
          plt.xticks(rotation=45)
          plt.legend()
          plt.title(f'Historical Prices for {potion_id}')
          plt.ylabel('Average Price (Silver)')
          plt.xlabel('Time UTC')

        time_ago = datetime.now() - timedelta(days=3)
        filtered_data = [item for item in data if datetime.fromisoformat(item['timestamp']) >= time_ago]
        y = [ int(item['item_count']) for item in filtered_data ]
        x = [ datetime.fromisoformat(item['timestamp']) for item in filtered_data ]
        self.plot_ui_amouts = ui.pyplot(figsize=(8, 4.5))
        with self.plot_ui_amouts:
          plt.bar(x, y, width=0.04)
          plt.xticks(rotation=45)
          plt.title(f'Amount seleld for {potion_id}')
          plt.ylabel('Qtt')
          plt.xlabel('Time UTC')


  def show(self):
    self.potion = next(( item for item in self.potions if item['@uniquename'] == self.potion_input.value), None)
    self.potion_image.source = f"images/{self.potion['@uniquename'] + ( f"@{self.enchant_input.value}" if self.enchant_input.value != 0 else "" )}.png"
    self.potion_image.update()
    self.clear_materials()
    self.add_materials()
    self.price_input_potion.set_value(self.get_current_item_price(self.potion['@uniquename']))

  def craft_price(self):
    crafting_requirements = self.potion['craftingrequirements']
    amount = int(crafting_requirements['@amountcrafted'])
    return_rate_multiplicator = 1 - int(self.return_rate_input.value)/100
    craft_price = 0
    for ressource in self.ressources_inputs:
      count = int(ressource.amount)
      ressource_price = int(ressource.price_input.value)
      craft_price += ressource_price * count if ressource.artifact else ressource_price * count * return_rate_multiplicator
    return round((craft_price + self.craft_fee_potion() ) / amount)

  def craft_fee_potion(self):
    material_amount = sum([ ressource.amount for ressource in self.ressources_inputs if not ressource.artifact])
    return round((self.usage_fee_input.value/1000) * (45 * material_amount))

  def calculate(self):
    self.potion_image_output.source = f"images/{self.potion['@uniquename'] + ( f"@{self.enchant_input.value}" if self.enchant_input.value != 0 else "" )}.png"
    self.potion_label.set_text(self.potion['@uniquename'])
    self.craft_tax_price.set_text(self.craft_fee_potion())
    craft_price = self.craft_price()
    self.potion_craft_cost.set_text(craft_price)
    self.rentability.set_text(round((int(self.price_input_potion.value)*(1-int(self.selling_tax_input.value)/100) / craft_price - 1) * 100))
    self.craft_tax_price.update()
    self.potion_craft_cost.update()
    self.rentability.update()
    self.plot_data()

potions_craft = PotionsCraft()
potions_craft.run()
potions_craft.potion_input.set_value('T5_POTION_MOB_RESET')
potions_craft.calculate()
