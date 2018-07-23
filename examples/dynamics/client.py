#!/usr/bin/env python
# coding: utf-8

import socket

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("", 1111))

s.send('/home/alexandre/Bureau/Backend_Akantu_WebApp/examples/dynamics/test.json')
r = s.recv(9999999)

print("Received : \"%s\" from server" %r)
