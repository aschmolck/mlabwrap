#!/usr/bin/env python
from distutils.core import setup, Extension
import sys, os, os.path
import re

# Variables you might have to change for your installation
MATLAB_DIR=None
EXTRA_COMPILE_ARGS=None

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

setup (# Distribution meta-data
       name = "pymat",
       version = "1.1",
       description = "A low-level interface to matlab",
       author = "Alexander Schmolck",
       author_email = "A.Schmolck@gmx.net",
       url = "http://alexander.schmolck.org/python/code", #FIXME
       # Description of the modules and packages in the distribution
       packages = [''],
       package_dir = {'': '.'},
       ext_modules = 
           [Extension('pymatmodule', ['pymat.cpp'],
                      library_dirs=MATLAB_LIBRARY_DIRS ,
                      libraries=MATLAB_LIBRARIES,
                      include_dirs=MATLAB_INCLUDE_DIRS,
                      extra_compile_args=EXTRA_COMPILE_ARGS,
                      ),
           ]
      )
