#!/usr/bin/env python
##############################################################################
########################### setup.py for mlabwrap ############################
##############################################################################
## o author: Alexander Schmolck (a.schmolck@gmx.net)
## o created: 2003-08-07 17:15:22+00:40
## o last modified: $Date$

####################################################################
##### VARIABLES YOU MIGHT HAVE TO CHANGE FOR YOUR INSTALLATION #####
##### (if setup.py fails to guess the right values for them)   #####
####################################################################
VERSION_6_5_OR_LATER=0      # MUST SET TO 0 for matlab < v6.5
MATLAB_DIR=None             # e.g: '/usr/local/matlab'; 'c:/matlab6'
EXTRA_COMPILE_ARGS=None     # e.g: ['-G']
PLATFORM_DIR=None           # e.g: 'glnx86'; r'win32/microsoft/msvc60'

# hopefully these 3 won't need modification
MATLAB_LIBRARIES=None       # e.g: ['eng', 'mx', 'mat', 'mi', 'ut']
PYTHON_INCLUDE_DIR=None     # where to find Numeric/*.h

SUPPORT_MODULES= ["awmstools", "awmsmeta"] # set to [] if already 
                                           # installed

# DON'T FORGET TO DO SOMETHING LIKE:
#   export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/MATLAB_DIR/extern/lib/glnx86/
####################################################################
### NO MODIFICATIONS SHOULD BE NECESSARY BEYOND THIS POINT       ###
####################################################################
# *******************************************************************
from distutils.core import setup, Extension
from distutils.file_util import copy_file
import os, os.path, glob, re
import sys
if sys.version_info < (2,2):
    print >> sys.stderr, "You need at least python 2.2"
    sys.exit(1)

# windows
if sys.platform.startswith('win'):
    MATLAB_LIBRARIES = MATLAB_LIBRARIES or 'libeng libmx'.split()
    print >> sys.stderr, "WINDOZE INSTALL UNTESTED: best of luck!"
    if not MATLAB_DIR:
        try:
            MATLAB_DIR = glob.glob('c:/matlab*')[0]
        except IndexError:
            print >> sys.stderr, """\
ERROR: CAN'T FIND MATLAB DIR
please edit setup.py by hand and set MATLAB_DIR
"""
            sys.exit(1)
    PLATFORM_DIR = PLATFORM_DIR or 'win32/microsoft/msvc60'
# unices
else:
    MATLAB_LIBRARIES = MATLAB_LIBRARIES or \
                       'eng mx mat mi ut'.split()  #FIXME stdc++?
    # try to guess where matlab is
    if not MATLAB_DIR:
        try:
            guess = os.path.dirname(os.popen('which matlab').read()).\
                    replace('/bin','') or \
                    filter(None,
                           map(glob.glob, ['/usr/local/matlab*',
                                           '/opt/matlab*']))[0][0]
        except:
            print >> sys.stderr("FAILED GUESSING MATLAB_DIR, assume default")
            guess = '/usr/local/matlab'
        if os.path.exists(guess):
            MATLAB_DIR = guess
        else:
            print >> sys.stderr, """\
ERROR: CAN'T FIND MATLAB DIR
please edit setup.py by hand and set MATLAB_DIR
"""
            sys.exit(1)
    if sys.platform.startswith('sunos'):
        EXTRA_COMPILE_ARGS = EXTRA_COMPILE_ARGS or ['-G']
        PLATFORM_DIR = PLATFORM_DIR or "sol2"
    elif sys.platform.startswith('linux'):
        PLATFORM_DIR = PLATFORM_DIR or "glnx86"

MATLAB_LIBRARY_DIRS = [MATLAB_DIR + "/extern/lib/" + PLATFORM_DIR]
MATLAB_INCLUDE_DIRS = [MATLAB_DIR + "/extern/include"] #, "/usr/include"
DEFINE_MACROS = VERSION_6_5_OR_LATER and [('_V6_5_OR_LATER',1)] or None
setup (# Distribution meta-data
       name = "mlabwrap",
       version = "0.9b2",
       description = "A high-level bridge to matlab",
       author = "Alexander Schmolck",
       author_email = "A.Schmolck@gmx.net",
       url = "http://alexander.schmolck.org/python/code",
       py_modules = ["mlabwrap"] + SUPPORT_MODULES,
       ext_modules = [
           Extension('mlabrawmodule', ['mlabraw.cpp'],
              define_macros=DEFINE_MACROS,
              library_dirs=MATLAB_LIBRARY_DIRS ,
              libraries=MATLAB_LIBRARIES,
                      include_dirs=MATLAB_INCLUDE_DIRS + (PYTHON_INCLUDE_DIR and [PYTHON_INCLUDE_DIR] or []),
                      extra_compile_args=EXTRA_COMPILE_ARGS,
                      ),
           ]
      )
