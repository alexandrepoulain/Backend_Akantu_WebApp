displacement = model.getDisplacement()
nb_nodes = mesh.getNbNodes()
position = mesh.getNodes()

pulse_width = token_pulse_width
A = token_amplitude
for i in range(0, nb_nodes):
  # Sinus * Gaussian
  x = position[i, 0] - 5.
  L = pulse_width
  k = 0.1 * 2 * np.pi * 3 / L
  displacement[i, 0] = A * \
      np.sin(k * x) * np.exp(-(k * x) * (k * x) / (L * L))