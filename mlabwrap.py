##############################################################################
################ mlab_direct: transparently wraps matlab(tm) #################
##############################################################################
##
## o author: Alexander Schmolck (a.schmolck@gmx.net)
## o created: 2002-05-29 21:51:59+00:40
## o last modified: $Date$
## o keywords: matlab wrapper
## o license: LGPL
## o TODO:
##   - issues to deal with: return casts (ints can only be passed as
##     arrays etc)., multiple value returns, special commands...
##   - assignment commands should be guessed as nout=0 automatically
## o XXX:
##   - allow switching between Numeric arrays an my wonderful matrix class
##   - autosync_dirs is a bit of a hack...
##   - matlab(tm) unhelpfully returns array([0.]) for empty 0x1 arrays!!!
##     (should we try to do a workaround for this (and maybe other yucky
##     things?))


## FIXME: - split and so on is crap: implement decent way to do it
##          implement hashes for name-> casts,nout etc.
##        - foo = legend vs. legend off
"""A wrapper for matlab, giving almost transparent access to matlab.

More precisely, a wrapper around a wrapper:  Andrew Sterian's pymat
(http://claymore.engineer.gvsu.edu/~steriana/Python/pymat.html)


Limitations
    - The return values of the matlab functions must be 2D or 1D arrays.
    - There isn't proper error handling, because the underlying pymat doesn't
      have proper error handling either.

Tested under matlab v6r12 and python2.2.1, but should also work for earlier
versions.

See the docu of `MLabDirect`. 
"""

__version__ = "$Revision$"

import os, sys, re
import Numeric
import pymat

# the following lines are just there for standaloness and downwards-compat.
#from awmstools import DEBUG_P, iupdate
DEBUG_P = lambda *args, **kwargs:None
def iupdate(d, e):
    """Destructively update dict `d` with dict `e`."""
    d.update(e)
    return d
try:     __metaclass__ = type
except:  print "Warning using python version < 2.2"
    
class MLabDirect:
    """This implements a powerful and simple to use wrapper that makes using
    matlab(tm) from python almost completely transparent. To use simply do:
    
    >>> mlab = MLabDirect()

    and then just use whatever matlab command you like as follows:
    
    >>> mlab.plot(range(10), 'x')

    You can do more than just plotting:

    >>> mlab.sort([3,1,2])
    array([ 1.,  2.,  3.])

    For names that are reserved in python (like print) do:

    >>> mlab.print_()

    There are two synataxes in matlab that have no direct equivalent in
    python:

    Special "Command Syntax" as alternative to function syntax

        In matlab some commands have an (usually additional) special call
        syntax without ``hold('on')`` and ``hold on``

    Multiple value returns
    
        It makes a difference how many variable you assign to a function. For
        example, if you say ``a = sort([3,1,2])`` you will just receive the
        sorted array, but if you do ``[a,b] = sort([3,1,2])`` you will receive
        the sorted array as ``a`` and the new order of the elements as ``b``.
        Similarly, also unlike python not every "function" returns a value and
        so it is an error to say
    
    For matlab(tm)'s idiosyncratic non-function syntax (e.g. ``hold on``) you
    can use the following shortcut:
    
    >>> mlab.hold_on() 

    along the same lines ``hold`` translates to:

    >>> mlab.hold()

    #XXX this is a stupid example, because hold('on') also works...
    

    If you need to emulate multiple value return, do:

    >>> mlab.sort([3,1,2], nout=2)
    (array([ 1.,  2.,  3.]), array([ 2.,  3.,  1.]))
    
    In almost all cases that should be enough --i f you need to emulate
    multiple return values and other trickier things, then get raw with
    ``mlab._do``, or build your child class that handles what you want.

    Examples:
    
    >>> mlab._do('a = [1,2,3]', nout=0)
    >>> mlab._get('a')
    array([ 1.,  2.,  3.])

    The sort example above could less conviniently be written as:
    
    >>> mlab._do('sort', [3,1,2])
    array([ 1.,  2.,  3.])
    
    """
    
    def __init__(self, splitter="_", autosync_dirs=1):
        """Create a new matlab(tm) wrapper object with its own session.

        :Paramters:
        
        - `splitter` is a regexp that's used to find out whether a command
          needs refidling into into matlab-idiosyncratic syntax (e.g. if
          splitter is ``"_"``, ``hold_on()`` gets translated ``hold on``
          rather than ``hold_on()``).XXX

        - `autosync_dirs` specifies whether the working directory of the
          matlab session should be kept in sync with that of python.
        """
        self._session = pymat.open()
        self._command_cache = {}
        self.autosync_dirs = autosync_dirs
        self.splitter = splitter
    def __del__(self):
        pymat.close(self._session)
    def _do(self, cmd, *args, **kwargs):
        """Semi-raw execution of a matlab command.
        
        Smartly handle calls to matlab, figure out what to do with `args`,
        and when to use function call syntax and not.
        
        If no `args` are specified ``cmd`` not ``result = cmd()`` form is used
        in Matlab -- this also makes literal matlab commands legal
        (eg. cmd=``get(gca, 'Children')``).

        If `nout=0` is specified, the matlab command is executed as
        procedure, otherwise it is executed as function (default), nout
        specifying how many values should be returned (default 1).

        `cast` specifies which typecast should be applied to the result
        (e.g. `int`), it defaults to none.

        XXX: should we add `parens` parameter?
        """
        self._session = self._session or pymat.open()
        # HACK        
        if self.autosync_dirs:
            pymat.eval(self._session,  'cd %s' % os.getcwd())
        nout =  kwargs.get('nout', 1)
        argnames = []
        for arg, count in zip(args, xrange(sys.maxint)):
            argnames.append('arg%d__' % count)
            # have to convert these by hand
            if   isinstance(arg, (int, float, long, complex)):
                pymat.eval(self._session, '%s=%r' % (argnames[-1], arg))
            #FIXME what about unicode and other seq-thingies?
            elif isinstance(arg, (Numeric.ArrayType, list, tuple, str)):
                pymat.put(self._session,  argnames[-1], arg)
            else:
                raise TypeError("Illegal argument type (%s) for %d. argument" %
                                (type(arg), type(count)))
        if args:
            cmd = "%s(%s)" % (cmd, ", ".join(argnames))
        # got three cases for nout:
        # 0 -> None, 1 -> val, >1 -> [val1, val2, ...]
        if nout == 0:
            pymat.eval(self._session, cmd)
            res = None
        # deal with matlab-style multiple value return
        else:
            resSL = ((["RES%d__" % i for i in range(nout)]))
            pymat.eval(self._session, '[%s]=%s' % (", ".join(resSL), cmd))
            res = []
            for resS in resSL:
                res.append(pymat.get(self._session, resS))
                pymat.eval(self._session, "clear('%s')" % resS)
            # nout = 1 ==> return ``val``, not ``[val]``
            if nout == 1:
                res = res[0]
            else: # casting to tuple is nicer than dealing with list
                res = tuple(res)
        pymat.eval(self._session, "clear('%s')" % "', '".join(argnames))
        if kwargs.has_key('cast'):
            if nout == 0:
                raise TypeError("Can't cast: 0 nout")
            return kwargs['cast'](res)
        else:
            return res
    def _get(self, name):
        return pymat.get(self._session, name)
    def __getattr__(self, attr):
        
        if self._command_cache.has_key(attr):
            return self._command_cache[attr]
        # print_ -> print
        if attr[-1] == "_":
            cmd = attr[:-1]
        else:
            cmd = attr
        typ = self._do("exist('%s')" % attr)
        doc = self_do("help('%s')" % cmd)
        if   typ == 0: # doesn't exist
            raise AttributeError("No such matlab object: %s" % attr)
        elif typ == 5: # builtin
            callSigRE = re.compile(r"""
                 # either
                 (?:
                     # FOO...
                     (?:^\s*)
                   |
                   (?:
                      
                         # A = FOO...
                         (?P<argout1>[A-Z]+)
                       |                     
                         # [A,B] = FOO...
                         \[(?:(?P<argout2>[A-Z]+),\s+)+\]
                   
                   )\s+=\s+
                 )
                 # the command name itself, upcased
                 %s
                 # either
                 (?: 
                     # FOO BAR QUUX (command syntax; this re doesn't work for
                     # pathological cases like `print` and `delete`)
                     (?:\s+(?P<argin1>[A-Z]*))+\s
                  |
                     # FOO(BAR, ...) (function call syntax)
                     (?:
                         \(
                          (?P<argin2>
                           (?:
                            (?:\.{3})
                            |
                            (?:['\w+]),\s+
                           )+?
                          )
                         \)
                     )
                 )
            """ % attr.upper(), re.X)
        else:
            nout = self._do("nargout('%s')" % attr)
            #nin  = self._do("nargin('%s')" % attr)
        def mlab_command(*args, **kwargs):
            return self._do(cmd, *args, **iupdate({'nout': nout}, kwargs))
        mlab_command.__doc__ = doc
        self._command_cache[attr] = mlab_command
        return mlab_command
        
#mlab = MLabDirect()
__all__ = MLabDirect
