import apt.debfile
from os import popen,access,mkdir,walk,path,chdir,symlink,tempnam,tmpfile,R_OK,W_OK,system,getcwd,makedirs,chmod,fchmod,remove,stat,fstat,listdir
import sys
import tarfile
import subprocess
from stat import *

DIRECTORY_METADATA_STANDARD = "BundleData"
DIRECTORY_PKG_STANDARD = "Data"
DIRECTORY_SCRIPTS_STANDARD = "Ubuntu"
DIRECTORY_ICONS_STANDARD = "Icons"

__all__ = ["BundleData", "BundleJail", "BundleScript","launch_bundle"]

class BundleData(tarfile.TarFile):
	def __init__(self,bundle_file):
		tarfile.TarFile.__init__(self,name=bundle_file,mode='r')

		self.DIRECTORY_METADATA = DIRECTORY_METADATA_STANDARD
		self.DIRECTORY_PKG = DIRECTORY_PKG_STANDARD
		self.DIRECTORY_SCRIPTS = DIRECTORY_SCRIPTS_STANDARD
		self.DIRECTORY_ICONS = DIRECTORY_ICONS_STANDARD
	
		self.bundle_file = path.abspath(bundle_file)
	
		# PKGLIST
		self.filenames = self.getnames()
		self.pkg_list = []
		for i in self.filenames:
			if i != self.DIRECTORY_PKG and i[:len(self.DIRECTORY_PKG)] == self.DIRECTORY_PKG:
				self.pkg_list.append(self.getmember(i))
		desktop_list = []
		for i in self.pkg_list:
			if path.splitext(i.name)[1] == ".desktop":
				desktop_list.append(i)
				desktop_app = True
	
		# TEMPORARY DIRECTORY - FILES
		self.temporary_directory = tempnam(None,"bun")
		self.temporary_directory_payload = path.join(self.temporary_directory,"payload")
		makedirs(self.temporary_directory_payload)
		self.log = open(path.join(self.temporary_directory,"bundle.log"),"w")

		# WRITER
		self.writer = tarfile.TarFile.open(path.join(self.temporary_directory,"writer.tar"),"w")
		
	def get_metafile_value(self,path_to_metafile):
		metafile = self.extractfile(self.getmember(path.join(self.DIRECTORY_METADATA,path_to_metafile)))
		value = metafile.read()
		metafile.close()
		return value
	
	def put_metafile_value(self,path_to_metafile,value):
		metafile = tempfile()
		metafile.write(value)
		with self.writer.gettarinfo(fileobj=metafile,arcname=path_to_metafile) as tarinfo:
				self.writer.addfile(tarinfo)

	def deploy(self):
		for i in self.pkg_list:
			target = path.join(self.temporary_directory_payload,i.name[len(self.DIRECTORY_PKG)+1:])
			reldir = path.split(target)[0]
			if i.isdir():
				mkdir(target,i.mode)
			elif i.isfile():
				xf = self.extractfile(i)
				with open(path.join(target),"w") as newfile:
					newfile.write(xf.read())
					fchmod(newfile.fileno(),i.mode)
			elif i.issym():
				xp = path.abspath(path.join(reldir,i.linkpath))
				symlink(xp,target)

	def close(self):
		tarfile.TarFile.close(self)
		self.writer.close()

		
class BundleJail(BundleData):
	def __init__(self,bundle_file):
		BundleData.__init__(self,bundle_file)
		self.temporary_directory_jail = path.join(self.temporary_directory,"jail")
		mkdir(self.temporary_directory_jail)
		self.rootdir = "/"
		self.runable = 0
		self.force_run = 0

	def getfile(self,filepath):
		xp = path.join(self.temporary_directory_payload,filepath)
		rxp = path.join(self.temporary_directory_jail,filepath)
		modebits = 0777
		with open(rxp,"w") as newfile:
			oldfile = open(xp,"r")
			newfile.write(oldfile.read())
			modebits = S_IMODE(fstat(oldfile.fileno()).st_mode)
			oldfile.close()
			fchmod(newfile.fileno(),modebits)

	def deploy(self):
		BundleData.deploy(self)
		cwd = getcwd()
		filelist = []
		for i in self.pkg_list:
			rxp = i.name[len(self.DIRECTORY_PKG)+1:]
			filelist.append(rxp)
		if self.temporary_directory_jail == None: return False
		try:
			if not access(self.temporary_directory_jail,R_OK): mkdir(self.temporary_directory_jail)
			if not access(self.temporary_directory_jail,W_OK) and access(self.rootdir,R_OK): return False
			chdir(self.temporary_directory_jail)
	
			for root, dirs, files in walk(self.rootdir):
				rmlist = []
				#print "CWD  ", root

				# Link system directories
				for x in dirs:
					xp = path.abspath(path.join(root,x))
					rxp = xp[1:]
					if rxp not in filelist:
						#print "LNK  ", rxp
						symlink(xp,rxp)
						rmlist.append(x)
					else: # Create local directories
						#print "MKD  ", rxp
						mkdir(rxp)
				for x in rmlist:
					dirs.remove(x)
				
				# Link system files
				exclude_list = []
				for x in files:
					xp = path.abspath(path.join(root,x))
					rxp = xp[1:]
					if rxp not in filelist:
						#print "LNK  ", rxp
						symlink(xp,rxp)
					else:   # Get local version
						#print "GET  ", rxp
						self.getfile(rxp)
						exclude_list.append(rxp)

				# Get local files
				if root[1:] in filelist:
					rp = path.join(self.temporary_directory_payload,root[1:])
					for x in listdir(rp):
						rxp = path.abspath(path.join(root,x))[1:]
						if rxp not in exclude_list and path.isfile(path.join(rp,x)):
							#print "GET  ", rxp
							self.getfile(rxp)

			self.runable = 1 
			return True
		except:
			print "Broke."
			return False
		finally:
			chdir(cwd)	

	def run(self,executable):
		if not self.runable or self.force_run: return False
		proc = subprocess.Popen(["fakechroot","chroot",self.temporary_directory_jail] + executable,stdout=subprocess.PIPE)
		proc.wait()
		self.log.write(proc.stdout.read())
		
		
class BundleScript(BundleJail):
	def __init__(self,bundle_file):
		BundleJail.__init__(self,bundle_file)

	def issue_warning(self):
		print "Warning! This program has been downloaded from the internet. It might compromise your system security."
	    self.put_metafile_value("safe",1)	

	def check_dependencies(self,deplist):
		pass


def launch_bundle(bundlepath):
	bundlepath = path.abspath(bundlepath)
	directory,filename = path.split(bundlepath)
	if not access(bundlepath,R_OK): return False
	cwd = getcwd()
	chdir(directory)
	with BundleData(bundlepath) as bundle:
		scrpt = bundle.extractfile(bundle.getmember(path.join(bundle.DIRECTORY_SCRIPTS,"Run")))
		xnam = tempnam()
		with open(xnam,"w") as scrptfile:
			scrptfile.write(scrpt.read())
		chmod(xnam,0777)
		try:
			system(xnam)
			return True
		except:
			return False
		finally:
			chdir(cwd)
			remove(xnam)
			system("rm -R /tmp/bun*")		

	

