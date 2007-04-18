==============
mlabwrap v1.0
==============

:copyright: 2003-2007 Alexander Schmolck
:date: 2007-04-10

..


.. contents:: 

Description
-----------
A high-level python to `Matlab(tm)`_ bridge. Let's Matlab look like a normal
python library.

    Thanks for your terrific work on this very-useful Python tool!

    -- George A. Blaha, Senior Systems Engineer, 
       Raytheon Integrated Defense Systems



.. _Matlab(tm): 
   http://www.mathworks.com



News
----

**2007-04-16** Added some more info for users experiencing problems with the
matlab engine in `Troubleshooting`_.

**2007-04-10** 1.0final is out! Compared to the last beta, setup.py should now
work better under windows (Borland C++ support, inter alia). Also included is
a work-around for an ipython bug that causes spurious error message when using
mlabwrap with some versions of ipython. 

This is the last version with optional Numeric support. Future versions of
mlabwrap will be hosted as a scikits project on scipy (see
<http://www.scipy.org/MlabWrap>), require numpy and adopt the scipy package
structure (i.e. ``import mlabwrap`` -> ``import scikits.mlabwrap``), which
also implies a change from distutils to setuptools. 

The source-forge hosted `project mailing list`_ will remain the prefered place
for users who seek support or want to provide feedback.

**Compatibility Note:** Since matlab is becoming increasingly less
``double``-centric, the default conversion rules might change in post 1.0
mlabwrap (even if such changes are introduced the old behavior will be
optionally available); so whilst using ``mlab.plot([1,2,3])`` rather than
``mlab.plot(array([1.,2.,3.]))`` is fine for interactive use as in the
tutorial below, the latter is recommended for production code.


License
-------

mlabwrap is under MIT license, see LICENSE.txt. mlabraw is under a BSD-style
license, see the mlabraw.cpp.

Installation
------------

If you're lucky (linux, Matlab binary in ``PATH`` and the Matlab libraries in
``LD_LIBRARY_PATH``)::

  python setup.py install

If the Matlab libraries are not in your ``LD_LIBRARY_PATH`` the above command
will print out a message how to rectify this (you will need to enter something
like ``export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/MatlabR14/bin/glnx86`` in
the shell (assuming you're using bash or zsh); and adding that line to your
``~/.bashrc`` (or equivalent) is presumably a good idea).

If things do go awry, see Troubleshooting_.

Although I myself use only linux, mlabwrap should work with python>=2.3 (even
python 2.2, with minor coaxing) and either numpy_ (recommended) or Numeric
(obsolete) installed and Matlab 6, 6.5 or 7 under unix(tm), OS X (tm) and
windows (see `OS X`) on 32- or 64-bit machines.

The windows install will for some reason complain that it can't delete a
tempory file, but this message is harmless (just delete the file by hand, if
necessary).

Documentation
-------------
- for lazy people
  
  >>> from mlabwrap import mlab; mlab.plot([1,2,3],'-o')

  .. image:: ugly-plot.png
     :alt: ugly-plot

- a slightly prettier example

  >>> from mlabwrap import mlab; from numpy import *
  >>> xx = arange(-2*pi, 2*pi, 0.2)
  >>> mlab.surf(subtract.outer(sin(xx),cos(xx)))

  .. image:: surface-plot.png
     :alt: surface-plot

- for a complete description:
  see the doc_ dir or just run ``pydoc mlabwrap``
  
  .. _doc: doc/html/index.html

- for people who like tutorials:
  see below


Tutorial
--------

[This is adapted from an email I wrote someone who asked me about mlabwrap.]

Legend: [...] = omitted output

Let's say you want to do use Matlab(tm) to calculate the singular value
decomposition of a matrix.  So first you import the `mlab` pseudo-module and
Numeric:


>>> from mlabwrap import mlab
>>> import numpy

Now you want to find out what the right function is, so you simply do:

>>> mlab.lookfor('singular value')
GSVD   Generalized Singular Value Decompostion.
SVD    Singular value decomposition.
[...]

Then you look up what `svd` actually does, just as you'd look up the
docstring of a python function:

>>> help(mlab.svd)
mlab_command(*args, **kwargs)
 SVD    Singular value decomposition.
    [U,S,V] = SVD(X) produces a diagonal matrix S, of the same
    dimension as X and with nonnegative diagonal elements in
[...]

Then you try it out:

>>> mlab.svd(array([[1,2], [1,3]]))
array([[ 3.86432845],
      [ 0.25877718]])

Notice that we only got 'U' back -- that's because python hasn't got something
like Matlab's multiple value return. Since Matlab functions can have
completely different behavior depending on how many output parameters are
requested, you have to specify explicitly if you want more than 1. So to get
'U' and also 'S' and 'V' you'd do:

>>> U, S, V = mlab.svd([[1,2],[1,3]], nout=3)

The only other possible catch is that Matlab (to a good approximation)
basically represents everything as a double matrix. So there are no
scalars, or 'flat' vectors. They correspond to 1x1 and 1xN matrices
respectively. So, when you pass a flat vector or a scalar to a
mlab-function, it is autoconverted. Also, integer values are automatically
converted to double floats. Here is an example:

>>> mlab.abs(-1)
array([       [ 1.]])

Strings also work as expected:

>>> mlab.upper('abcde')
'ABCDE'

However, although matrices and strings should cover most needs and can be
directly converted, Matlab functions can also return structs or indeed
classes and other types that cannot be converted into python
equivalents. However, rather than just giving up, mlabwrap just hides
this fact from the user by using proxies:
E.g. to create a netlab_ neural net with 2 input, 3 hidden and 1 output node:

>>> net = mlab.mlp(2,3,1,'logistic')

Looking at `net` reveals that is a proxy:

>>> net
<MLabObjectProxy of matlab-class: 'struct'; internal name: 'PROXY_VAL0__';
has parent: no>
    type: 'mlp'
     nin: 3
 nhidden: 3
    nout: 3
    nwts: 24
   outfn: 'linear'
      w1: [3x3 double]
      b1: [0.0873 -0.0934 0.3629]
      w2: [3x3 double]
      b2: [-0.6681 0.3572 0.8118]

When `net` or other proxy objects a passed to mlab functions, they are
automatically converted into the corresponding Matlab-objects. So to obtain
a trained network on the 'xor'-problem, one can simply do:

>>> net = mlab.mlptrain(net, [[1,1], [0,0], [1,0], [0,1]], [0,0,1,1], 1000)

And test with:

>>> mlab.mlpfwd(net2, [[1,0]])
array([       [ 1.]])
>>> mlab.mlpfwd(net2, [[1,1]])
array([       [  7.53175454e-09]])

As previously mentioned, normally you shouldn't notice at all when you are
working with proxy objects; they can even be pickled (!), although that is
still somewhat experimental.

mlabwrap also offers proper error handling and exceptions! So trying to
pass only one input to a net with 2 input nodes raises an Exception:


>>> mlab.mlpfwd(net2, 1)
Traceback (most recent call last):
[...]
mlabraw.error: Error using ==> mlpfwd
Dimension of inputs 1 does not match number of model inputs 2


Warning messages (and messages to stdout) are also displayed:

>>> mlab.log(0)
Warning: Log of zero.
array([       [             -inf]])


Comparison to other existing modules
------------------------------------

To get a vague impression just *how* high-level all this, consider attempting to
do something similar to the first example with pymat (upon which the
underlying mlabraw interface to Matlab(TM) is based).

this:

>>> A, B, C = mlab.svd([[1,2],[1,3]], 0, nout=3)

becomes this:

>>> session = pymat.open()
>>> pymat.put(session, "X", [[1,2], [1,3]])
>>> pymat.put(session, "cheap", 0)
>>> pymat.eval(session, '[A, B, C] = svd(X, cheap)')
>>> A = pymat.get(session, 'A')
>>> B = pymat.get(session, 'B')
>>> C = pymat.get(session, 'C')

Plus, there is virtually no error-reporting at all, if something goes wrong in
the `eval` step, you'll only notice because the subsequent `get` mysteriously
fails. And of course something more fancy like the netlab example above (which
uses proxies to represent matlab class instances in python) would be
impossible to accomplish in pymat in a similar manner.

However *should* you need low-level access, then that is equally available
(and *with* error reporting); basically just replace ``pymat`` with
``mlabraw`` above and use ``mlab._session`` as session), i.e

>>> from mlabwrap import mlab
>>> import mlabraw
>>> pymat.put(mlab._session, "X", [[1,2], [1,3]])
[...]

Before you resort to this you should ask yourself if it's really a good idea;
the inherent overhead associated with Matlab's C interface appears to be quite
high, so the additional python overhead shouldn't normally matter much -- if
efficiency becomes an issue it's probably better to try to chunk together
several matlab commands in an ``.m``-file in order to reduce the number of
matlab calls.

What's Missing?
---------------

- Handling of as arrays of (array) rank 3 or more as well as
  non-double/complex arrays (currently everything is converted to
  double/complex for passing to Matlab and passing non-double/complex from
  Matlab is not not supported). Both should be reasonably easy to implement,
  but I currently don't need them.
- Better support for cells.


Implementation Notes
--------------------

So how does it all work?

I've got a C extension module (a heavily bug-fixed and somewhat modified
version of pymat, an open-source, low-level python-matlab interface) to take
care of opening Matlab sessions, sending Matlab commands as strings to a
running Matlab session and and converting Numeric arrays (and sequences and
strings...) to Matlab matrices and vice versa. On top of this I then built a
pure python module that with various bells and whistles gives the impression
of providing a Matlab "module".

This is done by a class that manages a single Matlab session (of which
`mlab` is an instance) and creates methods with docstrings
on-the-fly. Thus, on the first call of ``mlab.abs(1)``, the wrapper looks
whether there already is a matching function in the cache. If not, the
docstring for ``abs`` is looked up in Matlab and Matlab's flimsy
introspection abilities are used to determine the number of output
arguments (0 or more), then a function with the right docstring is
dynamically created and assigned to ``mlab.abs``. This function takes care
of the conversion of all input parameters and the return values, using
proxies where necessary. Proxy are a bit more involved and the proxy
pickling scheme uses Matlab's `save` command to create a binary version of
the proxy's contents which is then pickled, together with the proxy object
by python itself. Hope that gives a vague idea, for more info study the
source.

Troubleshooting
---------------

matlab not in path
''''''''''''''''''
``setup.py`` will call ``matlab`` in an attempt to query the version and other
information relevant for installation, so it has to be in your ``PATH``
*unless* you specify everything by hand in ``setup.py``. Of course to be able
to use ``mlabwrap`` in any way ``matlab`` will have to be in your path anyway
(unless that is you set the environment variable ``MLABRAW_CMD_STR`` that
specifies how exactly Matlab(tm) should be called).


Library path not set
''''''''''''''''''''

If on importing mlabwrap you get somthing like this::

 ImportError: libeng.so: cannot open shared object file: No such file or directory

then chances are that the relevant Matlab libraries are not in you library
path. You can rectify this situation in a number of ways; let's assume your
running linux and that the libraries are in ``/opt/matlab/bin/glnx86/``
(**NOTE**: *this used to be ``/opt/matlab/extern/lib/glnx86/`` in versions
before 7; confusingly enough the directory still exists, but the required
libraries no longer reside there!*) 

1. As a normal user, you can append the path to LD_LIBRARY_PATH (under bash)::

    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/matlab/bin/glnx86/

2. As root, you can either add the Matlab library path to ``/etc/ld.so.conf``
   and run ``ldconfig``

3. Or, ugly but also works: just copy or symlink all the libraries to
   ``/usr/lib`` or something else that's in your library path.


Can't open engine
'''''''''''''''''

If you see something like ``mlabraw.error: Unable to start MATLAB(TM) engine``
then you may be using an incompatible C++ compiler (or version), or if you're
using unix you might not have ``csh`` installed under ``/bin/csh``, see below.
Try if you can get the ``engdemo.c`` file to work that comes with your Matlab
installation -- copy it to a directory where you have write access and do
(assuming Matlab is installed in /opt/MatlabR14 and you're running unix,
otherwise modify as requird)::

  mex -f /opt/MatlabR14/bin/engopts.sh engdemo.c
  ./engdemo

if you get ``Can't start MATLAB engine`` chances are you're trying to use a
compiler version that's not in Mathworks's `list of compatible compilers`_ or
something else with your compiler/Matlab installation is broken that needs to
be resolved before you can successfully build mlabwrap. Chances are that you
or you institution pays a lot of money to the Mathworks, so they should be
happy to give you some tech support. Here's what some user who recently
(2007-02-04) got Matlab 7.04's mex support to work under Ubuntu Edgy after an
exchange with support reported back; apart from installing gcc-3.2.3, he did
the following::

  The code I'd run (from within Matlab) is...
  > mex -setup;     # then select: 2 - gcc Mex options
  > optsfile = [matlabroot '/bin/engopts.sh'];
  > mex -v -f optsfile 'engdemo.c';
  > !./engdemo;

**Update** John Bender reports that under unix csh needs to be installed in
``/bin/csh`` for the matlab external engine to work -- since many linux
distros don't install csh by default, you might have to do something like
``sudo apt-get install csh`` (e.g. under ubuntu or other debian-based
systems). He also pointed out this helpful `engdemo troubleshooting`_ page at
the Mathworks(tm) site.



Old Matlab version
''''''''''''''''''
If you get something like this on ``python setup.py install``::

 mlabraw.cpp:634: `engGetVariable' undeclared (first use this function)

Then you're presumably using an old version of Matlab (i.e. < 6.5);
``setup.py`` ought to have detected this though (try adjusting
``MATLAB_VERSION`` by hand a write me a bug report).


OS X
''''

Josh Marshall tried it under OS X and sent me the following notes (thanks!).

Notes on running
................

- Before running python, run::

      export  DYLD_LIBRARY_PATH=$DYLD_LIBRARY_PATH$:/Applications/MATLAB701/bin/mac/
      export MLABRAW_CMD_STR=/Applications/MATLAB701/bin/matlab

- As far as graphics commands go, the python interpreter will need to  be run
  from within the X11 xterm to be able to display anything to the  screen.
  ie, the command for lazy people

  >>> from mlabwrap import mlab; mlab.plot([1,2,3],'-o')

  won't work unless python is run from an xterm, and the matlab startup
  string is
  changed to::

      export MLABRAW_CMD_STR="/Applications/MATLAB701/bin/matlab -nodesktop"

Windows
'''''''

I'm thankfully not using windows myself, but I try to keep mlabwrap working
under windows, for which I depend on the feedback from windows users. 

Since there are several popular C++ compilers under windows, you might have to
tell setup.py which one you'd like to use (unless it's VC 7).

George A. Blaha sent me a patch for Borland C++ support; search for "Borland
C++" in setup.py and follow the instructions.

Dylan T Walker writes mingw32 will also work fine, but for some reason
(distuils glitch?) the following invocation is required::

    > setup.py build --compiler=mingw32
    > setup.py install --skip-build



Support and Feedback
--------------------

Private email is OK, but the preferred way is via the `project mailing list`_

.. _project mailing list:
   http://lists.sourceforge.net/lists/listinfo/mlabwrap-user

Download
--------

<http://sourceforge.net/projects/mlabwrap/>

(P.S. the activity stats are bogus -- look at the release dates).


Credits
-------

Andrew Sterian for writing pymat without which this module would never have
existed. 

Matthew Brett contributed numpy compatibility and nice setup.py improvements
(which I adapted a bit) to further reduce the need for manual user
intervention for installation. 

I'm only using linux myself -- so I gratefully acknowledge the help of Windows
and OS X users to get things running smoothly under these OSes as well;
particularly those who provided patches to setup.py or mlabraw.cpp (Joris van
Zwieten, George A. Blaha and others).

Matlab is a registered trademark of `The Mathworks`_.

.. _The Mathworks: 
   http://www.mathworks.com

.. _engdemo troubleshooting:
   http://www.mathworks.com/access/helpdesk/help/techdoc/index.html?/access/helpdesk/help/techdoc/matlab_external/f39903.html

.. _numpy:
   http://numpy.scipy.org

.. _netlab:
   http://www.ncrg.aston.ac.uk/netlab/

.. _list of compatible compilers:
   http://www.mathworks.com/support/tech-notes/1600/1601.html

.. image:: http://sourceforge.net/sflogo.php?group_id=124293&amp;type=5
   :alt: sourceforge-logo
   :target: http://sourceforge.net/projects/mlabwrap/

