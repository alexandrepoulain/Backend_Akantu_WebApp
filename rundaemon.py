#!/usr/bin/env python
# coding: utf-8
####################################
# AKANTU Akantu daemon blackdynamite
# Class + Script to go through the
# blackdynamite database and check
# if some runs have to be launched
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
from createsimulation import CreateSimulation
from daemonBD import DaemonBD

#####################################################################################################
# Part script 
# Creation of two thread one has the role to create the runs by parsing the json input files
# The other thread has the role to launch the runs
#####################################################################################################

class DaemonThread(threading.Thread):

    def __init__(self, ip, port, clientsocket, l):
        threading.Thread.__init__(self)
        self.ip = ip
        self.port = port
        self.clientsocket = clientsocket
        print("[+] New thread for %s %s" % (self.ip, self.port, ))
        self.lock = l

    def run(self): 
   
        print("Connection of %s %s" % (self.ip, self.port, ))

        path_to_json = self.clientsocket.recv(2048)
        m = re.search(r"(?P<path>.+)/(?P<json>\w+).json", path_to_json)
        jsonFile = path_to_json
        userpath = m.group('path')
        print("Receive json file  : ", jsonFile, "at path : ", userpath)
        simu = CreateSimulation(jsonFile, userpath, self.lock)
        simu.run()
        self.clientsocket.send("Runs created")

        print("Client deconnected...")

def listen(tcpsock,lock):
	while True:
		tcpsock.listen(10)
		print( "Listening...")
		(clientsocket, (ip, port)) = tcpsock.accept()
		newthread = DaemonThread(ip, port, clientsocket, lock)
		newthread.start()

def daemon_BD(lock):
	daemonBD = DaemonBD(lock)
	while True:
		time.sleep(10)
		print( "check database...")
		daemonBD.check_database()

tcpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcpsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
tcpsock.bind(("",1111))
lock = Lock()
p1 = Process(target=listen, args=(tcpsock,lock))
p1.start()


p2 = Process(target=daemon_BD, args=(lock,))
p2.start()

p1.join()
p2.join()
