"""
Conversational interface for recipe parsing and querying.
This is a stateless, rule-based interface that answers questions about recipes.
"""

import re
from html_parser import process_url
from data_classes import Ingredient, Step
from recipe_state_machine import RecipeStateMachine


def show_ingredients(ingredients):
    """Display all ingredients in a readable format."""
    print("\nHere are the ingredients:")
    for ingredient in ingredients:
        # Format: quantity + unit + name
        parts = []
        if ingredient.quantity:
            parts.append(ingredient.quantity)
        if ingredient.measurement_unit:
            parts.append(ingredient.measurement_unit)
        if ingredient.name:
            parts.append(ingredient.name)
        
        ingredient_str = " ".join(parts) if parts else ingredient.name
        print(f"- {ingredient_str}")


def show_all_steps(steps):
    """Display all steps with step numbers."""
    print("\nHere are all the steps:")
    for step in steps:
        print(f"Step {step.step_number}: {step.description}")


def show_current_step(fsm):
    """Display a specific step by number."""
    step = fsm.get_current_step()
    print(f"\nStep {step.step_number}: {step.description}")
    return(None)


def is_next_step_query(query):
    """See if user wants to jump 1 step ahead."""

    patterns = [
        r'next step',
        r'next',
        #only single letter n
        r'\bn\b',
        r'advance',
        r'continue',
        r'what\'s next',
    ]

    query = query.lower().strip()
    for pattern in patterns:
        if re.search(pattern, query):
            return(True)

    return(False)

def is_go_back_a_step_query(query):
    """See if user wants to go back a step."""

    patterns = [
        r'last step',
        r'go back a step',
        #only single letter b
        r'\bb\b'
        r'go back',
        r'go back one step'
    ]

    query = query.lower().strip()
    for pattern in patterns:
        if re.search(pattern, query):
            return(True)
    return(False)

def is_begin_recipe_query(query):
    """See if user wants to start following the recipe step-by-step."""

    patterns = [
        r'\bstart recipe\b',
        r'start cooking',
        r'begin recipe',
        r'start the recipe',
        r'start',
        r'walkthrough'
    ]

    query = query.lower().strip()
    for pattern in patterns:
        if re.search(pattern, query):
            return(True)
    return(False)

def is_repeat_query(query):
    """Detect if the user wants the current step repeated."""
    patterns = [
        r'\brepeat\b',
        r'\brepeat that\b',
        r'\brepeat step\b',
        r'\bsay that again\b',
        r'\bwhat was that\b',
        r'\bagain\b$'
    ]
    
    q = query.lower().strip()
    for p in patterns:
        if re.search(p, q):
            return True
    return False



def extract_ingredient_from_how_much(query):
    """
    Extract ingredient name from "how much X do i need?" queries.
    
    Args:
        query: Lowercase user query
    
    Returns:
        str: Extracted ingredient name, or None if not found
    """

    # Pattern: "how much " followed by ingredient, then optional trailing phrases
    # Handle: "how much X do i need", "how much X is needed", "how much X do we need"
    pattern = r'how much (.+?)(?:\s+(?:do (?:i|we)|is|are)\s+(?:need|needed))?[?.]?$'
    match = re.search(pattern, query)
    
    if match:
        ingredient = match.group(1).strip()
        # Remove trailing phrases that might have been captured
        ingredient = re.sub(r'\s+(?:do (?:i|we)|is|are)\s+(?:need|needed)', '', ingredient)
        # Remove trailing punctuation
        ingredient = ingredient.rstrip('?.,!')
        return ingredient if ingredient else None
    
    return None


def find_ingredient_by_name(ingredients, search_name):
    """
    Find an ingredient by name using case-insensitive substring matching.
    
    Args:
        ingredients: List of Ingredient objects
        search_name: Name to search for (lowercase)
    
    Returns:
        Ingredient object if found, None otherwise
    """
    search_name = search_name.lower().strip()
    
    for ingredient in ingredients:
        ingredient_name_lower = ingredient.name.lower()
        # Check if search_name is a substring of ingredient name
        if search_name in ingredient_name_lower or ingredient_name_lower in search_name:
            return ingredient
    
    return None

def handle_substitution_query(query):
    """Handle ingredient substitution questions."""

    q = query.lower().strip()

    patterns = [
        r'substitute for (.+)',
        r'what can i use instead of (.+)',
        r'what can i substitute for (.+)'
        ]

    for p in patterns:
        match = re.search(p, q)
        if match:
            ingredient = match.groups()[-1].strip(" ?.!")

            #if no ingredient found
            if not ingredient:
                print("ingredient not found, sorry!")
                return True

            #link for substitutions
            encoded = ingredient.replace(" ", "+")
            url = f"https://www.google.com/search?q={encoded}+cooking+substitute"

            print(f"\nHere are some substitution options for '{ingredient}':")
            print(url)
            return(True)

    return(False)

def handle_cooking_time_or_temp_query(query):
    """Handle cooking time or temperature questions."""

    pass #todo


def handle_how_much_question(ingredients, query, fsm):
    """
    Handle "how much <ingredient> do i need?" questions.
    
    Args:
        ingredients: List of Ingredient objects
        query: User query (lowercase)
    
    Returns:
        bool: True if handled, False otherwise
    """

    #how much? or how many? or how much of that? or how many of that? 
    # or how much of those? or how many of those? (vague)
    vague_pattern = (
    r'^(how (much|many))'
    r'(?:\s+of\s+(that|this|it|those|these))?'
    r'(?:\s+(do i need|is needed|are needed))?'
    r'\s*\??$'
    )
    
    if re.search(vague_pattern, query.strip()):
        step = fsm.get_current_step()
        if hasattr(step, "ingredients") and step.ingredients:
            for name in step.ingredients:
                ingredient = find_ingredient_by_name(ingredients, name)
                if ingredient:
                    parts = []
                    if ingredient.quantity:
                        parts.append(ingredient.quantity)
                    if ingredient.measurement_unit:
                        parts.append(ingredient.measurement_unit)
                    parts.append(f"of {ingredient.name}")
                    response = " ".join(parts)
                else:
                    response = f"some {name}"
                print(f"\nYou need {response}.")
            return(True)
        print(f"\nI couldn't find any ingredients in this recipe step.")
        return(True)
    
    #otherwise, non-vague
    # Extract ingredient name
    ingredient_name = extract_ingredient_from_how_much(query)
    
    if not ingredient_name:
        return False
    
    # Find matching ingredient
    ingredient = find_ingredient_by_name(ingredients, ingredient_name)
    
    if ingredient:
        # Format response
        parts = []
        if ingredient.quantity:
            parts.append(ingredient.quantity)
        if ingredient.measurement_unit:
            parts.append(ingredient.measurement_unit)
        if ingredient.name:
            parts.append(f"of {ingredient.name}")
        
        response = " ".join(parts) if parts else f"some {ingredient.name}"
        print(f"\nYou need {response}.")
    else:
        print(f"\nI couldn't find that ingredient in this recipe.")
    
    return True


def handle_what_is_question(query, fsm):
    """
    Handle "what is X?" questions by returning a Google search URL.
    
    Args:
        query: User query (lowercase)
    
    Returns:
        bool: True if handled, False otherwise
    """
    #what's that/what is that?
    if re.search(r"what(?:'s| is) that\??$", query):
        step = fsm.get_current_step()
        if hasattr(step, "ingredients") and step.ingredients:
            for ingredient in step.ingredients:
                name = str(ingredient)
                search_query = name.replace(" ", "+")
                url = f"https://www.google.com/search?q={search_query}"
                print(f"\nI found a reference for you: {url}")
            return(True)
                

    #less vague
    # Pattern: "what is " or "what's " followed by the term
    pattern = r"what(?:'s| is) (.+?)[?.]?$"
    match = re.search(pattern, query)
    
    if not match:
        return False
    
    search_term = match.group(1).strip()
    # Remove trailing punctuation
    search_term = search_term.rstrip('?.,!')
    
    # Create Google search URL
    query_encoded = search_term.replace(" ", "+")
    url = f"https://www.google.com/search?q={query_encoded}"
    
    print(f"\nI found a reference for you: {url}")
    return True


def handle_how_do_i_question(query, fsm):
    """
    Handle "how do I X?" questions by returning a YouTube search URL.
    
    Args:
        query: User query (lowercase)
    
    Returns:
        bool: True if handled, False otherwise
    """
    # Check for vague references
    if re.search(r'^(how\??|how do i do (that|this|it)\??)$', query.strip()):
        step = fsm.get_current_step()
        if hasattr(step, "methods") and step.methods:
            methods = step.methods
            for method in methods:
                search_query = f"how to {method}".replace(" ", "+")
                url = f"https://www.youtube.com/results?search_query={search_query}"
                print(f"\nHere's a video search that might help: {url}")
            return(True)
        print(f"\nI couldn't find any methods in this recipe step.")
    
    #non-vague
    # Pattern: "how do i " or "how do you " followed by the action
    pattern = r'how do (?:i|you) (.+?)[?.]?$'
    match = re.search(pattern, query)
    
    if not match:
        return False
    
    action = match.group(1).strip()
    # Remove trailing punctuation
    action = action.rstrip('?.,!')
    
    # Create YouTube search URL
    search_query = f"how to {action}".replace(" ", "+")
    url = f"https://www.youtube.com/results?search_query={search_query}"
    
    print(f"\nHere's a video search that might help: {url}")
    return True


def extract_step_number(query):
    """
    Extract step number from queries like "show step 3" or "step 2".
    
    Args:
        query: User query (lowercase)
    
    Returns:
        int: Step number if found, None otherwise
    """
    # Pattern: "step" followed by a number
    pattern = r'step\s+(\d+)'
    match = re.search(pattern, query)
    
    if match:
        return int(match.group(1))
    
    return None


def is_ingredients_query(query):
    """Check if query is asking to show ingredients."""
    patterns = [
        r'show\s+ingredients',
        r'list\s+ingredients',
        r'show\s+me\s+the\s+ingredients',
        r'ingredients',
    ]
    
    for pattern in patterns:
        if re.search(pattern, query):
            return True
    
    return False


def is_recipe_query(query):
    """Check if query is asking to show the full recipe."""
    patterns = [
        r'show\s+recipe',
        r'show\s+all\s+steps',
        r'display\s+the\s+recipe',
        r'full\s+recipe',
    ]
    
    for pattern in patterns:
        if re.search(pattern, query):
            return True
    
    return False


def is_exit_query(query):
    """Check if query is asking to exit."""
    exit_commands = ['quit', 'exit', 'q']
    return query.strip().lower() in exit_commands


def process_user_query(ingredients, steps, fsm, query):
    """
    Process a user query and return appropriate response.
    
    Args:
        ingredients: List of Ingredient objects
        steps: List of Step objects
        query: User query string
    
    Returns:
        bool: True if should continue, False if should exit
    """
    query_lower = query.lower().strip()
    
    # Check for exit
    if is_exit_query(query_lower):
        print("\nGoodbye!")
        return False
    
    # Check for ingredients list
    if is_ingredients_query(query_lower):
        show_ingredients(ingredients)
        return True
    
    # Check for full recipe
    if is_recipe_query(query_lower):
        show_all_steps(steps)
        return True
    
    if is_begin_recipe_query(query_lower):
        fsm.jump_to_step(1)
        show_current_step(fsm)
        print("Type 'next' or 'n' for the next step, or ask a question.")
        return(True)
    
    if is_next_step_query(query_lower):
        fsm.move_steps_forward(1)
        show_current_step(fsm)
        print("Type 'next' or 'n' for the next step, or ask a question.")
        return(True)

    if is_go_back_a_step_query(query_lower):
        fsm.move_steps_forward(-1)
        show_current_step(fsm)
        print("Type 'next' or 'n' for the next step, or ask a question.")
        return(True)
    
    #check for specific step number
    step_num = extract_step_number(query_lower)
    if step_num:
        fsm.jump_to_step(step_num)
        show_current_step(fsm)
        return(True)
    
    if is_repeat_query(query_lower):
        show_current_step(fsm)
        return(True)
    
    if handle_cooking_time_or_temp_query(query_lower):
        return(True)
    
    if handle_substitution_query(query_lower):
        return(True)
    
    # Check for "how much" questions
    if query_lower.startswith("how much"):
        if handle_how_much_question(ingredients, query_lower, fsm):
            return True
    
    # Check for "what is" questions
    if query_lower.startswith("what is"):
        if handle_what_is_question(query_lower, fsm):
            return True
    
    # Check for "how" questions (that are not "how much")
    if query_lower.startswith("how"):
        if handle_how_do_i_question(query_lower, fsm):
            return True

    # Fallback: help message
    print("\nSorry, I didn't understand that.")
    print("\nI can:")
    print("- show ingredients")
    print("- show the full recipe")
    print("- start recipe walkthrough (start)")
    print("- show step <number>")
    print("- answer \"how much <ingredient> do I need?\"")
    print("- answer \"what is X?\" and \"how do I X?\" with helpful links.")

    return True


def main():
    """Main function to run the conversational interface."""
    print("Welcome to the Recipe Assistant!")
    print("=" * 50)
    
    # Ask for recipe URL
    url = input("\nPlease enter a recipe URL: ").strip()
    
    if not url:
        print("No URL provided. Exiting.")
        return
    
    # Parse the recipe
    print("\nParsing recipe...")
    try:
        ingredients, steps = process_url(url)
        print(f"Successfully parsed recipe with {len(ingredients)} ingredients and {len(steps)} steps!")
    except Exception as e:
        print(f"Error parsing recipe: {e}")
        return
    
    fsm = RecipeStateMachine(steps)
    
    # Enter conversation loop
    print("\n" + "=" * 50)
    print("You can now ask questions about the recipe.")
    print("Type 'quit', 'exit', or 'q' to exit.")
    print("=" * 50)
    
    while True:
        query = input("\nYour question: ").strip()
        
        if not query:
            continue
        
        should_continue = process_user_query(ingredients, steps, fsm, query)
        
        if not should_continue:
            break


if __name__ == "__main__":
    main()

