##############################################################################
################ mlab_direct: transparently wraps matlab(tm) #################
##############################################################################
##
## o author: Alexander Schmolck (a.schmolck@gmx.net)
## o created: 2002-05-29 21:51:59+00:40
## o last modified: $Date$
## o keywords: matlab wrapper
## o license: LGPL
## o FIMXE:
##   - the proxy getitem/setitem only works properly for 1D arrays
## o XXX:
##   - best treatment of lists, tuples obj-arrays?
##   - clean-up what is proxied and what isn't and make choices optional
##   - find out about classes and improve struct support
##   - multi-dimensional arrays
##   - should we transform 1D vectors into row vectors when handing them to
##     matlab?
##   - what should be flattend? Should there be a scalarization opition?
##   - nested proxies should be cached and identical.
##   - autosync_dirs is a bit of a hack...
## o TODO:
##   - delattr
##   - better error reporting: test for number of input args etc.
##   - add cloning of proxies.
##   - more tests
##   - is there a way to get ``display(x)`` as a string (apart from using
##     diary?)
## o !!!:
##   - matlab complex arrays are intelligently of type 'double'
##   - ``class('func')`` but ``class(var)``

"""A wrapper for matlab, giving almost transparent access to matlab, including
online help.

More precisely, a wrapper around a wrapper:  Andrew Sterian's pymat
(http://claymore.engineer.gvsu.edu/~steriana/Python/pymat.html)


Limitations
    - The return values of the matlab functions must be 2D or 1D arrays or
      strings (Well, there is support for arbitrary matlab classes for which
      proxy objects are created, but that is experimental, so don't complain
      if horrible things happen:)
      
    - There isn't good error handling, because the underlying pymat doesn't
      have good error handling either.
      
    - Matlab doesn't know scalars, or 1D arrays. Consequently all functions
      where on might expect a scalar or 1D array to be returned will return a
      1x1 array instead. Also, because matlab is built around the 'double'
      matrix type (which also includes complex matrices), other types will
      most likely be cast to double (XXX).

Tested under matlab v6r12 and python2.2.1, but should also work for earlier
versions.

See the docu of `MLabDirect`. 
"""

__version__ = "$Revision$"

from __future__ import generators
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
        klass = self._mlab_direct._do("class(%s)" % self._name)
        #FIXME what about classes?
        if klass == "struct":
            rep = "\n" + self._mlab_direct._format_struct(self._name)
        else:
            rep = ""
        return "<%s of matlab-class: %r; internal name: %r; has parent: %s>%s" % (
            type(self).__name__, klass,
            self._name, ['no', 'yes'][bool(self._parent)],
            rep)
            #AARGH there seems to be no sane way to 'display' to a string...
            #self._mlab_direct._do("display(%s)" % self._name))
    def __del__(self):
        if not self._parent:
            pymat.eval(self._mlab_direct._session, 'clear %s' % self._name)
    def _get_part(self, to_get):
        #FIXME cells etc. needs refactoring
        pymat.eval(self._mlab_direct._session, "TMP_VAL__=%s" % to_get)
        if self._mlab_direct._var_type(to_get) in self._mlab_direct._can_convert:
            DEBUG_P("getting", (("to_get", to_get),))
            return self._mlab_direct._get("TMP_VAL__", remove=True)
        else:
            return type(self)(self._mlab_direct, to_get, self)
    def _set_part(self, to_set, value):
        #FIXME s.a.
        if isinstance(value, MLabObjectProxy):
            pymat.eval(self._mlab_direct._session, "%s = %s" % (to_set, value._name))
        else:
            self._mlab_direct._set("TMP_VAL__", value)
            pymat.eval(self._mlab_direct._session, "%s = TMP_VAL__ " % to_set)
            pymat.eval(self._mlab_direct._session, 'clear TMP_VAL__')
        
    def __getattr__(self, attr):
        return self._get_part("%s.%s" % (self._name, attr))
    def __setattr__(self, attr, value):
        self._set_part("%s.%s" % (self._name, attr), value)
    #FIXME: those two only works ok for vectors
    def __getitem__(self, index):
        if not type(index) is int:
            raise TypeError("Currently only integer indices are supported.")
        return self._get_part("%s(%d)" % (self._name, index+1))
    def __setitem__(self, index, value):
        if not type(index) is int:
            raise TypeError("Currently only integer indices are supported.")
        self._set_part("%s(%d)" % (self._name, index+1), value)

    
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

    You can look at the documentation of a matlab function just by using help,
    as usual:

    >>> help(mlab.sort)
    
    In almost all cases that should be enough -- if you need to do trickier
    things, then get raw with ``mlab._do``, or build your child class that
    handles what you want.
    """
    
    def __init__(self, array_cast=None, autosync_dirs=True):
        """Create a new matlab(tm) wrapper object with its own session.

        :Paramters:

        - `array_cast` specifies a cast for arrays. If the result of an
          operation is a Numeric array, ``return_type(res)`` will be returned
          instead.
        
        - `autosync_dirs` specifies whether the working directory of the
          matlab session should be kept in sync with that of python.
        """
        self.array_cast = array_cast
        self.flatten_row_vecs = True
        self.flatten_col_vecs = False
        self.autosync_dirs = autosync_dirs
        self._session = pymat.open()
        self._command_cache = {}
        self._proxies = weakref.WeakValueDictionary()
        self._proxy_count = 0
        self._can_convert = ('double', 'char')
        
    def __del__(self):
        pymat.close(self._session)
    def _format_struct(self, varname):
        res = []
        fieldnames = self._do("fieldnames(%s)" % varname)
        size       = self._do("size(%s)" % varname).flat
        return "%dx%d struct array with fields:\n%s" % (
            size[0], size[1], "\n   ".join([""] + fieldnames))
##         fieldnames
##         fieldvalues = self._do(",".join(["%s.%s" % (varname, fn)
##                                          for fn in fieldnames]), nout=len(fieldnames))
##         maxlen = max(map(len, fieldnames))
##         return "\n".join(["%*s: %s" % (maxlen, (`fv`,`fv`[:20] + '...')[len(`fv`) > 23])
##                                        for fv in fieldvalues])
        
    def _var_type(self, varname):
        DEBUG_P("", (("varname", varname),))
        pymat.eval(self._session, "TMP_CLS__ = class(%s)" % varname) #FIXME for funcs we would need ''s
        res_type = pymat.get(self._session, "TMP_CLS__")
        pymat.eval(self._session, "clear TMP_CLS__")
        return res_type
    def _make_proxy(self, varname):
        """Creates a proxy for a variable.

        XXX create and cache nested proxies also here.
        """
        proxy_val_name = "PROXY_VAL%d__" % self._proxy_count
        self._proxy_count += 1
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
            try:
                return arg.__array__()
            except AttributeError:
                raise TypeError("Unsuitable argument type: %s" % type(arg))
    def _get_cell(self, varname):
        # make sure it's 1D
        pymat.eval(self._session,
                   "TMP_SIZE_INFO__ = \
                   [min(size(%(vn)s)) == 1 & ndims(%(vn)s) == 2, \
                   max(size(%(vn)s))] " % {'vn':varname})
        is_rank1, cell_len = self._get("TMP_SIZE_INFO__", remove=True).flat
        if is_rank1:
            cell_bits = (["TMP%i%s__" % (i, gensym('_'))
                           for i in range(cell_len)])
            pymat.eval(self._session, '[%s] = deal(%s{:})' %
                       (",".join(cell_bits), varname))
            # !!! this recursive call means we have to take care with
            # overwriting temps!!!
            DEBUG_P("", (("cell_bits", cell_bits), ("varname", varname),))
            return self._get_values(cell_bits)
        else: return None #FIXME #raise ValueError("Not a 1D cell array")
        
    def _get_values(self, varnames):
        res = []
        if not varnames: raise ValueError("No varnames") #to prevent clear('')
        for varname in varnames:
            vartype = self._var_type(varname)
            if vartype in self._can_convert:
                var = pymat.get(self._session, varname)
                if type(var) is Numeric.ArrayType:
                    if self.flatten_row_vecs and Numeric.shape(var)[0] == 1:
                        DEBUG_P("", (("Numeric.shape(var)", Numeric.shape(var)),))
                        var.shape = var.shape[1:2]
                    elif self.flatten_col_vecs and Numeric.shape(var)[1] == 1:
                        var.shape = var.shape[0:1]
                    if self.array_cast:
                        var = self.array_cast(var)
            else:
                var = None
                if vartype == 'cell':
                    var = self._get_cell(varname)
                    DEBUG_P("got a cell?", (("var", var), ("varname", varname),))
                if not var:
                    # we can't convert this to a python object, so we just
                    # create a proxy, and don't delete the real matlab
                    # reference until the proxy is garbage collected
                    DEBUG_P("funny res", ())
                    var = self._make_proxy(varname)
            res.append(var)
        pymat.eval(self._session, "clear('%s')" % "','".join(varnames))
        return res
    
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
        #self._session = self._session or pymat.open()
        # HACK        
        if self.autosync_dirs:
            pymat.eval(self._session,  'cd %s' % os.getcwd())
        nout =  kwargs.get('nout', 1)
        DEBUG_P("", (("nout", nout),))
        argnames = []
        for arg, count in zip(args, xrange(sys.maxint)):
            if isinstance(arg, MLabObjectProxy):
                argnames.append(arg._name)
            else:
                argnames.append('arg%d__' % count)
                # have to convert these by hand
                try:
                    arg = self._as_mlabable_type(arg)
                except TypeError:
                    raise TypeError("Illegal argument type (%s.:) for %d. argument" %
                                    (type(arg), type(count)))
                pymat.put(self._session,  argnames[-1], arg)

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
        res = self._get_values(resSL)
        
        if nout == 1: res = res[0]
        else:         res = tuple(res)
        if kwargs.has_key('cast'):
            if nout == 0: raise TypeError("Can't cast: 0 nout")
            return kwargs['cast'](res)
        else:
            return res
    # this is really raw, no conversion of [[]] -> [], whatever
    def _get(self, name, remove=False):
        res = pymat.get(self._session, name)
        if remove:
            pymat.eval(self._session, "clear %s" % name)
        return res
    def _set(self, name, value):
        DEBUG_P("", (("name", name), ("value", value),))
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
                # XXX: doesn't work for 'DISPLAY(x) is called...'
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
DEBUG = 1
__all__ = MLabDirect
if __name__ == "__main__":
    from Numeric import array
    DEBUG = 0
    mlab = MLabDirect()
    assert mlab.sort(1) == Numeric.array([1.])
    assert mlab.sort([3,1,2]) == Numeric.array([1., 2., 3.])
    assert mlab.sort(Numeric.array([3,1,2])) == Numeric.array([1., 2., 3.])
    sct = mlab._do("struct('type',{'big','little'},'color','red','x',{3 4})")
    bct = mlab._do("struct('type',{'BIG','little'},'color','red')")
    print sct
    assert sct[1].x == 4
    sct[1].x  = 'New Value'
    assert sct[1].x == 'New Value'
    assert bct[0].type == 'BIG' and sct[0].type == 'big'
    mlab._set('foo', 1)
    assert mlab._get('foo') == Numeric.array([1.])
    assert mlab._do("{'a', 'b', {3,4, {5,6}}}") == \
           ['a', 'b', [array([ 3.]), array([ 4.]), [array([ 5.]), array([ 6.])]]]
    mlab.clear('foo')
    try:
        print mlab._get('foo')
    except: print "deletion worked"
    print sct
    print `bct`
    #FIXME: add tests for assigning and nesting proxies
    assert mlab.who() == ['HOME', 'PROXY_VAL0__', 'PROXY_VAL1__']
    del sct
    del bct
    mlab._set('bar', '1234')
    assert mlab.who() == ['HOME', 'bar']
