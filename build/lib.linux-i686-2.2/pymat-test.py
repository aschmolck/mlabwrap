#!/usr/bin/python
# Simple test file for the PyMat interface

import pymat
from Numeric import *
x = array([1, 2, 3, 4, 5, 6])
H = pymat.open()
pymat.put(H, 'x', x)
pymat.eval(H, 'y = dct(x)')

y = pymat.get(H, 'y')
pymat.close(H)

expect = asarray([8.573214099741124e+000,
                  -4.162561795878958e+000,
                  -1.785561006679121e-015,
                  -4.082482904638622e-001,
                  -1.638955159695808e-015,
                  -8.007889124033019e-002])
err = sum((y-expect)*(y-expect)) 
print 'Norm of the error is:', err
if err < 1e-15:
  print "(That's pretty small -- the test passes)"
else:
  print "UMMM...THAT'S A BIT BIG! The test has failed."
  
