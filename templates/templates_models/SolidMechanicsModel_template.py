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


token_functors

################################################################


def main():

  token_spatial_dimension

  akantu.parseInput('material.dat')

  token_mesh_file
  token_geo_file

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

  token_initialization_model

  ################################################################
  # boundary conditions
  ################################################################
  token_boundary_conditions

  ################################################################
  # initial conditions
  ################################################################
  token_initial_conditions

  ################################################################
  # timestep value computation
  ################################################################
  token_timestep_value

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
