import requests
from bs4 import BeautifulSoup
from data_classes import Ingredient

def parse_html(url):
    """
    Parses HTML to return the list of ingredients (Ingredient class) and list of instructions (str)

    Args:
        url (str): URL of the recipe page

    Returns: (ingredients, instructions)
    """
    # Read the URL
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    #set empty lists
    ingredients = []
    instructions = []

    # Loop through all ingredient list items
    ingredient_items = soup.find_all('li', class_='mm-recipes-structured-ingredients__list-item')
    for item in ingredient_items:
        # Extract individual fields from the spans within each ingredient item
        quantity_span = item.find('span', attrs={'data-ingredient-quantity': 'true'})
        unit_span = item.find('span', attrs={'data-ingredient-unit': 'true'})
        name_span = item.find('span', attrs={'data-ingredient-name': 'true'})
        
        # Get text from each span, or empty string if not found
        quantity = quantity_span.get_text(strip=True) if quantity_span else ""
        unit = unit_span.get_text(strip=True) if unit_span else ""
        name = name_span.get_text(strip=True) if name_span else ""
        
        # Create an Ingredient object and add to list
        ingredient = Ingredient(name=name, quantity=quantity, measurement_unit=unit)
        ingredients.append(ingredient)

    # Loop through all instruction paragraphs (they appear in order in the HTML)
    instruction_items = soup.find_all('p', class_='comp mntl-sc-block mntl-sc-block-html')
    for item in instruction_items:
        # Get the text from each instruction paragraph
        instruction_text = item.get_text(strip=True)
        if instruction_text:  # Only add non-empty instructions
            instructions.append(instruction_text)

    return ingredients, instructions

def main():
    url = "https://www.allrecipes.com/recipe/218091/classic-and-simple-meat-lasagna/"
    ingredients, instructions = parse_html(url)
    
    print("Ingredients:")
    for ingredient in ingredients:
        print(f"- {ingredient.quantity} {ingredient.measurement_unit} {ingredient.name}".strip())
    
    print("\nInstructions:")
    for idx, instruction in enumerate(instructions, 1):
        print(f"{idx}. {instruction}")

if __name__ == "__main__":
    main()