#!/bin/env python 
import BlackDynamite as BD 
import re,os
myrun, myjob = BD.getRunFromScript() 
file = open("material.dat", "r")
lines = file.readlines()
file.close()
in_material=False
ind=0
for line in lines:
  m=re.search('steel',line)
  if m is not None:
    in_material=True
  m=re.search('E=',line)
  if m is not None and in_material == True:
    lines[ind]='E=' + str(myjob.material_steel_e) + '\n'
    in_material=False 
  ind = ind+1
file = open("material.dat", "w+")
file.writelines(lines)
file.close()
myrun.start()
myrun.finish()
