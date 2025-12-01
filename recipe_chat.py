import re
from html_parser import process_url
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv
from recipe_state_machine import RecipeStateMachine

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash-lite"

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

def create_chat_session(recipe_data):
    """
    Create a new Gemini chat session with recipe context.
    
    Args:
        recipe_data: Dict with 'ingredients' and 'instructions' keys
    
    Returns:
        chat session object
    """
    # Configure Gemini API
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    
# Create initial system-like message with recipe context
    initial_prompt = f"""
You are a helpful cooking assistant with conversation memory. You can help users navigate through a recipe step-by-step.

FULL RECIPE DATA:
{json.dumps(recipe_data, indent=2)}

INSTRUCTIONS FOR YOU:
CRITICAL FIRST STEP: Before anything else, you MUST atomize the instructions. Break down each instruction into smaller, atomic steps. Each atomic step should be a single action. For example:
- "Preheat oven to 350°F, then mix flour and eggs" → becomes Step 1: "Preheat oven to 350°F" and Step 2: "Mix flour and eggs"
- Look for conjunctions like "then", "and then", "while", etc. and split on those
- Each step should be one clear action

After atomizing, you will use ONLY these atomized steps for the entire conversation. Renumber them starting from 1.

Then follow these rules:
- Track which step the user is currently on based on our conversation
- If they say "start", "begin", or "start recipe", begin at step 1 of the ATOMIZED steps
- If they say "next" or "n", move to the next atomized step
- If they say "back", "b", or "previous", go to the previous atomized step
- If they say "repeat" or "again", repeat the current atomized step
- If they ask "step X", jump to that step number in the atomized steps
- When presenting a step, format it clearly: "Step X: [instruction text]"
- After showing a step, remind them they can say 'next', 'back', or ask questions
- If they ask contextual questions like "how much of that?", "what temperature?", "how long?", refer to the current step based on our conversation
- If asking about ingredients without context, provide exact quantities from the recipe
- If the answer isn't in the recipe, say so politely and provide general cooking advice if appropriate
- Keep track of where they are in the recipe throughout our conversation

You should maintain context and remember which step the user is on as we talk.

First, atomize the steps internally, then respond with: "Ready! I've loaded and processed the recipe into [NUMBER] steps. You can ask me questions, or say 'start' to begin the step-by-step walkthrough."
"""
    
    # Start chat session
    chat = model.start_chat(history=[])
    
    # Send initial context
    response = chat.send_message(initial_prompt)
    
    return chat


def query_gemini_chat(chat, query):
    """
    Send a user query through the chat session.
    
    Args:
        chat: Active chat session
        query: User's current question
    
    Returns:
        str: Gemini's response
    """
    try:
        response = chat.send_message(query)
        return response.text
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"


def process_user_query(chat, query, fsm):
    """
    Process a user query and return appropriate response.
    
    Args:
        chat: Active chat session
        query: User query string
    
    Returns:
        bool: True if should continue, False if should exit
    """
    query_lower = query.lower().strip()
    
    # Check for exit
    if query_lower in ['quit', 'exit', 'q']:
        print("\nGoodbye!")
        return False
    
    # FSM navigation
    if query_lower in ['start', 'begin', 'start recipe']:
        print(f"\nStep 1: {fsm.jump_to_step(1)}")
        return True
    elif query_lower in ['next', 'n']:
        print(f"\n{fsm.next_step()}")
        return True
    elif query_lower in ['back', 'b', 'previous']:
        print(f"\n{fsm.previous_step()}")
        return True
    elif query_lower in ['repeat', 'again']:
        print(f"\n{fsm.get_current_step()}")
        return True
    elif re.match(r'step \d+', query_lower):
        step_num = int(re.findall(r'\d+', query_lower)[0])
        print(f"\n{fsm.jump_to_step(step_num)}")
        return True

    # "How do I ..." questions
    if handle_how_do_i_question(query_lower, fsm):
        return True
    
    # Send to Gemini chat
    print("\nThinking...")
    fsm_context = fsm_context_for_prompt(fsm)
    full_query = f"FSM context:\n{fsm_context}\nUser question: {query}"
    response = query_gemini_chat(chat, full_query)

    #full prompt chat gets (4 debugging)
    #print(full_query)

    print(f"\n{response}")
    
    return(True)

def fsm_context_for_prompt(fsm):
    """
    create a string summarizing the FSM state for inclusion in the AI prompt.
    """
    current_step_number, current_step_text = fsm.visited_states[-1] if fsm.visited_states else (fsm.current_step_index + 1, fsm.steps[fsm.current_step_index])
    
    context = f"Current step: Step {current_step_number}: {current_step_text}\n"
    
    if fsm.visited_states:
        visited_formatted = [f"Step {num}: {text}" for num, text in fsm.visited_states]
        context += f"Previously visited steps ({len(visited_formatted)}): {visited_formatted}\n"
    else:
        context += "No previously visited steps.\n"
    
    return context


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
        recipe_data = process_url(url) #for ai
        steps = recipe_data["instructions"] # for fsm
        print(f"Successfully parsed recipe with {len(recipe_data['ingredients'])} ingredients and {len(recipe_data['instructions'])} steps!")
    except Exception as e:
        print(f"Error parsing recipe: {e}")
        return
    
    # Create chat session with recipe context
    print("\nInitializing AI assistant...")
    chat = create_chat_session(recipe_data)

    fsm = RecipeStateMachine(steps)
    
    # Enter conversation loop
    print("\n" + "=" * 50)
    print("You can now ask questions about the recipe.")
    print("Try: 'start' to begin walkthrough, 'next', 'back', 'repeat', or ask any question!")
    print("Type 'quit', 'exit', or 'q' to exit.")
    print("=" * 50)
    
    while True:
        query = input("\nYour question: ").strip()
        
        if not query:
            continue
        
        should_continue = process_user_query(chat, query, fsm)
        
        if not should_continue:
            break


if __name__ == "__main__":
    main()