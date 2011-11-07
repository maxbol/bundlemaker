#!/usr/bin/env python

#import apt
import apt.debfile
import os,sys,subprocess
from time import *
from tarfile import *
import gzip
from debian.arfile import ArFile
from xdg import DesktopEntry,IconTheme
import shlex
from gi.repository import Notify

args = sys.argv[1:]
pkgfile = os.path.abspath(args[0])
pkgdir,pkgname = os.path.split(pkgfile)
pkgname_clean = pkgname.title()
pkgname_clean = pkgname_clean.replace("_","")
pkgname_clean = pkgname_clean.replace(" ","")
pkgname_clean = pkgname_clean.replace("(","")
pkgname_clean = pkgname_clean.replace(")","")
pkgname_clean = pkgname_clean.replace("%","")
try:
	pkgname_clean = pkgname_clean[:pkgname_clean.index(".Deb")]
	#pkgname_clean = pkgname_clean[:pkgname_clean.index("-")]
	pkgname_clean = pkgname_clean[:pkgname_clean.index("+")]
	pkgname_clean = pkgname_clean[:pkgname_clean.index(":")]
	pkgname_clean = pkgname_clean[:pkgname_clean.index("~")]
	pkgname_clean = pkgname_clean[:pkgname_clean.index("\%")]
except:
	pass
tempdir = "/tmp"
hometempdir = os.path.join(os.getenv("HOME"),".config/bundlemaker")

Notify.init("BundleMaker")
bundle_notify_msg_SUCCESS = Notify.Notification.new(pkgname_clean,"Application %s was successfully mounted and is ready to run." % pkgname_clean, "block-device")
bundle_notify_msg_FAILURE = Notify.Notification.new(pkgname_clean,"Starting Ubuntu Software Center.", "synaptic")

def cleanup():
	os.system("rm -f -R %s" % dirpath)
	os.system("rm -f %s" % static_name + ".bun")
	#os.system("rm -f %s" % static_name)
	os.system("rm -f %s" % static_name + ".desktop")
	os.system("rm -f Applications")
	Notify.uninit()

def fallback():
	bundle_notify_msg_FAILURE.show()
	subprocess.Popen(("software-center",pkgfile))
	cleanup()
	sys.exit(1)

os.chdir(tempdir)

if not os.access(hometempdir,os.R_OK):
	try:
		os.makedirs(hometempdir)
	except:
		fallback()

# GET PACKAGE METADATA
try:
	testPackage = apt.debfile.DebPackage(filename=pkgfile)
	desktop_app = False
	desktop_list = []
	for i in testPackage.filelist:
		if i[-8:] == ".desktop":
			desktop_list.append(i)
			desktop_app = True
	if not desktop_app:
		fallback()

except:
	print "Couldn't read package file. Quitting."
	fallback()

# CREATE TEMPORARY DIR
try:
	tf = "%Y%m%d%H%M%S"; lt = localtime()
	timestr = strftime(tf,lt)
	dirpath = "%s.bundle.%s" % (pkgname, timestr)
	os.mkdir(dirpath)
	tree = ["Ubuntu","Sys","Data","Icons","BundleData"]
	for i in tree:
		os.mkdir(os.path.join(dirpath,i))
except:
	print "No write permissions. Quitting."
	fallback()

# INHABIT
try:
	arfile = ArFile(pkgfile)
except:
	print "Could not read AR format. Quitting."
	fallback()

try:
	debian_binary = arfile.getmember("debian-binary")
	x = open(os.path.join(dirpath,tree[0],"debian-binary"),"w")
	x.write(debian_binary.read())
	x.close()
except:
	print "Warning: Inconsistent package: Missing file debian-binary"
	pass

try:
	if "control.tar.gz" in arfile.getnames():
		sysobj = arfile.getmember("control.tar.gz")
		x = TarFile.gzopen(name="control.tar.gz",fileobj=sysobj,mode="r")
	else:
		sysobj = arfile.getmember("control.tar.bz2")
		x = TarFile.bz2open(name="control.tar.bz2",fileobj=sysobj,mode="r")
	x.extractall(os.path.join(dirpath,tree[1]))
	x.close()
except:
	print "Warning: Inconsistent package: Missing control file"
	pass

try:
	if "data.tar.gz" in arfile.getnames():
		dataobj = arfile.getmember("data.tar.gz")
		x = TarFile.gzopen(name="data.tar.gz",fileobj=dataobj,mode="r")
	else:
		dataobj = arfile.getmember("data.tar.bz2")
		x = TarFile.bz2open(name="data.tar.bz2",fileobj=dataobj,mode="r")
	x.extractall(os.path.join(dirpath,tree[2]))		
	x.close()
except:
	print "Warning: Inconsistent package: Missing data file"
	passs

try:
	metadata_files = [
		("safe",0),
		("ready",0),
			]
	xp = os.path.join(dirpath,tree[4])
	for i,j in metadata_files:
		with open(os.path.join(xp,i),"w") as metafile:
			metafile.write(str(j))
except:
	pass

execlist = []
icon = None
entry = DesktopEntry.DesktopEntry()

try:
	for i in desktop_list:
		x = os.path.join(dirpath,tree[2],i)
		if os.access(x,os.R_OK):
			try:
				entry.parse(x)
				_exec_args = shlex.split(entry.getExec())
				for arg in _exec_args:
					if arg != "%u": execlist.append(arg)
			except:
				pass
			finally:
				break
except:
	pass

for i in desktop_list:
	x = os.path.join(dirpath,tree[2],i)
	if os.access(x,os.R_OK):
		try:
			entry.parse(x)
			icon_name = IconTheme.getIconPath(entry.getIcon())
			print icon_name
			if os.access(icon_name,os.R_OK):
				print "Readable."
				icon = open(icon_name,'r')
				print icon
			elif os.access(os.path.join(dirpath,tree[2],icon_name)):
				icon = open(os.path.join(dirpath,tree[2],icon_name))
		except:
			pass
		finally:
			break

# CREATE RUNSCRIPT
try:
	handle = open(os.path.join(os.path.join(dirpath,tree[0]),"Run"),'w')
	depstr = str(testPackage.depends)

	depstr = depstr.replace("(","\n(")

	execstr = str(execlist)

	runscript = """#!/usr/bin/env python
from bundletools import BundleScript

_PKG_NAME = "%s"
_EXEC = %s
_PKG_DEPENDS = %s

def main():
	bundlescript = BundleScript(_PKG_NAME)

	if not bundlescript.get_metafile_value("safe"):
		bundlescript.issue_warning()
	bundlescript.check_dependencies(_PKG_DEPENDS)
	if bundlescript.get_metafile_value("ready"):
		bundlescript.deploy()
		bundlescript.run(_EXEC)

main()
	""" % (pkgname_clean + ".bun",execstr,depstr)

	handle.write(runscript)
	os.fchmod(handle.fileno(),0775)
	handle.close()
except:
	print "Could not create runscript. Quitiing."
	fallback()


# COMPRESS AND MOUNT

try:
	os.chdir(dirpath)
	static_name = os.path.join(tempdir,pkgname_clean)
	fn = static_name + ".bun"
	x = TarFile(fn,mode="w")
	for i in os.listdir("."):
		x.add(i) 
	x.close()

	os.chdir(tempdir)
	fn2 = static_name
	x = TarFile(fn2,mode="w")
	x.add(pkgname_clean + ".bun")
	if os.access(pkgname_clean + ".desktop",os.R_OK):
		os.chmod(pkgname_clean + ".desktop",0777)
		x.add(pkgname_clean + ".desktop")
	#try:
	#	os.symlink("/usr/share/applications","Applications")
	#	x.add("Applications")
	#except:
	#	pass
		y = x.getmember(pkgname_clean + ".desktop")
	x.close()

	subprocess.Popen(("/usr/lib/gvfs/gvfsd-archive","file="+fn2,"umask=777"))
	mount_dir = "%s/.gvfs/%s" % (os.getenv("HOME"),pkgname_clean)
	mounted_bun_path = os.path.join(mount_dir,pkgname_clean+".bun")

	if icon:
		icontmpfile = ""
		icontmpdir = os.path.join(hometempdir,"icons")
		if not os.path.isdir(icontmpdir):
			try:
				print "Creating", icontmpdir
				os.makedirs(icontmpdir)
			except:
				fallback()
		rndname_num = 0
		while icontmpfile == "": 
			if "temp_icon_" + str(rndname_num) not in os.listdir(icontmpdir):
				fh = open(os.path.join(icontmpdir,"temp_icon_" + str(rndname_num)),"w")
				fh.write(icon.read())
				fh.close()
				icontmpfile = os.path.join(icontmpdir,"temp_icon_" + str(rndname_num))
			rndname_num += 1
		print icontmpfile	
		subprocess.Popen(("gvfs-set-attribute","-t","string",mounted_bun_path,"metadata::custom-icon","file://"+icontmpfile))
		print "gvfs-set-attribute","-t","string",mounted_bun_path,"metadata::custom-icon","file://"+icontmpfile

	subprocess.Popen(("nautilus",mount_dir))
except:
	print "Could not create BUN archive. Quitting."
	fallback()

# REMOVE TEMPDIR

bundle_notify_msg_SUCCESS.show()
cleanup()
