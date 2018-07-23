#!/usr/bin/env python
# coding: utf-8
####################################
# AKANTU Parsing the Jjson file
# produced by the WebApp
####################################
import psycopg2
import re
import time
import BlackDynamite as BD
from types import ModuleType
import os
import sys
import socket
import json
import numpy as np
import threading
from multiprocessing import Process, Lock


class CreateSimulation():
	""" docstring for Simulation
	        Class Simulation

	        Attributs
	        ---------

	        Methods
	        -------

	"""
	def __init__(self, jsonName="", path="", l= None):
		self.jsonFile = jsonName
		self.userPath = path
		self.parametric_space = {}
		self.templatePath = '/home/alexandre/Bureau/Backend_Akantu_WebApp/templates'
		self.geo_file = 'bar.geo'
		self.mesh_file = 'bar.msh'
		self.path_to_IC = '.'
		self.nbProc = 1
		self.tab = "  "
		self.lock = l
		self.need_functors = False
		self.functors = []

	def listen(self):
		""" method to listen the web application
		If an user wants to create jobs and runs 
		the application will send a message to this class to create the runs 
		The deamon will listen to the port 15555 on localhost

		"""
		socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		socket.bind(('', 15555))

		while True:
			socket.listen(5)
			client, address = socket.accept()
			print"{} connected".format( address )
			# once we are connected we have to make sure that the other process 
			# is in sleep mode (we can commit some changes on the database)

			response = client.recv(255)
			if response != "":
			  print response

		print "Close"
		client.close()
		stock.close()

	def flush_connections(self):
		"""Method to delete the previous connections to database in order to avoid the conflict between the parsing process
		and the launching runs process
		"""
		conn = psycopg2.connect("dbname=blackdynamite user=alexandre")
		curs = conn.cursor()
		curs.execute('SELECT *, pg_terminate_backend(pid) FROM pg_stat_activity  WHERE pid <> pg_backend_pid() AND datname = \'blackdynamite\';')
		curs.close()
		conn.close()

	def open_json_file(self):
	  """ open the JSON file and read its content line per line
	  """
	  with open(self.jsonFile, 'r') as json_file:
	    # read data
	    self.data = json.load(json_file)

	  # Fill the main attributs
	  # we can define more than one boundary condition and
	  # material
	  self.materials = []
	  self.bc = []
	  self.ic = []
	  for key, value in self.data.items():
	    if key == 'Username':
	      self.username = value
	    elif key == 'Dimension':
	      self.dim = value
	    elif key == 'Model':
	      self.model = value
	    elif key == 'Material':
	      self.materials.append(value)
	    elif key == 'BoundaryConditions':
	      self.bc = value
	    elif key == 'InitialConditions':
	      self.ic.append(value)  

	def run(self):
	  """ create all the components of the simulations and create the jobs nd runs for blackdynamite

	  """
	  self.open_json_file()
	  self.create_material_file()
	  self.create_simulation_file()

	  # launch createDB
	  # create the arguments for createDB
	  self.lock.acquire()
	  self.create_db()
	  self.create_jobs()
	  self.create_config_file()
	  self.create_exec_file()
	  self.create_runs()
	  self.lock.release()

	def create_config_file(self):
	  """ write the config file
	  this python script will change the parameters defined in the
	  parametric space into the concerned file (material.dat or simulation.cc)
	  This script permits also to push quantities in the database and access
	  them while the simulation is running
	  """
	  with open(self.userPath + '/config.py', 'w') as config_file:
	    lines = ['#!/bin/env python \n', 'import BlackDynamite as BD \n','import re,os\n',
	               'myrun, myjob = BD.getRunFromScript() \n']

	    for key, value in self.parametric_space.items():
				print("key = " +str(key))
				if 'Material' in key:
					# find the material name
					m = re.search(
					    r"Material_(?P<name>\w+)_(?P<param>\w+)", key)
					material_name = m.group('name')
					# find the parameter concerned
					parameter = m.group('param')
					# config opens material file and reads its content
					lines.append('file = open(\"material.dat\", \"r\")\n')
					lines.append('lines = file.readlines()\n')
					# then config close it to open it later in write mode
					lines.append('file.close()\n')
					# config initializes a variable to know if it is in the right material
					# and to find the indexes where the change will be made
					lines.append('in_material=False\n')
					lines.append('ind=0\n')
					lines.append('for line in lines:\n')
					# config file need to search the parameter
					lines.append(self.tab+'m=re.search(\'{}\',line)\n'.format(
					    material_name.lower()))
					# if it finds it, it needs to search the parameter
					lines.append(self.tab+'if m is not None:\n')
					lines.append(self.tab+self.tab+'in_material=True\n')
					lines.append(self.tab+'m=re.search(\'{}=\',line)\n'.format(
					    parameter))
					lines.append(self.tab+'if m is not None and in_material == True:\n')
					lines.append(self.tab+self.tab+'lines[ind]=\'{}=\' + str(myjob.{}_{}_{}) + \'\\n\'\n'.format(parameter,'material',material_name.lower(),parameter.lower()))
					# config has found the vaiable so we are moving to another parameter
					lines.append(self.tab+self.tab+'in_material=False \n')
					# write the line
					lines.append(self.tab+'ind = ind+1\n')
					# write the lines
					lines.append('file = open(\"material.dat\", \"w+\")\n')
					lines.append('file.writelines(lines)\n')
					lines.append('file.close()\n')

	    lines.append('myrun.start()\n')
	    # TODO push values
	    lines.append('myrun.finish()\n')

	    # write file
	    config_file.writelines(lines)

	def create_exec_file(self):
	  """ this method creates the executable file that will launch the config file and the script

	  """
	  with open(self.userPath + '/exec.sh', 'w') as exec_file:
	    exec_file.write('python ./config.py\n')
	    exec_file.write('python3 ./simulation.py')

	def create_simulation_file(self):
		""" create the simulation file from a template corresponding to
		the model and dimension selected.
		The boundary conditions are also defined within this file so they need to be handled
		in this function
		"""
		# create and open the simulation file
		lines_to_write = []
		# In function of the model selected copy and past the contents of the template
		# in this new file
		# Select the template
		path_template = self.templatePath + '/templates_models/' + \
		  self.model['ModelType'] + '_template.py'
		with open(path_template, 'r') as template_file:
		  # We read each line of the template file, copy and paste them to the new simulation
		  # file while replacing parts of them
		  for line in template_file:
		    # if the line contains something that need to be replaced
		    if "token" in line:
		      new_lines = self.create_line_simulation(line)
		      if type(new_lines) == list:
		        # more than one line to write
		        lines_to_write = lines_to_write + new_lines
		      if type(new_lines) == str:
		        # only one line to create
		        lines_to_write.append(new_lines)
		    # other wise we just copy-paste the line in simulation.py
		    else:
		      lines_to_write.append(line)
		with open(self.userPath + '/simulation.py', 'w+') as simu_file:
			# write the functors at the beginning of the file
			for line in lines_to_write:
				if 'token_functors' in line:
					# write every functors
					for fun in self.functors:
						# open the corresponding template and write the lines in the simu file
						with open(self.templatePath +'/templates_BC/{}_template.py'.format(fun)) as fun_template:
							for template_line in fun_template:
								simu_file.write(template_line)
				else:
					simu_file.write(line)

	def create_line_simulation(self, line):
	  """ create the corresponding line using the token and the data contained in the json file

	  """
	  if 'spatial_dimension' in line:
	    return self.tab+'spatial_dimension = ' + str(self.dim) + '\n'
	  if 'mesh_file' in line:
	    return self.tab+'mesh_file = \'' + self.mesh_file + '\' \n'
	  if 'geo_file' in line:
	    return self.tab+'geo_file = \'' + self.geo_file + '\' \n'
	  if 'token_initialization_model' in line:
			newLine = self.tab+'model.initFull(_analysis_method = akantu.' + self.model['Parameters']['AnalysisMethod'] + ')\n'
			return str(newLine)
	  if 'token_boundary_conditions' in line:
	    temp_ret = self.write_boundaryconditions()
	    return temp_ret
	  if 'token_initial_conditions' in line:
	    temp_ret = self.write_initial_conditions()
	    return temp_ret
	  if 'token_timestep_value' in line:
	    ret_lines = []
	    # define end step
	    ret_lines.append(self.tab+'end_step = {}'.format(
	      self.model['Parameters']['EndStep']) + '\n')
	    ret_lines.append(self.tab+'time_step = {}'.format(
	      self.model['Parameters']['TimeStep']) + '\n')
	    return ret_lines
	  if 'token_functors' in line:
	  	return 'token_functors'

	def write_boundaryconditions(self):
	  """ TODO

	  """
	  lines = []
	  for Boundcond in self.bc:
		  # depending of the type of boundary condition
		  print(self.bc)
		  if Boundcond['BCType'] == 'Dirichlet':
		  	if 'FixedValue' not in self.functors:
		  		self.functors.append('FixedValue')
		  		# boolean to true in order to write the functors at the beginning of the simulation file
			  	self.need_functors = True
		  	disp_value = Boundcond['Value']
		  	direction = Boundcond['Direction']
		  	on_what = Boundcond['on']
		  	lines.append(self.tab+'model.applyDirichletBC(FixedValue({}, akantu._{}), \"{}\")\n'.format(disp_value, direction.lower(), on_what))
	  return lines

	def write_initial_conditions(self):
	  """ Find the initial conditions wanted in the json file
	  Then finds the functor and replace the parameters
	  or write directly the code present in the json

	  """
	  lines = []
	  # fro each initial conditions defined in json
	  for initial_cond in self.ic:
		  # find the type wanted
		  ICType = initial_cond['ICType']
		  # and now depending on the type we define different ics
		  if ICType == 'Sinusoidal':
	  		# find the functor 
	  		with open(self.templatePath + '/templates_IC/functor_IC_sinusoidal.py','r') as functor_file:
	  			for line in functor_file:
	  				if 'token_pulse_width' in line:
	  					lines.append(self.tab+'pulse_width = '+str(initial_cond['PulseWidth'])+'\n')
	  				elif 'token_amplitude' in line:
	  					lines.append(self.tab+'A = '+str(initial_cond['Amplitude'])+'\n')
	  				else:
	  					lines.append(self.tab + line)
	  return lines

	def create_material_file(self):
	  """ create the material.dat file and file it with the info extracted from
	  the json file.
	  This function also checks if a parameter is defined as a range.
	  If this is the case it stocks this information and add a default value in 
	  the .dat file.
	  """
	  # create and open the material.dat file
	  with open(self.userPath + '/material.dat', 'w') as material_file:
	    # for each material
	    for material in self.materials:
	      # write the type of the material
	      line = 'material ' + material['MaterialType'] + ' [ \n'
	      material_file.write(line)
	      #write the name of the material
	      line = 'name='+material['name'] +'\n'
	      material_file.write(line)
	      # for each parameter we write it in the material file
	      # except if this is a range a value
	      for key, value in material.items():
	      	print(key)
	        if key != 'MaterialType' and key != 'name':
	          if type(value) != dict:
	            line = key + '=' + str(value) + '\n'
	            material_file.write(line)
	          else:
	            # define a key so that we can create the job for this
	            # parameter in this specific material
	            new_key = 'Material_'+material['name'] + '_' + key
	            # define the range from the infos in the json file
	            range_values = self.define_range(value)
	            # append this new variable in the parametric space
	            self.parametric_space[new_key] = range_values
	            # and we define a standard value for this parameter in the file
	            # we will take the first value of the range
	            default_value = range_values[0]
	            line = key + '=' + str(default_value) + '\n'
	            material_file.write(line)
	      material_file.write(']')

	def define_range(self, value):
	  """ From the dictionnary contained in value we can define the range
	  """
	  # if numeric
	  if value['type'] == 'int' or value['type'] == 'float':
	    min_val = value['min']
	    max_val = value['max']
	    step = value['step']
	    new_range = list(np.arange(min_val, max_val, step))
	    return new_range
	  elif value['type'] == 'array_str':
	    return value('values')
	  else:
	    # log error
	    print('error type of range not known')

	def parse_model_parameters(self):
	  """ This method parse the parameters of the model 
	  In function of the type of the model we need to fill different parameters

	  """
	  self.modelType = self.model['ModelType']

	  if self.modelType == 'SolidMechanicsModel':
	    self.modelParameters = self.model['Parameters']
	    self.AnalysisMethod = self.modelParameters['AnalysisMethod']
	    self.timeStep = self.modelParameters['TimeStep']
	    self.searchKeys.append('AnalysisMethod', 'TimeStep')

	def parse_material_parameters(self):
	  """ This method parse the parameters of the material 
	  In function of the type of the material we need to fill different parameters
	  Also search if this is defined as a dictionnary: if yes it means that 
	  this is a range so it has to be in the parametric space 
	  """
	  self.materialType = self.material['MaterialType']
	  self.materialName = self.material['name']
	  if self.materialType == 'elastic':
	    self.rho = self.material['rho']
	    self.E = self.material['E']
	    self.nu = self.material['nu']

	  self.create_material_file()

	def parse_boundary_conditions(self):
	  """ This method parse the parameters of the BC 
	  In function of the type of the BC type we need to fill different parameters

	  """
	  self.bcType = self.bc['BCType']

	def create_db(self):
	  # Then you have to create a generic black dynamite parser
	  # and parse the system (including the connection parameters and
	  # credentials)
	  self.parser = BD.bdparser.BDParser()
	  studyName = self.username + self.model['ModelType']
	  arguments = ['--host', 'localhost',
	               '--truerun', '--study', studyName, '--yes', '--logging']
	  self.params = self.parser.parseBDParameters(arguments)

	  # Then we can connect to the black dynamite database
	  # localhost because it will be install on the server

	  self.base = BD.base.Base(**self.params)
	  print(self.base.dbhost)

	  # Then you have to define the parametric space (the job pattern)

	  job_desc = BD.job.Job(self.base)

	  # define the parameters of the fileds defining the jobs
	  job_desc = self.define_types_fields(job_desc)
	  job_desc = self.define_parametric_space(job_desc)

	  # Then you have to define the run pattern
	  myruns_desc = BD.run.Run(self.base)
	  myruns_desc.types["compiler"] = str

	  # Then we request for the creation of the database
	  # create the neame of the study

	  # check data base to make sure that this studyName is not
	  # studyName = checkStudyName()
	  self.base.createBase(job_desc, myruns_desc, **self.params)

	def define_types_fields(self, job_desc):
	  """ defines the types of the fields for the jobs

	  Arguments
	  ---------
	  job_desc: (Job) reference to modify the object
	  """
	  # define type username
	  job_desc.types["username"] = str
	  # define type dimension
	  job_desc.types["dim"] = int
	  # define type model
	  job_desc.types["modelType"] = str

	  return job_desc

	def define_parametric_space(self, job_desc):
	  """ Go through the attributs and which one is of type
	  dictionnary. In this case we will define a component of the jobs and runs
	  """
	  for key, value in self.parametric_space.items():
	      if type(value[0]) == np.float64:
	          job_desc.types[key] = float
	  return job_desc

	def create_jobs(self):
	  """ create the jobs 

	  """
	  # Then you have to create a generic black dynamite parser
	  # and parse the system (including the connection parameters and
	  # credentials)

	  # create of job object
	  job = BD.job.Job(self.base)
	  # specify a range of jobs
	  job["username"] = self.username
	  job["dim"] = self.dim
	  job["modelType"] = self.model['ModelType']
	  for key, value in self.parametric_space.items():
	    job[key] = value
	  # creation of the jobs on the database
	  self.base.createParameterSpace(job)

	def create_runs(self):
	  """ create the runs 

	  """
	  # create the config and the executable file (the one that will launch
	  # the program)
	  # import a runparser (instead of a generic BD parser)
	  
	  
	  self.parser = BD.bdparser.RunParser()
	  studyName = self.username + self.model['ModelType'] 
	  arguments = ['--logging', '--host', 'localhost', '--truerun', '--study', studyName,
	               '--machine_name', 'demonAkantu', '--nproc', str(self.nbProc), '--run_name', studyName + '_run']
	  self.params = self.parser.parseBDParameters(arguments)

	  # Then we can connect to the black dynamite database
	  self.base = BD.Base(**self.params)

	  # create a run object
	  myrun = BD.Run(self.base)

	  # set the run parameters from the parsed entries
	  myrun.setEntries(self.params)

	  # add a configuration file
	  myrun.addConfigFiles([self.userPath+"/config.py", self.userPath+"/material.dat", self.userPath+"/"+self.geo_file, self.userPath+"/simulation.py"])

	  # set the entry point (executable) file
	  myrun.setExecFile(self.userPath+"/exec.sh")

	  # create a job selector
	  jobSelector = BD.JobSelector(self.base)

	  # select the jobs that should be associated with the runs about to be
	  # created
	  job_list = jobSelector.selectJobs(self.params)

	  # create the runs
	  for j in job_list:
	    myrun['compiler'] = 'gcc'
	    myrun.attachToJob(j)

	  # if truerun, commit the changes to the base
	  if (self.params["truerun"] is True):
			self.base.commit()

