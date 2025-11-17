class RecipeStateMachine:
    def __init__(self, steps):
        self.steps = steps
        self.current_step_index = 0
        #visited states tracking
        self.visited_states = []

    def get_current_step(self):
        return(self.steps[self.current_step_index])
    
    def jump_to_step(self, step_number):

        if ((1 <= step_number) and (step_number <= len(self.steps))):
            self.visited_states.append(self.current_step_index)
            self.current_step_index = step_number - 1
        else:
            print("step number out of range.")

        return(self.get_current_step())

    def move_steps_forward(self, steps_forward):
    #xsteps_forward == -1 -> back 1 step
    #if steps_forward is too many steps forward or back, go to start or end
        new_index = self.current_step_index + steps_forward
        return(self.jump_to_step(new_index + 1))
    
    def next_step(self):
        return(self.move_steps_forward(1))


    def previous_step(self):
        return(self.move_steps_forward(-1))
    
    #if there was a jump (ex. what temp to set oven to form 5 steps ago)
    #and the user wants to go back to the bit of the recipe they were on
    def resume(self):
        if self.visited_states:
            self.current_step_index = self.visited_states[-1]
        return(self.get_current_step())

    #for debugging
    def print_info(self):
        print(f"current step index: {self.current_step_index}")
        print(f"current step: {self.get_current_step()}")
        #print(f"visited states: {self.visited_states}")


    
