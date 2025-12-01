import requests
from bs4 import BeautifulSoup
from data_classes import Ingredient, Step
import re
import spacy
import json
from recipe_state_machine import RecipeStateMachine

WEBSITE_CONFIGS = {
    "allrecipes.com": {
        "ingredient_item": {
            "tag": "li",
            "class": "mm-recipes-structured-ingredients__list-item"
        },
        "ingredient_fields": {
            "quantity": {"tag": "span", "attrs": {"data-ingredient-quantity": "true"}},
            "unit": {"tag": "span", "attrs": {"data-ingredient-unit": "true"}},
            "name": {"tag": "span", "attrs": {"data-ingredient-name": "true"}}
        },
        "instruction_item": {
            "tag": "p",
            "class": "comp mntl-sc-block mntl-sc-block-html"
        }
    },

    "seriouseats.com": {
        "ingredient_item": {
            "tag": "li",
            "class": "structured-ingredients__list-item"
        },
        "ingredient_fields": {
            "quantity": {"tag": "span", "attrs": {"data-ingredient-quantity": "true"}},
            "unit": {"tag": "span", "attrs": {"data-ingredient-unit": "true"}},
            "name": {"tag": "span", "attrs": {"data-ingredient-name": "true"}}
        },
        "instruction_item": {
            "tag": "p",
            "class": "comp mntl-sc-block mntl-sc-block-html"
        }
    },
    "foodnetwork.com": {
    "ingredient_item": {
        "tag": "span",
        "class": "o-Ingredients__a-Ingredient--CheckboxLabel"
    },
    "ingredient_fields": None,
    "instruction_item": {
        "tag": "li",
        "class": "o-Method__m-Step"
    }
}
}

def get_website_config(url):
    """
    Determines which website configuration to use based on the URL.
    
    Args:
        url (str): Recipe URL
    
    Returns:
        dict: Website configuration or None if unsupported
    """
    for site_name, config in WEBSITE_CONFIGS.items():
        if site_name in url:
            return config
    return None

def get_raw_ingredients_instructions(url):
    """
    Parses HTML to return the list of ingredients (strings) and list of instructions (strings)

    Args:
        url (str): URL of the recipe page

    Returns: (ingredients, instructions) - both as lists of strings
    """
    # Get the appropriate configuration for this website
    config = get_website_config(url)
    if config is None:
        raise ValueError(f"Unsupported website. URL: {url}")
    
    # Read url with user-agent header (some sites block requests without it)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Set empty lists
    ingredients = []
    instructions = []

    # Extract ingredients using config
    ingredient_config = config["ingredient_item"]
    ingredient_items = soup.find_all(
        ingredient_config["tag"], 
        class_=ingredient_config["class"]
    )
    
    # If no ingredients found, try alternative selectors
    if len(ingredient_items) == 0:
        # Try without class restriction
        ingredient_items = soup.find_all(ingredient_config["tag"])
    
    for item in ingredient_items:
        # Check if this is Food Network (unstructured ingredient text)
        fields_config = config["ingredient_fields"]
        
        if fields_config is None:
            # Food Network style: single text string
            # e.g., "1 pound (4 sticks) unsalted butter, at room temperature"
            ingredient_text = item.get_text(strip=True)
            if ingredient_text:  # Only add non-empty ingredients
                ingredients.append(ingredient_text)
        else:
            # Structured format (AllRecipes, Serious Eats)
            quantity_span = item.find(
                fields_config["quantity"]["tag"],
                attrs=fields_config["quantity"]["attrs"]
            )
            unit_span = item.find(
                fields_config["unit"]["tag"],
                attrs=fields_config["unit"]["attrs"]
            )
            name_span = item.find(
                fields_config["name"]["tag"],
                attrs=fields_config["name"]["attrs"]
            )
            
            # Get text from each
            quantity = quantity_span.get_text(strip=True) if quantity_span else ""
            unit = unit_span.get_text(strip=True) if unit_span else ""
            name = name_span.get_text(strip=True) if name_span else ""
            
            # Clean the name first
            #name = clean_ingredient_name(name)

            # Build ingredient string: "quantity unit name"
            parts = []
            if quantity:
                parts.append(quantity)
            if unit:
                parts.append(unit)
            if name:
                parts.append(name)
            
            ingredient_str = " ".join(parts)
            
            # Split on "and" to create separate ingredients
            # e.g., "salt and ground black pepper" -> ["salt", "ground black pepper"]
            if ' and ' in name and not quantity:  # Only split if there's no quantity
                ingredient_parts = [part.strip() for part in name.split(' and ')]
                for part in ingredient_parts:
                    if part:  # Only add non-empty parts
                        ingredients.append(part)
            else:
                # Add single ingredient string
                if ingredient_str:
                    ingredients.append(ingredient_str)

    # Extract instructions using config
    instruction_config = config["instruction_item"]
    
    # Special handling for Serious Eats: find instructions within the instructions section
    if "seriouseats.com" in url:
        # Find the instructions section container
        instructions_section = soup.find('section', id=lambda x: x and 'section--instructions' in x)
        
        if instructions_section:
            # Get all paragraphs within this section that match the config
            instruction_items = instructions_section.find_all(
                instruction_config["tag"],
                class_=instruction_config["class"]
            )
        else:
            # Fallback to original method if section not found
            instruction_items = soup.find_all(
                instruction_config["tag"],
                class_=instruction_config["class"]
            )
    
    # Special handling for AllRecipes: find instructions within the mm-recipes-steps container
    elif "allrecipes.com" in url:
        # Find the instructions section container
        instructions_section = soup.find('div', id=lambda x: x and 'mm-recipes-steps' in x)
        
        if instructions_section:
            # Get all paragraphs within this section that match the config
            instruction_items = instructions_section.find_all(
                instruction_config["tag"],
                class_=instruction_config["class"]
            )
        else:
            # Fallback to original method if section not found
            instruction_items = soup.find_all(
                instruction_config["tag"],
                class_=instruction_config["class"]
            )
    
    else:
        # For other sites (including Food Network), use the original method
        instruction_items = soup.find_all(
            instruction_config["tag"],
            class_=instruction_config["class"]
        )
    
    # If no instructions found, try alternative selectors
    if len(instruction_items) == 0:
        # Try common instruction patterns
        if "allrecipes.com" in url:
            # Try alternative AllRecipes selectors
            instruction_items = soup.find_all('li', class_=lambda x: x and 'mntl-sc-block' in str(x))
            if len(instruction_items) == 0:
                instruction_items = soup.find_all('p', class_=lambda x: x and 'mntl-sc-block' in str(x))
        elif "seriouseats.com" in url:
            # Try alternative Serious Eats selectors
            instruction_items = soup.find_all('li', class_=lambda x: x and 'structured-instructions' in str(x))
            if len(instruction_items) == 0:
                instruction_items = soup.find_all('p', class_=lambda x: x and 'comp' in str(x))
    
    for item in instruction_items:
        # Get the text from each instruction paragraph
        instruction_text = item.get_text(strip=True)
        if instruction_text:  # Only add non-empty instructions
            instructions.append(instruction_text)

    return ingredients, instructions


#FOR PROJECT 2 PART 2 ONLY, returns raw original strings for ingredients and instructions
def process_url(url):
    """
    For a given url, gives the fully parsed ingredient and instruction set.

    returns: (ingredients: list of string ingredients, instructions: list of string instructions)
    
    """
    #Get raw ingredients and instructions from url
    ingredients, instructions = get_raw_ingredients_instructions(url)

    # #Atomize instructions into smaller atomic steps
    # instructions = atomize_steps(instructions)

    # #parse instructions into Step classes
    # instructions = parse_instructions(instructions, ingredients)

    # Just return as a simple dict structure - no Gemini needed for this part
    return {
        "ingredients": ingredients,  # List of strings
        "instructions": instructions  # List of strings
    }

def main():
    url1 = "https://www.allrecipes.com/recipe/218091/classic-and-simple-meat-lasagna/"
    url2 = "https://www.allrecipes.com/recipe/228285/teriyaki-salmon/"
    url3 = "https://www.seriouseats.com/pecan-pie-cheesecake-recipe-11843450"
    url4 = "https://www.foodnetwork.com/recipes/pumpkin-pie-in-a-sheet-pan-3415884"

    url = url1 #to test other
    ingredients, instructions = process_url(url)

    fsm = RecipeStateMachine(instructions)
    
    print("Ingredients:")
    for ingredient in ingredients:
        print(f"- {ingredient}")
    
    print("\nInstructions:")
    for step in instructions:
        print(f"- {step}")

if __name__ == "__main__":
    main()