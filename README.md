#Project 1
python ver. 3.11.9
Github link: https://github.com/NLP-Group-9/project2

## Dependencies
This project requires the following Python packages:

- requests
- beautifulsoup4
- spacy

Install them with:
pip install -r requirements.txt

Also install the following spacy model:
python -m spacy download en_core_web_sm

## Steps to run
1) Run recipe_chat with:
>python3 recipe_chat.py

## Recipes and Websites Tested On
1) allrecipes.com like:
   "https://www.allrecipes.com/recipe/218091/classic-and-simple-meat-lasagna/"
   "https://www.allrecipes.com/recipe/228285/teriyaki-salmon/"

3) seriouseats.com like:
   "https://www.seriouseats.com/pecan-pie-cheesecake-recipe-11843450"
   
## Supported User Inputs

Below is a comprehensive list of the types of queries the bot understands. These examples cover everything the bot is designed to do.

---

### **1. Recipe Retrieval and Display**
Use these commands to view the recipe or its components.

- “Show me the ingredients list.”
- “What are the ingredients?”
- “Ingredients please.”
- “Display the recipe.”
- “Show me the full recipe.”

---

### **2. Navigation Commands**
Control the recipe walkthrough step-by-step.

- “Start the recipe walkthrough.”
- “Start cooking.”
- “Start.”
- “Next.”
- “Go to the next step.”
- “Go back.”
- “Go back a step.”
- “Repeat please.”
- “What’s next?”
- “What was that again?”
- “Take me to step 3.”
- “Resume recipe walkthrough.”
- “Resume.”

---

### **3. Step Parameter Queries**
Ask about details in the *current* step (timing, quantities, temperatures, substitutions).

- “How much salt do I need?”
- “What temperature should the oven be?”
- “How long do I bake it?” *(only works if “bake” appears in the recipe steps)*
- “When is it done?”
- “What can I substitute for butter?”
- “What can I use instead of butter?”

---

### **4. Clarification Questions**
Ask for explanations of tools, terms, or techniques.

- “What is a whisk?”
- “What’s X?”
- “How do I sauté?”
- “How do I X?”

---

### **5. Procedure Questions**
Ask how to perform an action mentioned in the current step.  
*(Requires starting the recipe walkthrough first.)*

- “How do I knead the dough?”
- “How do I do that?”
- “What is that?” *(referring to the current step’s action)*

---

### **6. Quantity Questions**
Ask about ingredient amounts.

- **Specific:** “How much flour do I need?”
- **Step-dependent:** “How much of that do I need?” *(requires the recipe walkthrough to be active)*

---

## Parsing Logic
1) Ingredient and Instruction extraction from websites.
   We use BeautifulSoup to read the url and then identify hard coded html tags to identify and extract ingredients and instructions text from the url.

2) Ingredient Parsing.
   The websites that work (allrecipes and seriouseats) have the html tags already differentiate the name, quantity, and measurements of the ingredients which made it incredibly easy to parse. We use this information because it was already expertly prepared by the writer.

3) Atomize Instructions.
   We first atomize the steps by splitting the instructions by common conjunctions and punctuation.

4) Instruction Parsing.
   The main purpose of this step is to identify the ingredients, tools, methods, times, and temps available in a specified instruction step.
   - Ingredients were identified from the ingredients obtained from Step 2). We used substring search for the ingredients since some of the ingredients appear with shorter names in the ingredients.
   - Tools were identified from using a hardcoded list of tools.
   - Methods were extracted from a hardcoded list plus the use of spaCy tagging for VERBS
   - Time was extracted by finding common temp terms (medium heat, low heat, etc) and the detection of numbers from units (Fahrenheit, Celsius, etc)
   - Temp was extracted by finding common numbers including units (seconds, minutes, hours, etc).

## Extra Credit Features
1) Supports allrecipes.com AND seriouseats.com recipes. We tried to also get functionality for the listed websites on the project page: epicurious, bonappetit, delish, and foodnetwork but all of them had issues that were out of our control.
Mainly, epicurious, bonappetit, delish required a paid subscription to access recipes. Foodnetwork did not allow for out html reader to access the website.

2) (IN PROGRESS) Speech to text functionality.
