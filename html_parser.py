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
}

#load spacy
nlp = spacy.load("en_core_web_sm")

def clean_ingredient_name(name):
    """
    Cleans ingredient name by removing descriptors and preparation instructions.
    
    Args:
        name (str): Raw ingredient name
    
    Returns:
        str: Cleaned ingredient name
    """
    # common descriptors
    descriptors = [
        'whole wheat', 'whole grain', 'white', 'brown',
        'fresh', 'frozen', 'canned', 'dried', 'dry',
        'lean', 'extra-lean', 'ground',
        'shredded', 'grated', 'sliced', 'diced', 'chopped', 'minced',
        'crushed', 'peeled', 'unpeeled',
        'large', 'small', 'medium',
        'ripe', 'unripe', 'firm',
        'unsalted', 'salted', 'sweetened', 'unsweetened',
        'raw', 'cooked',
        'extra-virgin', 'virgin',
        'low-fat', 'fat-free', 'reduced-fat',
        'boneless', 'skinless'
    ]
    
    #common prep descriptions
    prep_phrases = [
        ', chopped', ', diced', ', minced', ', sliced', ', crushed',
        ', peeled', ', grated', ', shredded',
        ', or to taste', ', to taste', ', optional',
        ', or as needed', ', as needed',
        ', divided', ', plus more for',
        ', softened', ', melted', ', room temperature',
        ', drained', ', rinsed'
    ]
    
    #remove preps
    for phrase in prep_phrases:
        if phrase in name.lower():
            # Find the phrase and remove everything from that point
            idx = name.lower().find(phrase)
            name = name[:idx]
    
    #remove descriptors
    name_lower = name.lower()
    for descriptor in descriptors:
        # Check if name starts with this descriptor
        if name_lower.startswith(descriptor + ' '):
            # Remove the descriptor
            name = name[len(descriptor):].strip()
            name_lower = name.lower()
    
    return name.strip()

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
    Parses HTML to return the list of ingredients (Ingredient class) and list of instructions (str)

    Args:
        url (str): URL of the recipe page

    Returns: (ingredients, instructions)
    """
    # Get the appropriate configuration for this website
    config = get_website_config(url)
    if config is None:
        raise ValueError(f"Unsupported website. URL: {url}")
    
    # Read url
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Set empty lists
    ingredients = []
    instructions = []

    # Extract ingredients using config
    ingredient_config = config["ingredient_item"]
    ingredient_items = soup.find_all(
        ingredient_config["tag"], 
        class_=ingredient_config.get("class")
    )
    
    for item in ingredient_items:
        # Extract individual components using config
        fields_config = config["ingredient_fields"]
        
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
        name = clean_ingredient_name(name)

        # Create Ingredient
        ingredient = Ingredient(name=name, quantity=quantity, measurement_unit=unit)
        ingredients.append(ingredient)

    # Extract instructions using config
    instruction_config = config["instruction_item"]
    instruction_items = soup.find_all(
        instruction_config["tag"],
        class_=instruction_config.get("class")
    )
    
    for item in instruction_items:
        # Get the text from each instruction paragraph
        instruction_text = item.get_text(strip=True)
        if instruction_text:  # Only add non-empty instructions
            instructions.append(instruction_text)

    return ingredients, instructions

def atomize_steps(instructions):
    """
    Takes a list of instruction strings and breaks them into smaller atomic steps.
    Uses spaCy for natural language processing.

    Args:
        instructions (list of str): List of instruction strings
    Returns:
        list of str: List of atomic instruction strings
    """
    import spacy
    
    #conjunctions that separate two steps
    conjunctions = ['and', 'then']
    
    #store final results
    atomic_steps = []
    
    # Process each instruction paragraph
    for instruction in instructions:
        #label each entity with spacy
        doc = nlp(instruction)
        
        #split into sentences
        sentences = list(doc.sents)
        
        #for each sentence
        for sentence in sentences:
            # Find all verbs in this sentence
            verbs = [token for token in sentence if token.pos_ == "VERB"]
            
            # If there's only one verb or no verbs, keep the sentence as is
            if len(verbs) <= 1:
                atomic_steps.append(sentence.text.strip())
                continue
            
            #Multiple verbs - check if they're coordinated from conjunction list
            split_occurred = False
            
            #Look for conjunctions between verbs
            for token in sentence:
                # Check if conjunction
                if token.text.lower() in conjunctions:
                    # Check if there are verbs on both sides of this coordinator
                    verbs_before = [t for t in sentence if t.pos_ == "VERB" and t.i < token.i]
                    verbs_after = [t for t in sentence if t.pos_ == "VERB" and t.i > token.i]
                    
                    #split logic
                    if verbs_before and verbs_after:             
                        # Get the text before the coordinator
                        left_tokens = [t for t in sentence if t.i < token.i]
                        left_text = " ".join([t.text for t in left_tokens]).strip()
                        
                        # Get the text after the coordinator
                        right_tokens = [t for t in sentence if t.i > token.i]
                        right_text = " ".join([t.text for t in right_tokens]).strip()
                        
                        # Clean up punctuation at the end of left_text
                        if left_text.endswith(',') or left_text.endswith(';'):
                            left_text = left_text[:-1].strip()
                        
                        # Add both parts as atomic steps
                        atomic_steps.append(left_text)
                        atomic_steps.append(right_text)
                        
                        split_occurred = True
                        break  # Only split once per sentence
            
            # If no split occurred, keep the original sentence
            if not split_occurred:
                atomic_steps.append(sentence.text.strip())
    
    return atomic_steps

def get_ingredients_from_instruction(doc, ingredients):
    """
    Extracts ingredient names that appear in the instruction text.
    
    Args:
        doc: spaCy Doc object of the instruction text
        ingredients: list of Ingredient objects from the recipe
    
    Returns:
        list of str: ingredient names found in this instruction
    """
    instruction_text = doc.text.lower()
    found_ingredients = []
    
    for ingredient in ingredients:
        ingredient_name = ingredient.name.lower()
        
        #check if ingredient name present in text
        if ingredient_name in instruction_text:
            found_ingredients.append(ingredient.name)
    
    return found_ingredients

def get_tools_from_instruction(doc):
    """
    Extracts cooking tools and equipment mentioned in the instruction.
    
    Args:
        doc: spaCy Doc object of the instruction text
    
    Returns:
        list of str: tools found in this instruction
    """
    instruction_text = doc.text.lower()
    
    #Hardcoded list of common cooking tools
    tools_list = [
        #cookware
        "pan", "skillet", "frying pan", "saucepan", "pot", "dutch oven",
        "wok", "griddle", "roasting pan", "baking dish", "casserole dish",
        
        #baking appliances
        "baking sheet", "cookie sheet", "baking pan", "muffin tin",
        "cake pan", "loaf pan", "pie dish", "tart pan", "springform pan",
        
        #appliances
        "oven", "stove", "stovetop", "microwave", "toaster", "toaster oven",
        "slow cooker", "crockpot", "pressure cooker", "instant pot",
        "air fryer", "blender", "food processor", "mixer", "stand mixer",
        "hand mixer",
        
        #utensils
        "spoon", "wooden spoon", "spatula", "whisk", "ladle", "tongs",
        "fork", "knife", "peeler", "grater", "zester", "masher",
        "rolling pin", "can opener", "strainer", "colander", "sieve",
        
        #measurement instr
        "measuring cup", "measuring spoon", "scale", "thermometer",
        
        #bowls and containers
        "bowl", "mixing bowl", "container", "plate", "platter",
        
        #misc.
        "cutting board", "parchment paper", "aluminum foil", "plastic wrap",
        "kitchen towel", "oven mitts", "timer"
    ]
    
    found_tools = []
    
    # Sort tools by length (longest first) to match multi-word tools before single words
    # e.g., match "baking sheet" before "sheet"
    sorted_tools = sorted(tools_list, key=len, reverse=True)
    
    for tool in sorted_tools:
        if tool in instruction_text:
            # Avoid duplicates
            if tool not in found_tools:
                found_tools.append(tool)
    
    return found_tools

def get_methods_from_instruction(doc):
    """
    Extracts cooking methods (actions/verbs) from the instruction.
    
    Args:
        doc: spaCy Doc object of the instruction text
    
    Returns:
        list of str: cooking methods found in this instruction
    """
    #hardcoded list of methods
    cooking_methods = [
        #heat based
        "bake", "roast", "broil", "grill", "toast", "sear",
        "boil", "simmer", "poach", "steam", "blanch", "parboil",
        "fry", "deep-fry", "pan-fry", "saute", "sautee", "stir-fry",
        "braise", "stew", "microwave", "smoke", "char", "caramelize", "reduce",
        
        #cut
        "chop", "dice", "mince", "slice", "julienne", "cube", "cut",
        
        #mix
        "mix", "stir", "whisk", "beat", "fold", "combine", "blend", "toss", "cream",
        
        #prep
        "peel", "core", "pit", "seed", "skin", "trim", "debone",
        "marinate", "season", "coat", "dredge", "bread", "bring", "lay", "repeat",
        
        #modifications
        "mash", "puree", "grind", "crush", "grate", "shred", "zest",
        
        #liquid
        "drain", "strain", "squeeze", "press",
        
        #assembly
        "arrange", "layer", "spread", "pour", "place", "transfer",
        "stuff", "roll", "wrap", "top",
        
        #temp. control
        "heat", "warm", "cool", "chill", "freeze", "thaw", "preheat",
        
        #application
        "sprinkle", "drizzle", "brush", "baste", "glaze", "garnish",
        
        #general/misc.
        "cook", "prepare", "serve", "rest", "cover", "uncover",
        "flip", "turn", "remove", "add", "set"
    ]
    
    found_methods = []
    instruction = doc.text.lower()

    # Method 1: Use spaCy POS tagging to find verbs
    for token in doc:
        if token.pos_ == "VERB":
            verb_lemma = token.lemma_.lower()
            if verb_lemma in cooking_methods:
                if verb_lemma not in found_methods:
                    found_methods.append(verb_lemma)
    
    # Method 2: Direct text matching as fallback
    # This catches cases where spaCy mistagged the verb
    for method in cooking_methods:
        # Create word boundary pattern to avoid partial matches
        # e.g., don't match "bake" in "baker"
        pattern = r'\b' + re.escape(method) + r'\b'
        if re.search(pattern, instruction):
            if method not in found_methods:
                found_methods.append(method)
    
    return found_methods

def get_time_from_instruction(doc):
    """
    Extracts time duration from the instruction.
    
    Args:
        doc: spaCy Doc object of the instruction text
    
    Returns:
        dict: {"duration": str} or empty dict if no time found
    """
    instruction_text = doc.text
    
    #pattern 1: Number + time unit (e.g., "30 minutes", "2 hours")
    #matches: "30 minutes", "1 hour", "2.5 hours", "1-2 minutes"
    pattern1 = r'\b(\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?)\s*(hour|hours|minute|minutes|second|seconds|min|mins|hr|hrs|sec|secs)\b'
    
    #pattern 2: Approximate time (e.g., "about 30 minutes", "approximately 2 hours")
    pattern2 = r'\b(about|approximately|around)\s+(\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?)\s*(hour|hours|minute|minutes|second|seconds|min|mins|hr|hrs|sec|secs)\b'
    
    #try pattern 2 first (with "about/approximately")
    match = re.search(pattern2, instruction_text, re.IGNORECASE)
    if match:
        qualifier = match.group(1)  #"about", "approximately", etc.
        number = match.group(2)
        unit = match.group(3)
        return {"duration": f"{qualifier} {number} {unit}"}
    
    #try pattern 1 (simple duration)
    match = re.search(pattern1, instruction_text, re.IGNORECASE)
    if match:
        number = match.group(1)
        unit = match.group(2)
        return {"duration": f"{number} {unit}"}

    #no time found
    return {}

def get_temperature_from_instruction(doc):
    """
    Extracts temperature from the instruction.
    
    Args:
        doc: spaCy Doc object of the instruction text
    
    Returns:
        str: temperature string or empty string if no temperature found
        Examples: "350°F", "medium heat", ""
    """
    instruction_text = doc.text
    
    #pattern 1: Numeric temperature (e.g., "350°F", "175 degrees C", "180C")
    #matches: "350°F", "350 °F", "350 degrees F", "175°C", "180C"
    pattern_numeric = r'\b(\d+)\s*(?:°|degrees?)?\s*([FCfc])\b'
    
    #pattern 2: Heat level (e.g., "medium heat", "high heat", "medium-high heat")
    #matches: "low heat", "medium heat", "high heat", "medium-low", etc.
    pattern_heat = r'\b(low|medium-low|medium|medium-high|high)(?:\s+heat)?\b'
    
    #try to find numeric temperature first
    match = re.search(pattern_numeric, instruction_text, re.IGNORECASE)
    if match:
        number = match.group(1)
        unit = match.group(2).upper()  # Convert to uppercase (F or C)
        return f"{number}°{unit}"
    
    #try to find heat level
    match = re.search(pattern_heat, instruction_text, re.IGNORECASE)
    if match:
        heat_level = match.group(1)
        return f"{heat_level} heat"
    
    #no temp
    return ""

def parse_instructions(instructions, ingredients):
    """
    Parses a list of instruction strings into Step classes
    """
    #store results here
    steps = []

    for i, instruction in enumerate(instructions):

        doc = nlp(instruction)

        #extract individual components
        ingredients_extracted = get_ingredients_from_instruction(doc, ingredients)
        tools_extracted = get_tools_from_instruction(doc)
        methods_extracted = get_methods_from_instruction(doc)
        time_extracted = get_time_from_instruction(doc)
        temp_extracted = get_temperature_from_instruction(doc)

        #create a Step obj
        step = Step(
            step_number=i + 1,
            description=instruction,
            ingredients=ingredients_extracted,  # Placeholder, can be filled with actual ingredient parsing logic
            tools=tools_extracted,        # Placeholder
            methods=methods_extracted,      # Placeholder
            time=time_extracted,         # Placeholder
            temperature=temp_extracted   # Placeholder
        )
        steps.append(step)

    return steps

def process_url(url):
    """
    For a given url, gives the fully parsed ingredient and instruction set.

    returns: (ingredients: list of Ingredient classes, instructions: list of Step classes, see doc in data_classes.py)
    
    """
    #Get raw ingredients and instructions from url
    ingredients, instructions = get_raw_ingredients_instructions(url)

    #Atomize instructions into smaller atomic steps
    instructions = atomize_steps(instructions)

    #parse instructions into Step classes
    instructions = parse_instructions(instructions, ingredients)


    return ingredients, instructions

def main():
    allrecipes_url = "https://www.allrecipes.com/recipe/218091/classic-and-simple-meat-lasagna/"
    seriouseats_url = "https://www.seriouseats.com/pecan-pie-cheesecake-recipe-11843450"

    url = allrecipes_url #for testing
    ingredients, instructions = process_url(url)

    fsm = RecipeStateMachine(instructions)
    
    print("Ingredients:")
    for ingredient in ingredients:
        print(f"Name: {ingredient.name}")
        print(f"  Quantity: {ingredient.quantity if ingredient.quantity else 'N/A'}")
        print(f"  Unit: {ingredient.measurement_unit if ingredient.measurement_unit else 'N/A'}")
        print()
    
    print("\nInstructions:")
    for step in instructions:
        print(f"\nStep {step.step_number}: {step.description}")
        print(f"  Ingredients: {step.ingredients if step.ingredients else 'None'}")
        print(f"  Tools: {step.tools if step.tools else 'None'}")
        print(f"  Methods: {step.methods if step.methods else 'None'}")
        print(f"  Time: {step.time.get('duration', 'None') if step.time else 'None'}")
        print(f"  Temperature: {step.temperature if step.temperature else 'None'}")

    # Convert to JSON-serializable format
    recipe_data = {
        "url": url,
        "ingredients": [
            {
                "name": ing.name,
                "quantity": ing.quantity,
                "measurement_unit": ing.measurement_unit
            }
            for ing in ingredients
        ],
        "steps": [
            {
                "step_number": step.step_number,
                "description": step.description,
                "ingredients": step.ingredients,
                "tools": step.tools,
                "methods": step.methods,
                "time": step.time,
                "temperature": step.temperature
            }
            for step in instructions
        ]
    }

    # Write to JSON file
    output_file = "recipe_output.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(recipe_data, f, indent=2, ensure_ascii=False)
    
    print(f"Recipe data saved to: {output_file}")
    
if __name__ == "__main__":
    main()