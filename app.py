from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from html_parser import process_url
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv
import re
from recipe_state_machine import RecipeStateMachine

load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash-lite"

def handle_how_do_i_question(query, fsm):
    """Handle "how do I X?" questions by returning a YouTube search URL."""
    if re.search(r'^(how\??|how do i do (that|this|it)\??)$', query.strip()):
        step = fsm.get_current_step()
        if hasattr(step, "methods") and step.methods:
            urls = []
            for method in step.methods:
                search_query = f"how to {method}".replace(" ", "+")
                url = f"https://www.youtube.com/results?search_query={search_query}"
                urls.append(f"Here's a video search that might help: {url}")
            return "\n".join(urls)
        return "I couldn't find any methods in this recipe step."
    
    pattern = r'how do (?:i|you) (.+?)[?.]?$'
    match = re.search(pattern, query)
    
    if not match:
        return None
    
    action = match.group(1).strip()
    action = action.rstrip('?.,!')
    
    search_query = f"how to {action}".replace(" ", "+")
    url = f"https://www.youtube.com/results?search_query={search_query}"
    
    return f"Here's a video search that might help: {url}"

# Global state to store parsed recipe data
recipe_data = {
    'recipe': None,
    'url': None
}

# Store chat sessions per session (simplified - in production use proper sessions)
chat_sessions = {}
#fsms too
fsms = {}


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
- Remember which step the user is currently on based on our conversation

IMPORTANT NOTE ABOUT STEPS:
- A 
finite state machine (FSM) controls which step the user is on.
- you DO NOT track the user's step.
- you DO NOT move forward or backward.
- you DO NOT interpret commands like “next,” “back,” “start,” or “step 3.”
- The FSM will provide you the current step as:
    “Current step: Step X: <text>”
- ALWAYS use the step provided in the FSM context.
- the FSM will also provide any history of steps visited. If the user asks about 
step visiting history, please spit that history back VERBATIM.

- If they ask contextual questions like "how much of that?", "what temperature?", "how long?", refer to the current step based on the FSM
- If asking about ingredients without context, provide exact quantities from the recipe
- If the answer isn't in the recipe, say so politely and provide general cooking advice if appropriate

You should maintain context and remember which step the user is on as we talk, keeping in mind the FSM state and history
you MUST NOT:
- Track or store the current step.
- Assume the next or previous step.
- Navigate the recipe.
- Reply with “moving to step…” or similar.
- Renumber or regenerate steps after your initial atomization. 

First, atomize the steps internally, then respond with: "Ready! I've loaded and processed the recipe into [NUMBER] steps. You can ask me questions, or say 'start' to begin the step-by-step walkthrough."
"""

    # Start chat session
    chat = model.start_chat(history=[])
    
    # Send initial context
    response = chat.send_message(initial_prompt)
    
    return chat

def fsm_context_for_prompt(fsm):
    """
    Create a string summarizing the FSM state for inclusion in the AI prompt.
    """
    # Always take current step from FSM index
    current_step_number = fsm.current_step_index + 1
    current_step_text = fsm.steps[fsm.current_step_index]
    
    context = f"Current step: Step {current_step_number}: {current_step_text}\n"
    
    if fsm.visited_states:
        visited_formatted = [f"Step {num}: {text}" for num, text in fsm.visited_states]
        context += f"Previously visited steps ({len(visited_formatted)}): {visited_formatted}\n"
    else:
        context += "No previously visited steps.\n"
    
    return context

@app.route('/api/parse', methods=['POST'])
def parse_recipe():
    """Parse a recipe URL and store the results."""
    global recipe_data
    
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON data'}), 400
    
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        parsed_recipe = process_url(url)
        
        recipe_data['recipe'] = parsed_recipe
        recipe_data['url'] = url
        
        return jsonify({
            'success': True,
            'message': f'Successfully parsed recipe with {len(parsed_recipe["ingredients"])} ingredients and {len(parsed_recipe["instructions"])} steps!',
            'ingredients_count': len(parsed_recipe['ingredients']),
            'steps_count': len(parsed_recipe['instructions'])
        })
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"DEBUG: Error parsing recipe: {str(e)}")
        print(f"DEBUG: Traceback: {error_trace}")
        return jsonify({'error': f'Error parsing recipe: {str(e)}'}), 500


@app.route('/api/query', methods=['POST'])
def query_recipe():
    """Process a query about the recipe."""
    global recipe_data, chat_sessions, fsms
    
    if not recipe_data['recipe']:
        return jsonify({'error': 'No recipe loaded. Please parse a recipe first.'}), 400
    
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON data'}), 400
    
    query = data.get('query')
    session_id = data.get('session_id', 'default')  # Use session_id to track different users
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    # Get or create fsm session for this session
    if session_id not in fsms:
            fsms[session_id] = RecipeStateMachine(recipe_data['recipe']['instructions'])
    # Get or create chat session for this session
    if session_id not in chat_sessions:
        chat_sessions[session_id] = create_chat_session(recipe_data['recipe'])
    
    try:
        fsm = fsms[session_id]
        chat = chat_sessions[session_id]

        #update fsm w regex specific to step changes
        query_lower = query.lower().strip()
        if re.search(r'\bstart\b', query_lower):
            fsm.jump_to_step(1)
        elif re.search(r'\b(next)\b', query_lower):
            fsm.next_step()
        elif re.search(r'\b(back|previous)\b', query_lower):
            fsm.previous_step()
        elif re.search(r'\b(repeat|again)\b', query_lower):
            fsm.get_current_step()
        elif re.search(r'step (\d+)', query_lower):
            step_num = int(re.search(r'step (\d+)', query_lower).group(1))
            fsm.jump_to_step(step_num)

        #how do i
        youtube_response = handle_how_do_i_question(query, fsm)
        if youtube_response:
            return jsonify({'success': True, 'response': youtube_response})


        #reference fsm changes
        fsm_context = fsm_context_for_prompt(fsm)
        full_query = f"FSM context:\n{fsm_context}\nUser question: {query}"

        response = chat.send_message(full_query)
        
        return jsonify({
            'success': True,
            'response': response.text
        })
    except Exception as e:
        return jsonify({'error': f'Error processing query: {str(e)}'}), 500


@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    """Reset the conversation by creating a new chat session."""
    global chat_sessions, recipe_data
    
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    
    if not recipe_data['recipe']:
        return jsonify({'error': 'No recipe loaded. Please parse a recipe first.'}), 400
    
    # Create new chat session
    chat_sessions[session_id] = create_chat_session(recipe_data['recipe'])
    
    return jsonify({
        'success': True,
        'message': 'Conversation reset'
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get the current status of the recipe."""
    global recipe_data
    
    if recipe_data['recipe']:
        return jsonify({
            'has_recipe': True,
            'url': recipe_data['url'],
            'ingredients_count': len(recipe_data['recipe']['ingredients']),
            'steps_count': len(recipe_data['recipe']['instructions'])
        })
    else:
        return jsonify({
            'has_recipe': False
        })


@app.route('/')
def index():
    """Serve the main frontend page."""
    return render_template('index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'message': 'Server is running'})


if __name__ == '__main__':
    app.run(debug=True, port=5000)