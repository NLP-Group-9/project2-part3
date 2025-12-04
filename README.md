# Recipe Chat - Voice-Enabled Recipe Assistant

A web-based recipe parsing and querying system that uses NLP to extract and answer questions about recipes from popular cooking websites. A combination of parts 1 and 2 of this project, with the best parts of each. AI answers most questions but defers to a finite state machine to keep track of step order (more successful!)

**Python version:** 3.11.9  
**GitHub:** https://github.com/NLP-Group-9/project2-part3
**Gemini model:** gemini-2.5-flash-lite

## Quick Start

### Installation

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### .env set up
add a .env file into the folder with variable
GEMINI_API_KEY=[YOUR GEMINI API KEY HERE]

### Run the Application For GUI (Voice + Text)

```bash
python app.py
```

Then open your browser to `http://localhost:5000`

### Run the Application For text based interaction

```bash
python recipe_chat.py
```


## Usage

1. **Parse a Recipe:** Enter a recipe URL from allrecipes.com or seriouseats.com and click "Parse Recipe"
2. **Ask Questions:** Use the voice button or type your question and click "Ask"

## Supported Queries

### Recipe Display
- `show ingredients` - List all ingredients
- `show recipe` - Display all steps
- `show step 3` - Show a specific step

### Recipe Walkthrough
- `start recipe` - Begin step-by-step walkthrough
- `next` - Next step
- `back` - Previous step
- `repeat` - Repeat current step

### Ingredient Questions
- `how much salt do I need?`
- `how many eggs do I need?`
- `how much of that?` (in walkthrough mode)

### Cooking Questions
- `what temperature?`
- `how long to bake?`
- `how long does it take?`

### Substitutions
- `what can I substitute for butter?`
- `I don't have eggs`

### Definitions & How-To
- `what is zesting?` - Get ai generated definition (we thought it would be more helpful than a google link)
- `how do I julienne?` - Get YouTube video search link

## Browser Compatibility

**Speech Recognition:**
- Chrome (recommended)
- Edge
- Safari (limited)
- Firefox (text input only)

## Parsing Logic
All Parsing is handled by Google's Gemini. Model is specified in the header of this README

## Prompt Used
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


## Extra Credit Features

1. **Multi-website Support:** Supports allrecipes.com and seriouseats.com recipes
2. **Speech-to-Text:** Voice-enabled query interface using Web Speech API

## Tested Recipes

- `https://www.allrecipes.com/recipe/218091/classic-and-simple-meat-lasagna/`
- `https://www.allrecipes.com/recipe/228285/teriyaki-salmon/`
- `https://www.seriouseats.com/pecan-pie-cheesecake-recipe-11843450`
- 'https://www.allrecipes.com/recipe/19511/smoked-salmon-sushi-roll/'