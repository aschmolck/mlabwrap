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
##   - is there a way to get ``display(x)`` as a string (apart from using
##     diary?)
## o XXX:
##   - better error reporting: test for number of input args etc.
##   - allow switching between Numeric arrays an my wonderful matrix class
##   - autosync_dirs is a bit of a hack...
##   - pymat unhelpfully returns array([0.]) for empty 0x1 arrays
##     (e.g. zeros(0,1))!!!  (should we try to do a workaround for this?)
## o !!!:
##   - matlab complex arrays are intelligently of type 'double'
##   - ``class('func')`` but ``class(var)``

"""A wrapper for matlab, giving almost transparent access to matlab.

More precisely, a wrapper around a wrapper:  Andrew Sterian's pymat
(http://claymore.engineer.gvsu.edu/~steriana/Python/pymat.html)


Limitations
    - The return values of the matlab functions must be 2D or 1D arrays or
      strings (Well, there is support for arbitrary matlab classes for which
      proxy objects are created, but that is experimental, so don't complain
      if horrible things happen:)
      
    - There isn't good error handling, because the underlying pymat doesn't
      have good error handling either.
      
    - Matlab doesn't know scalars, so array([1]) and [1] are the same.
      Consequently all functions where on might expect a scalar to be returned
      will return a 1x1 array instead. However, unlike in pymat (where they
      cause segfaults), scalars are automatically converted to arrays where
      necessary.

Tested under matlab v6r12 and python2.2.1, but should also work for earlier
versions.

See the docu of `MLabDirect`. 
"""

__version__ = "$Revision$"

import os, sys, re
import Numeric
import pymat
import weakref

# the following lines are just there for standaloness and downwards-compat.
from awmstools import DEBUG_P, iupdate
from awmsmeta import gensym
DEBUG = 0
#FIXME: nested access
class MLabObjectProxy(object):
    """A proxy class for matlab objects that can't be converted to python
       types."""
    def __init__(self, mlab_direct, name, parent=None):
        self.__dict__['_mlab_direct'] = mlab_direct
        self.__dict__['_name'] = name
        """The name is the name of the proxies representation in matlab."""
        self.__dict__['_parent'] = parent
    def __repr__(self):
        return "<%s of matlab-class: %r; internal name: %r; has parent: %s>" % (
            type(self).__name__, self._mlab_direct._do("class('%s')"),
            self._name, ['no', 'yes'][bool(self._parent)])
            #AARGH there seems to be no sane way to 'display' to a string...
            #self._mlab_direct._do("display(%s)" % self._name))
    def __del__(self):
        if not self._parent:
            pymat.eval(self._mlab_direct._session, 'clear %s' % self._name)
    def _get_part(self, to_get):
        if self._mlab_direct._can_convert(to_get):
            DEBUG_P("getting", (("to_get", to_get),))
            pymat.eval(self._mlab_direct._session, "TMP_VAL=%s" % to_get)
            return self._mlab_direct._get("TMP_VAL", remove=True)
        else:
            return type(self)(self._mlab_direct, to_get, self)
    def __getattr__(self, attr):
        return self._get_part("%s.%s" % (self._name, attr))
    def __setattr__(self, attr, value):
        self._mlab_direct._set("%s.%s" % (self._name, attr), value)
    def __getitem__(self, index):
        if not type(index) is int:
            raise TypeError("Currently only integer indices are supported.")
        return self._get_part("%s(%d)" % (self._name, index+1))
    def __setitem__(self, index, value):
        if not type(index) is int:
            raise TypeError("Currently only integer indices are supported.")
        self._mlab_direct._set("%s(%d)" % (self._name, index+1), value)

    
class MLabDirect(object):
    """This implements a powerful and simple to use wrapper that makes using
    matlab(tm) from python almost completely transparent. To use simply do:
    
    >>> mlab = MLabDirect()

    and then just use whatever matlab command you like as follows:
    
    >>> mlab.plot(range(10), 'x')

    You can do more than just plotting:

    >>> mlab.sort([3,1,2])
    array([ 1.,  2.,  3.])

    MLab, unlike python has multiple value returns. To emulate calls like
    ``[a,b] = sort([3,2,1])`` just do:

    >>> mlab.sort([3,1,2], nout=2)
    (array([ 1.,  2.,  3.]), array([ 2.,  3.,  1.]))

    For names that are reserved in python (like print) do:

    >>> mlab.print_()
    
    In almost all cases that should be enough -- if you need to do trickier
    things, then get raw with ``mlab._do``, or build your child class that
    handles what you want.
    """
    
    def __init__(self, array_cast=None, autosync_dirs=1):
        """Create a new matlab(tm) wrapper object with its own session.

        :Paramters:

        - `array_cast` specifies a cast for arrays. If the result of an
          operation is a Numeric array, ``return_type(res)`` will be returned
          instead.
        
        - `autosync_dirs` specifies whether the working directory of the
          matlab session should be kept in sync with that of python.
        """
        self.array_cast = array_cast        
        self.autosync_dirs = autosync_dirs
        self._session = pymat.open()
        self._command_cache = {}
        self._proxies = weakref.WeakValueDictionary()
        self._permanent_names = []
        self._convertable = ('double', 'char')
        
    def __del__(self):
        pymat.close(self._session)
    def _can_convert(self, varname):
        DEBUG_P("", (("varname", varname),))
        pymat.eval(self._session, "TMP_CLS__ = class(%s)" % varname) #FIXME for funcs we would need ''s
        res_type = pymat.get(self._session, "TMP_CLS__")
        pymat.eval(self._session, "clear TMP_CLS__")
        # we only now how to deal with double (includes complex) matrices and
        # strings
        return res_type in self._convertable
    def _make_proxy(self, varname):
        """Creates a proxy for a variable.

        This doesn't have to deal with nested proxies -- only the root of a
        nested non-pythonable project is created with this method.
        """
        proxy_val_name = "PROXY_VAL%d__" % len(self._proxies)
        pymat.eval(self._session, "%s = %s" % (proxy_val_name, varname))
        res = MLabObjectProxy(self, proxy_val_name)
        self._proxies[proxy_val_name] = res
        return res

    def _as_mlabable_type(self, arg):
        if   isinstance(arg, (int, float, long, complex)):
            #pymat.eval(self._session, '%s=%r' % (argnames[-1], arg))
            return Numeric.array([arg])
            #FIXME what about unicode and other seq-thingies?
        if isinstance(arg, (Numeric.ArrayType, list, tuple, str)):
            return arg
        else:
            raise TypeError("Unsuitable argument type: %s" % type(arg))
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
        DEBUG_P("", (("cmd", cmd), ("args", args), ("kwargs", kwargs),))
        self._session = self._session or pymat.open()
        # HACK        
        if self.autosync_dirs:
            pymat.eval(self._session,  'cd %s' % os.getcwd())
        nout =  kwargs.get('nout', 1)
        DEBUG_P("", (("nout", nout),))
        argnames = []
        for arg, count in zip(args, xrange(sys.maxint)):
            if isinstance(arg, MLabObjectProxy):
                argnames.append(MLabObjectProxy._name)
            else:
                argnames.append('arg%d__' % count)
                # have to convert these by hand
                try:
                    arg = self._as_mlabable_type(arg)
                except TypeError:
                    raise TypeError("Illegal argument type (%s) for %d. argument" %
                                    (type(arg), type(count)))
        if args:
            cmd = "%s(%s)" % (cmd, ", ".join(argnames))
        # got three cases for nout:
        # 0 -> None, 1 -> val, >1 -> [val1, val2, ...]
        if nout == 0:
            pymat.eval(self._session, cmd)
            if argnames:
                pymat.eval(self._session, "clear('%s')" % "', '".join(argnames))
            return
        # deal with matlab-style multiple value return
        resSL = ((["RES%d__" % i for i in range(nout)]))
        DEBUG_P("", (("resSL", resSL), ("cmd", cmd),))
        pymat.eval(self._session, '[%s]=%s' % (", ".join(resSL), cmd))
        res = []
        for resS in resSL:
            #FIXME: this should be fixed in the c++ sources
##             HACK zeros(0,1) etc. incorrectly returns array([1.])
##             pymat.eval(self._session, "TMP__ = isempty(%s)" % resSL):
##             if pymat.get("TMP__")[0]:
##                 res.append(pymat...
            pymat.eval(self._session, "clear('TMP__')")
            DEBUG_P("determining res type", ())            
            if self._can_convert(resS):
                resPart = pymat.get(self._session, resS)
                if self.array_cast and type(resPart) is Numeric.ArrayType:
                    resPart = self.array_cast(resPart)
            # we can't convert this to a python object, so we just create
            # a proxy, and don't delete the real matlab reference until
            # the proxy is garbage collected
            else:
                DEBUG_P("funny res", ())
                resPart = self._make_proxy(resS)
            res.append(resPart)
        # XXX: if we have a very large number of results, this might cause
        # a problem.
        pymat.eval(self._session, "clear('%s')" % "','".join(resSL))
        if nout == 1: res = res[0]
        else:         res = tuple(res)
        pymat.eval(self._session, "clear('%s')" % "', '".join(argnames))
        if kwargs.has_key('cast'):
            if nout == 0: raise TypeError("Can't cast: 0 nout")
            return kwargs['cast'](res)
        else:
            return res
    def _get(self, name, remove=False):
        res = pymat.get(self._session, name)
        if remove:
            pymat.eval(self._session, "clear %s" % name)
        return res
    def _set(self, name, value):
        if isinstance(value, MLabObjectProxy):
            pymat.eval(self._session, "%s = %s" % (name, value._name))
        else:
            pymat.put(self._session, name, self._as_mlabable_type(value))
    #XXX this method needs some refactoring, but only after it is clear how
    #things should be done (e.g. what should be extracted from docstrings and
    #how, and how
    def __getattr__(self, attr):
        """Magically creates a wapper to a matlab function, procedure or
        object on-the-fly."""
        # print_ -> print        
        if attr[-1] == "_": attr = attr[:-1]        
        if self._command_cache.has_key(attr):
            return self._command_cache[attr]
        typ = self._do("exist('%s')" % attr)
        doc = self._do("help('%s')" % attr)
        if   typ == 0: # doesn't exist
            raise AttributeError("No such matlab object: %s" % attr)
        elif typ == 5: # builtin
            #FIXME: should we discard all this crap and just assume nout=1?
            
            # well, obviously matlab doesn't offer much in terms of
            # introspective capabilities for builtins (*completely* unlike
            # python <cough>), but with the aid of a simple regexp, we may
            # still find out what we want.
            callSigRE = re.compile(r"""
            ^\s*
            # opitonally return values, either
            (?:
              (?P<argout>
                    # A = FOO...
                    (?:[A-Z]+)
                  |                     
                    # [A,B] = FOO...
                    \[
                      (?:[A-Z]+,\s*)+[A-Z]+
                    \]

              )\s*=\s*
            )?
            # the command name itself, upcased
            (?P<cmd>%s)
            # the (optional) arguments; either
            (?: 
                # FOO BAR QUUX (command syntax; this re doesn't work for
                # pathological cases like `print` and `delete`)
                (?P<cmdargs>(?:\s+[A-Z]+)+)?\s
             |
                # FOO(BAR, ...) (function call syntax)
                (?P<argin>
                    \(
                    .*
                      (?:
                       (?:\.\.\.),\s*
                       |
                       (?:['\w]+),\s*
                      )*
                    \)
                )
            )
            """ % attr.upper(), re.X | re.M)
            match_at = lambda what: match[callSigRE.groupindex[what]-1]
            maxout = 0
            maxin = 0
            for match in callSigRE.findall(doc[doc.find("\n"):]):
                DEBUG_P("", (("match", match),))
                argout = match_at('argout')
                #FIXME how are infinite nouts specified in docstrings?
                if argout:
                    maxout = max(maxout, len(argout.split(',')))
                argin = match_at('argin')
                if argin:
                    if argin.find('...'):
                        maxin = -1
                    else:
                        maxin = max(maxin, len(argin.split(',')))
                cmdargs = match_at('cmdargs')
                if cmdargs:
                    maxin = max(maxin, len(cmdargs.split()))
            if maxout == 0:
                # an additional HACK for docs that aren't following the
                # ``foo = bar(...)`` convention
                if re.search(r'\b%s\(.+?\) (?:is|return)' % attr.upper(), doc):
                    maxout = 1
            nout = maxout #XXX
            nin  = maxin  #XXX
        else: #XXX should this be ``elif typ == 2:`` ?
            nout = self._do("nargout('%s')" % attr)
            nin  = self._do("nargin('%s')" % attr)
        def mlab_command(*args, **kwargs):
            # XXX are all `nout>1`s also useable as `nout==1`s?
            return self._do(attr, *args, **iupdate({'nout': nout and 1}, kwargs))
        mlab_command.__doc__ = "\n" + doc
        self._command_cache[attr] = mlab_command
        return mlab_command
        
#mlab = MLabDirect()
__all__ = MLabDirect
if __name__ == "__main__":
    DEBUG = 3
    mlab = MLabDirect()
    sct = mlab._do("struct('type',{'big','little'},'color','red','x',{3 4})")
    print sct
    sct[1].x  = 3    
