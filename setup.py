#!/usr/bin/env python
# Variables you might have to change for your installation
MATLAB_DIR=None
EXTRA_COMPILE_ARGS=None
PYTHON_INCLUDE_DIR = None #XXX where to find Numeric/*.h 
from distutils.core import setup, Extension
from distutils.file_util import copy_file
import sys, os, os.path, shutil
import re
shove = lambda src, dst: copy_file(src, dst, preserve_mode=1, preserve_times=1)
if sys.version_info < (2,2):
    print >> sys.stderr, "You need at least python 2.2"
    sys.exit(1)
def whichAreMissing(modules):
    from distutils.version import StrictVersion as Version
    missing = {}
    for name, version in modules:
        try:
            module = __import__(name)
            if Version(module.__version__) < Version(version):
                raise ImportError
        except ImportError, AttributeError:
            missing[name] = 1
    return missing.keys()

# no modifications should be necessary beyond this point
if sys.platform.startswith('win'):
    print >> sys.stderr, """\
WINDOZE INSTALL VIA SETUP.PY CURRENTLY UNSUPPORTED
PLEASE CONTRIBUTE.
"""
    sys.exit(1)

# try to guess where matlab is
if not MATLAB_DIR:
    for path in ['/usr/local/matlab',
                 re.sub(r'/bin/.*', '', os.popen('which matlab').read())]:
        if os.path.exists(path):
            MATLAB_DIR = path
            break
    else:
        print >> sys.stderr, """\
ERROR: CAN'T FIND MATLAB DIR
please edit setup.py by hand and set MATLAB_DIR
"""

if sys.platform.startswith('sunos'):
    MATLAB_LIBRARY_DIRS = [MATLAB_DIR + "/extern/lib/sol2"]
    EXTRA_COMPILE_ARGS = ['-G'] #FIXME
elif sys.platform.startswith('linux'):
    MATLAB_LIBRARY_DIRS = [MATLAB_DIR + '/extern/lib/glnx86']
    


MATLAB_LIBRARIES = 'eng mx mat mi ut'.split()

#FIXME /usr/include
MATLAB_INCLUDE_DIRS = [MATLAB_DIR + "/extern/include", "/usr/include"]

requiredModules = [('awmsmeta', '0.1a1'),
                   ('awmstools', '0.7')]
missingModules = whichAreMissing(requiredModules)
# Hack to make the automatic building of sourceDists etc. easier
if os.getenv("BUILD_DIST"):
    print "BUILDING DIST"
    missingModules = [t[0] for t in requiredModules]
    print "added: %r"
if missingModules:
    for missingModule in missingModules:
        shove(os.path.join("others",missingModule + ".py"), "missing")
setup (# Distribution meta-data
       name = "mlabwrap",
       version = "0.9b1",
       description = "A high-level bridge to matlab",
       author = "Alexander Schmolck",
       author_email = "A.Schmolck@gmx.net",
       url = "http://alexander.schmolck.org/python/code",
       package_dir = {'': 'missing'},
       packages=['.'],
       ext_modules = 
           [Extension('mlabrawmodule', ['mlabraw.cpp'],
                      library_dirs=MATLAB_LIBRARY_DIRS ,
                      libraries=MATLAB_LIBRARIES,
                      include_dirs=MATLAB_INCLUDE_DIRS + (PYTHON_INCLUDE_DIR and [PYTHON_INCLUDE_DIR] or []),
                      extra_compile_args=EXTRA_COMPILE_ARGS,
                      ),
           ]
      )
shutil.rmtree("missing")
os.mkdir("missing")
