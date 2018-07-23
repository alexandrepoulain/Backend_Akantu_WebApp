#!/usr/bin/env python
# coding: utf-8
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

##################
# Class to check the database and launch the runs
##################
class DaemonBD(threading.Thread):
	"""Class to define the blackdynamite daemon"""

	def __init__(self, l):
		super(DaemonBD, self).__init__()
		# connect to database
		self.user = 'blackdynamite'
		self.dbname = 'blackdynamite'
		arguments = ['--dbname', 'blackdynamite', '--user', 'blackdynamite']
		self.lock = l

	def active_connections(self):
		self.curs.execute("SELECT * FROM pg_stat_activity;")
		list_connections = self.curs.fetchall()
		for connection in list_connections:
			print(connection)
		return True

	def flush_connections(self):
		self.curs.execute('SELECT *, pg_terminate_backend(pid) FROM pg_stat_activity  WHERE pid <> pg_backend_pid() AND datname = \'blackdynamite\';')

	def check_database(self):
		"""Method to check the database and find if some runs have to be launched

		"""
		# When we check the database we lock the database to avoid conflict
		self.lock.acquire() 
		print("lock acquired")
		self.conn = psycopg2.connect("dbname=blackdynamite user=alexandre")
		self.curs = self.conn.cursor()
		# list all the studies
		self.schemaList = self.getSchemaList()
		print(self.schemaList)
		# Go through the list of the studies
		for study in self.schemaList:
			# curs.execute("SELECT pg_terminate_backend(pg_stat_activity.pid)FROM pg_stat_activity WHERE pg_stat_activity.datname = 'blackdynamite' AND pid <> pg_backend_pid();")
			# before doing anything we check if we can use the database
			#try_bool = self.active_connections()
			self.curs.execute("SELECT * FROM {}.runs;".format(study))
			listruns = self.curs.fetchall()
			# for each runs
			for run in listruns:
				# check if the run need to be launched
				if run[6] != 'FINISHED':
					username = self.find_username(study)
					# then retreive the informations concerning the runs
					outpath = './user_data/'+ username
					machineName = 'demonAkantu'
					try:
						ret_bool = self.launch_runs(machineName, study, outpath)
						# and then directly return
						self.flush_connections()
						self.curs.close()
						self.conn.close()
						self.lock.release()
						print("lock released")
						return
						
					except Exception as e:
						print('can\'t launch the runs')
		self.flush_connections()
		self.curs.close()
		self.conn.close()
		self.lock.release()
		print("lock released")

	def find_username(self,study):
		self.curs.execute("SELECT * FROM {}.jobs;".format(study))
		listjobs = self.curs.fetchall()
		return str((listjobs[0])[1])

	def getSchemaList(self, filter_names=True):
		self.curs.execute(
			"""SELECT distinct(table_schema) from information_schema.tables where table_name='runs'""")
		schemas = [desc[0] for desc in self.curs]
		filtered_schemas = []
		if filter_names is True:
			for s in schemas:
				m = re.match('{0}_(.+)'.format(self.user), s)
				if m:
					s = m.group(1)
					filtered_schemas.append(s)
				else:
					filtered_schemas = schemas
		return filtered_schemas

	def launch_runs(self, machine_name, study, outpath, argv=None):
		""" 

		"""
		if (type(argv) == str):
			argv = argv.split()
		parser = BD.BDParser()

		parser.register_params(
        group="launchRuns.py",
        params={
            "outpath": str,
            "generator": ModuleType,
            "nruns": int,
            "state": str,
            "machine_name": str},
        defaults={
            "machine_name": socket.gethostname(),
            "nruns": -1,
            "generator": "bashCoat"})

		parser.help.update({
		    "nruns": ('Specify the number of runs to launch. '
		              'This is useful when we want to launch '
		              'only the first run from the stack.'),
		    "generator": "Specify the launcher generator"
		    })

		arguments = ['--host', 'localhost', '--machine_name', machine_name,
		    '--study', study, '--truerun', '--outpath', outpath]
		params = parser.parseBDParameters(arguments)
		mybase = BD.Base(**params)
		if ("outpath" not in params):
			print('A directory where to create temp files '
				'should be provided. use --outpath ')
			sys.exit(-1)
		# create directories to save the results
		mydir = os.path.join(params["outpath"], "BD-" + params["study"] + "-runs")
		if not os.path.exists(mydir):
			os.makedirs(mydir)

		os.chdir(mydir)

		runSelector = BD.RunSelector(mybase)
		constraints = []
		if ("constraints" in params):
			constraints = params["constraints"]

		def item_matcher(name, item):
			return item.lower().lstrip().startswith(name)

		if not any([item_matcher("state", item) for item in constraints]):
			constraints.append("state = CREATED")
		if not any([item_matcher("machine_name", item)for item in constraints]):
			constraints.append("machine_name = {0}".format(params["machine_name"]))

		run_list = runSelector.selectRuns(constraints)

		if (params["nruns"] > 0):
			run_list = [run_list[i]
			    for i in range(0, min(params["nruns"], len(run_list)))]

		if (len(run_list) == 0):
			# print("No runs to be launched")
			return False

		for r, j in run_list:
			# print("Dealing with job {0.id}, run {1.id}".format(j, r))
			r["run_path"] = os.path.join(mydir, "run-" + str(r.id))
			# print(j.types)
			j.update()

			if not os.path.exists("run-" + str(r.id)):
				os.makedirs("run-" + str(r.id))

			os.chdir("run-" + str(r.id))

			conffiles = r.getConfigFiles()
			for conf in conffiles:
				# print("create file " + conf["filename"])
				f = open(conf["filename"], 'w')
				f.write(conf["file"])
				f.close()

			# print("launch in '" + mydir + "/" + "run-" + str(r.id) + "/'")
			mymod = params["generator"]
			# print(mymod)
			mymod.launch(r, params)

			os.chdir("../")

		if (params["truerun"] is True):
			# to commit the change in the database we need the lock
			mybase.commit()
		return True



