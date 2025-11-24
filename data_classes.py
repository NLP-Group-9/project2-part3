class Ingredient:
    """Represents a recipe ingredient"""
    def __init__(self, name, quantity, measurement_unit):
        self.name = name
        self.quantity = quantity
        self.measurement_unit = measurement_unit
    
    def __repr__(self):
        return f"Ingredient(name='{self.name}', quantity='{self.quantity}', measurement_unit='{self.measurement_unit}')"

class Step:
    """Represents a recipe step"""
    def __init__(self, step_number, description, ingredients=None, tools=None, methods=None, time=None, temperature=None, type="Observation"):
        self.step_number = step_number
        self.description = description
        self.ingredients = ingredients if ingredients is not None else []
        self.tools = tools if tools is not None else []
        self.methods = methods if methods is not None else []
        self.time = time if time is not None else {}
        self.temperature = temperature if temperature is not None else {}
        self.type = type
    
    def __repr__(self):
        return f"Step(step_number={self.step_number}, description='{self.description[:50]}...', ingredients={self.ingredients}, tools={self.tools})"