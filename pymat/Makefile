# Makefile for pymat on redhat-7.1 i386 and python2.1
# (also works for python1.5, just change the PY and the 
# NUMPY value
## NumPy and Python header locations
NUMPY = /usr/include/python2.2/Numeric
PY=/usr/include/python2.2

# python module install site
PYMODINST = /usr/lib/python2.2/site-packages

## matlab header and lib locations
MATLAB = /usr/local/matlab
MATLABLIB = $(MATLAB)/extern/lib/glnx86
MATLINK = -L$(MATLABLIB) -leng -lmx -lmat -lmi -lut
MATINC = -I/usr/include -I$(MATLAB)/extern/include  -I$(NUMPY) -I$(PY)

## for testing pymat module: set LD_LIBRARY_PATH to include 
LD_LIB =  $(LD_LIBRARY_PATH):$(MATLABLIB)

## ---------------------------------------------------------------

pymatmodule.so: pymat.o
	g++ -shared -o pymatmodule.so pymat.o $(MATLINK)

pymat.o: pymat.cpp
	g++ -c pymat.cpp -o pymat.o $(MATINC) 

clean:
	rm -f pymatmodule.so pymat.o

install: pymatmodule.so
	install -c pymatmodule.so $(PYMODINST)
test: pymatmodule.so
	 LD_LIBRARY_PATH=$(LD_LIB) pymat-test.py
