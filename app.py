from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from html_parser import process_url
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash-lite"

# Global state to store parsed recipe data
recipe_data = {
    'recipe': None,
    'url': None
}

# Store chat sessions per session (simplified - in production use proper sessions)
chat_sessions = {}


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
    global recipe_data, chat_sessions
    
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
    
    # Get or create chat session for this session
    if session_id not in chat_sessions:
        chat_sessions[session_id] = create_chat_session(recipe_data['recipe'])
    
    try:
        chat = chat_sessions[session_id]
        response = chat.send_message(query)
        
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