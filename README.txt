===============
mlabwrap v0.9b3
===============

copyright (c) 2003 Alexander Schmolck (A.Schmolck@gmx.net)
==========================================================

.. contents:: 


Description
-----------

A high-level python to matlab(tm) bridge. Let's matlab look like a normal
python library.

License
-------

mlabwrap is under MIT license, see LICENSE.txt. mlabraw is under a BSD-style
license, see the mlabraw.cpp.

Installation
------------

If you're lucky (linux; matlab **v6.5** with its libraries installed and
**in the library path**)::

  python setup.py install

If not, for example if your version is < **v6.5** or you installed matlab in
an unusual location, you'll have to edit ``setup.py`` (if that's the case and
you think its not specific to your particular installation, please share your
improvements with me). If the install proceeds but you get errors on
importing, see Troubleshooting.

Documentation
-------------
- for lazy people:
  
  >>> from mlabwrap import mlab; mlab.plot([1,2,3])

- for a complete description:
  see the doc_ dir or just run ``pydoc mlabwrap``
  
  .. _doc: doc/html/index.html

- for people who like tutorials:
  see below


Tutorial
--------

[This is adapted from an email I wrote someone who asked me about mlabwrap.]

Legend: [...] = omitted output

Let's say you want to do use matlab to calculate the singular value
decomposition of a matrix.  So first you import the `mlab` pseudo-module and
Numeric:


>>> from mlabwrap import mlab
>>> import Numeric

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

Notice that we only go 'U' back -- that's because python hasn't got something
like matlab's multiple value return. Since matlab functions can have
completely different behavior depending on how many output parameters are
requested, you have to specify explicitly if you want more than 1. So to get
'U' and also 'S' and 'V' you'd do:

>>> U, S, V = mlab.svd([[1,2],[1,3]], nout=3)

The only other possible catch is that matlab (to a good approximation)
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
directly converted, matlab functions can also return structs or indeed
classes and other types that cannot be converted into python
equivalents. However, rather than just giving up, mlabwrap just hides
this fact from the user by using proxies:
E.g. to create a netlab neural net with 2 input, 3 hidden and 1 output node:

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
automatically converted into the corresponding matlab-objects. So to obtain
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
underlying mlabraw interface to matlab is based).

this:

>>> A, B, C = mlab.svd([[1,2],[1,3]], 0, nout=3)

becomes this:

>>> session = pymat.open()
>>> pymat.put(session, [[1,2], [1,3]], "X")
>>> pymat.put(session, 0, "cheap")
>>> pymat.eval(session, '[A, B, C] = svd(X, cheap)')
>>> A = pymat.get(session, 'A')
>>> B = pymat.get(session, 'B')
>>> C = pymat.get(session, 'C')

Plus, there is virtually no error-reporting at all, if something goes wrong in
the `eval` step, you'll only notice because the subsequent `get` mysteriously
fails.


What's Missing?
---------------

- Untested under matlab 6.5 (which has seen an C-level interface change).
- Handling of as arrays of (array) rank 3 or more as well as
  non-double/complex arrays (currently everything is converted to
  double/complex for passing to matlab and passing non-double/complex from
  matlab is not not supported). Both should be reasonably easy to implement,
  but I currently don't need them.
- Better support for cells.


Implemenation Notes
-------------------

So how does it all work?

I've got a C extension module (a heavily bug-fixed and somewhat modified
version of pymat, an open-source, low-level python-matlab interface) to take
care of opening matlab sessions, sending matlab commands as strings to a
running matlab session and and converting Numeric arrays (and sequences and
strings...) to matlab matrices and vice versa. On top of this I then built a
pure python module that with various bells and whistles gives the impression
of providing a matlab "module".

This is done by a class that manages a single matlab session (of which
`mlab` is an instance) and creates methods with docstrings
on-the-fly. Thus, on the first call of ``mlab.abs(1)``, the wrapper looks
whether there already is a matching function in the cache. If not, the
docstring for ``abs`` is looked up in matlab and matlab's flimsy
introspection abilities are used to determine the number of output
arguments (0 or more), then a function with the right docstring is
dynamically created and assigned to ``mlab.abs``. This function takes care
of the conversion of all input parameters and the return values, using
proxies where necessary. Proxy are a bit more involved and the proxy
pickling scheme uses matlab's `save` command to create a binary version of
the proxy's contents which is then pickled, together with the proxy object
by python itself. Hope that gives a vague idea, for more info study the
source.

Troubleshooting
---------------
If on importing mlabwrap you get somthing like this::

 ImportError: libeng.so: cannot open shared object file: No such file or directory

then chances are that the relevant matlab libraries are not in you library
path. You can rectify this situation in a number of ways; let's assume your
running linux and that the libraries are in
``/usr/local/matlab/extern/lib/glnx86/``

1. As a normal user, you can append the path to LD_LIBRARY_PATH (under bash)::

    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/matlab/extern/lib/glnx86/

2. As root, you can either add the matlab library path to ``/etc/ld.so.conf``
   and run ``ldconfig``

3. Or, ugly but also works: just copy or symlink all the libraries to
   ``/usr/lib`` or something else that's in your library path.


Credits
-------

Andrew Sterian for writing pymat without this module would never have existed.

