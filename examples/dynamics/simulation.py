#!/usr/bin/env python3

from __future__ import print_function
################################################################
import os
import subprocess
import numpy as np
import akantu
################################################################
# Functors to describe boundary conditions
################################################################


class FixedValue:
	def __init__(self, value, axis):
		self.value = value
		self.axis = axis
	def operator(self, node, flags, disp, coord):
	  # sets the displacement to the desired value in the desired axis
	  disp[self.axis] = self.value
	  # sets the blocked dofs vector to true in the desired axis
	  flags[self.axis] = True
################################################################


def main():

  spatial_dimension = 2

  akantu.parseInput('material.dat')

  mesh_file = 'bar.msh' 
  geo_file = 'bar.geo' 

  # if mesh was not created the calls gmsh to generate it
  if not os.path.isfile(mesh_file):
    ret = subprocess.call(
      'gmsh -2 {} {}'.format(geo_file, mesh_file), shell=True)
    if ret != 0:
      raise Exception(
        'execution of GMSH failed: do you have it installed ?')

  ################################################################
  # Initialization
  ################################################################
  mesh = akantu.Mesh(spatial_dimension)
  mesh.read(mesh_file)

  model = akantu.SolidMechanicsModel(mesh)

  model.initFull(_analysis_method = akantu._explicit_lumped_mass)

  ################################################################
  # boundary conditions
  ################################################################
  model.applyDirichletBC(FixedValue(0.0, akantu._x), "XBlocked")
  model.applyDirichletBC(FixedValue(0.0, akantu._y), "YBlocked")

  ################################################################
  # initial conditions
  ################################################################
  displacement = model.getDisplacement()
  nb_nodes = mesh.getNbNodes()
  position = mesh.getNodes()
  
  pulse_width = 1
  A = 0.01
  for i in range(0, nb_nodes):
    # Sinus * Gaussian
    x = position[i, 0] - 5.
    L = pulse_width
    k = 0.1 * 2 * np.pi * 3 / L
    displacement[i, 0] = A * \
        np.sin(k * x) * np.exp(-(k * x) * (k * x) / (L * L))
  ################################################################
  # timestep value computation
  ################################################################
  end_step = 1000
  time_step = 0.025

  model.setTimeStep(time_step)

  ################################################################
  # vizualisation
  ################################################################
  model.setBaseName("waves")
  model.addDumpFieldVector("displacement")
  model.addDumpFieldVector("acceleration")
  model.addDumpFieldVector("velocity")
  model.addDumpFieldVector("internal_force")
  model.addDumpFieldVector("external_force")
  model.addDumpField("strain")
  model.addDumpField("stress")
  model.addDumpField("blocked_dofs")

  ################################################################
  # loop for evolution of motion dynamics
  ################################################################
  model.assembleInternalForces()

  for step in range(0, end_step + 1):
    print('{}/{}'.format(step,end_step))
    model.solveStep()

    if step % 10 == 0:
      model.dump()

    epot = model.getEnergy('potential')
    ekin = model.getEnergy('kinetic')

  return


################################################################
if __name__ == "__main__":
  main()
