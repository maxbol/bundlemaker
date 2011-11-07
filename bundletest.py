#!/usr/bin/env python

import os,sys,subprocess

args = sys.argv[1:]
archive = args[0]

if os.access(
	os.path.join( archive, "depends" ),
	"R_OK"):
		depfile = open(
			os.path.join( archive, "depends" ),
			'r'
			)

		dpstr = depfile.read()
else:
		print "Corrupted bundle. Could not check."
		sys.exit(0)

if os.access(
	os.path.join( archive,
			"Ubuntu",
			"DEBIAN",
			"control",
			),
	"R_OK"):
		controlfile = open(
			os.path.join( archive,
					"Ubuntu",
					"DEBIAN",
					"control",
					),
					'r'
					)
		ctstr = controlfile.read()
else:
		print "Corrupted bundle. Could not check."
		sys.exit(0)	

dpdict = {}
buf = ["",""]
isver = 0
ccount = 1

for char in dpstr:
	if char == "," or ccount == len(dpstr):
		dpdict[buf[0]] = buf[1]
		buf = ["",""]
		isver = 0
	elif char in ("(",")"):
		isver = 1
	else:
		buf[isver] += char
	ccount += 1


