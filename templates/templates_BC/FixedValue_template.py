class FixedValue:
	def __init__(self, value, axis):
		self.value = value
		self.axis = axis
	def operator(self, node, flags, disp, coord):
	  # sets the displacement to the desired value in the desired axis
	  disp[self.axis] = self.value
	  # sets the blocked dofs vector to true in the desired axis
	  flags[self.axis] = True