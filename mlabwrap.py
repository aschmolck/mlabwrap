##############################################################################
################ mlab_direct: transparently wraps matlab(tm) #################
##############################################################################
##
## o author: Alexander Schmolck (a.schmolck@gmx.net)
## o created: 2002-05-29 21:51:59+00:40
## o last modified: $Date$
## o version: 0.5
## o keywords: matlab wrapper
## o license: LGPL
## o FIXME:
##   - the proxy getitem/setitem only works properly for 1D arrays
##   - multi-dimensional arrays are unsupported
## o XXX:
##   - treatment of lists, tuples and arrays with non-numerical values?
##   - find out about classes and improve struct support
##   - should we transform 1D vectors into row vectors when handing them to
##     matlab?
##   - what should be flattend? Should there be a scalarization opition?
##   - ``autosync_dirs`` is a bit of a hack (and maybe``handle_out``, too)...
##   - is ``global mlab`` in unpickling of proxies OK?
##   - hasattr fun for proxies (__deepcopy__ etc.)
##   - check pickling
## o TODO:
##   - delattr
##   - better error reporting: test for number of input args etc.
##   - add cloning of proxies.
##   - pickling for nested proxies
##   - more tests
## o !!!:
##   - matlab complex arrays are intelligently of type 'double'
##   - ``class('func')`` but ``class(var)``

"""A wrapper for matlab, giving almost transparent access to matlab, including
online help and experimental pickling support.

More precisely, it is a wrapper around a wrapper: A modified version of Andrew
Sterian's pymat (http://claymore.engineer.gvsu.edu/~steriana/Python/pymat.html).

Limitations
    - Only 2D matrices are directly supported as return values of matlab
      functions (arbitrary matlab classes are supported via proxy objects --
      in most cases this shouldn't make much of a difference (and these proxy
      objects can be even pickled) -- still this functionality is yet
      experimental).

      One potential pitfall with structs (which are currently proxied) is that
      setting indices of subarrays ``struct.part[index] = value`` might seem
      to have no effect (since ``part`` can be directly represented as a
      python array which will be modified without an effect on the proxy
      ``struct``'s contents); in that case::

        some_array[index] = value; struct.part == some_array``

      will have the desired effect.
      
    - Matlab doesn't know scalars, or 1D arrays. Consequently all functions
      where on might expect a scalar or 1D array to be returned will return a
      1x1 array instead. Also, because matlab is built around the 'double'
      matrix type (which also includes complex matrices), other types will
      most likely be cast to double (XXX). Note that row and column vectors
      can be autoconverted automatically to 1D arrays if that is desired (see
      `_flatten_row_vecs`).

Tested under matlab v6r12 and python2.2.1.

See the docu of `MLabDirect`. 
"""

__version__ = "$Revision$"

from __future__ import generators
import tempfile
from pickle import PickleError
import os, sys, re
import Numeric
import pymat
import weakref
import atexit

from awmstools import DEBUG_P, iupdate, magicGlobals, slurpIn, spitOut, prin
from awmsmeta import gensym
DEBUG = 0
DEBUG_P = lambda *x,**y:None
#XXX: nested access

def _flush_write_stdout(s):
    """Writes `s` to stdout and flushes. Default value for ``handle_out``."""
    sys.stdout.write(s); sys.stdout.flush()

class MLabObjectProxy(object):
    """A proxy class for matlab objects that can't be converted to python
       types.

       !!! Assigning to parts of proxy objects (e.g. ``proxy[1].foo =
       [[1,2,3]]``) should *largely* work as expected, the only exception
       would be if ``proxy.foo[1] = 3`` where ``foo`` is some type that can be
       converted to python (i.e. an array or string, (or cell, if cell
       conversion has been enabled)), because then ``proxy.foo`` returns a new
       python object. For these cases it's necessary to do::

         some_array[1] = 3; proxy.foo = some_array

       """
    def __init__(self, mlab_direct, name, parent=None):
        self.__dict__['_mlab_direct'] = mlab_direct
        self.__dict__['_name'] = name
        """The name is the name of the proxies representation in matlab."""
        self.__dict__['_parent'] = parent

    def __getstate__(self):
        "Experimental pickling support."
        if self.__dict__['_parent']:
            raise PickleError(
                "Only root instances of %s can currently be pickled." % \
                type(self).__name__)
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            "mlab_pickle_%s.mat" % self._mlab_direct._session)
        try:
            mlab.save(tmp_filename, self._name)
            mlab_contents = slurpIn(tmp_filename, binary=1)
        finally:
            if os.path.exists(tmp_filename): os.remove(tmp_filename)

        return {'mlab_contents' : mlab_contents,
                'name': self._name}
        
        
    def __setstate__(self, state):
        "Experimental unpickling support."
        global mlab         #XXX: make this class var
        old_name = state['name']
        mlab_name = "UNPICKLED%s__" % gensym('')
        try:
            tmp_filename = tempfile.mktemp('.mat')
            spitOut(state['mlab_contents'], tmp_filename, binary=1)
            pymat.eval(mlab._session,
                       "TMP_UNPICKLE_STRUCT__ = load('%s', '%s');" % (
                tmp_filename, old_name))
            pymat.eval(mlab._session,
                       "%s = TMP_UNPICKLE_STRUCT__.%s;" % (mlab_name, old_name))
            pymat.eval(mlab._session, "clear TMP_UNPICKLE_STRUCT__;")
            # XXX
            mlab._make_proxy(mlab_name, constructor=lambda *args: self.__init__(*args) or self)
            pymat.eval(mlab._session, 'clear %s;' % mlab_name)
        finally:
            if os.path.exists(tmp_filename): os.remove(tmp_filename)
        
    def __repr__(self):
        # HACK
        output = []
        mlab._do('disp(%s)' % self._name, nout=0, handle_out=output.append)
        rep = output[0]
        klass = self._mlab_direct._do("class(%s)" % self._name)
##         #XXX what about classes?
##         if klass == "struct":
##             rep = "\n" + self._mlab_direct._format_struct(self._name)
##         else:
##             rep = ""
        return "<%s of matlab-class: %r; internal name: %r; has parent: %s>\n%s" % (
            type(self).__name__, klass,
            self._name, ['no', 'yes'][bool(self._parent)],
            rep)
    def __del__(self):
        if not self._parent:
            pymat.eval(self._mlab_direct._session, 'clear %s;' % self._name)
    def _get_part(self, to_get):
        if self._mlab_direct._var_type(to_get) in self._mlab_direct._pymat_can_convert:
            #!!! need assignment to TMP_VAL__ because `pymat.get` only works with
            #    'atomic' values like ``foo`` and not e.g. ``foo.bar``.
            pymat.eval(self._mlab_direct._session, "TMP_VAL__=%s" % to_get)
            return self._mlab_direct._get('TMP_VAL__', remove=True)
        return type(self)(self._mlab_direct, to_get, self)
    def _set_part(self, to_set, value):
        #FIXME s.a.
        if isinstance(value, MLabObjectProxy):
            pymat.eval(self._mlab_direct._session, "%s = %s;" % (to_set, value._name))
        else:
            self._mlab_direct._set("TMP_VAL__", value)
            pymat.eval(self._mlab_direct._session, "%s = TMP_VAL__;" % to_set)
            pymat.eval(self._mlab_direct._session, 'clear TMP_VAL__;')
        
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

class MLabConversionError(Exception):
    """Raised when a mlab type can't be converted to a python primitive."""
    pass
    
class MLabDirect(object):
    """This implements a powerful and simple to use wrapper that makes using
    matlab(tm) from python almost completely transparent. To use simply do:
    
    >>> from mlab_direct import mlab

    and then just use whatever matlab command you like as follows:
    
    >>> mlab.plot(range(10), 'x')

    You can do more than just plotting:

    >>> mlab.sort([3,1,2])
    array([[ 1.,  2.,  3.]])

    N.B.: The result here is a 1x3 matrix (and not a flat lenght 3 array) of
    type double (and not int), as matlab built around matrices of type double
    (see `MLabDirect._flatten_row_vecs`).

    MLab, unlike python has multiple value returns. To emulate calls like
    ``[a,b] = sort([3,2,1])`` just do:

    >>> mlab.sort([3,1,2], nout=2)
    (array([[ 1.,  2.,  3.]]), array([[ 2.,  3.,  1.]]))

    For names that are reserved in python (like print) do:

    >>> mlab.print_()

    You can look at the documentation of a matlab function just by using help,
    as usual:

    >>> help(mlab.sort)
    
    In almost all cases that should be enough -- if you need to do trickier
    things, then get raw with ``mlab._do``, or build your child class that
    handles what you want.
    """
    
    def __init__(self):
        """Create a new matlab(tm) wrapper object.
        """
        self._array_cast  = None
        """specifies a cast for arrays. If the result of an
        operation is a Numeric array, ``return_type(res)`` will be returned
        instead."""
        self._autosync_dirs=True
        """`autosync_dirs` specifies whether the working directory of the
        matlab session should be kept in sync with that of python."""
        self._flatten_row_vecs = False
        """Automatically return 1xn matrices as flat numeric arrays."""
        self._flatten_col_vecs = False
        """Automatically return nx1 matrices as flat numeric arrays."""
        self._session = pymat.open()
        self._command_cache = {}
        self._proxies = weakref.WeakValueDictionary()
        self._proxy_count = 0
        self._pymat_can_convert = ('double', 'char')
        """The matlab(tm) types that pymat will automatically convert for us."""
        self._optionally_convert = {'cell' : False}
        """The matlab(tm) types we can handle ourselves with a bit of
           effort. To turn on autoconversion for e.g. cell arrays do:
           ``mlab._optionally_convert["cell"] = True``."""
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
        pymat.eval(self._session, "TMP_CLS__ = class(%s);" % varname) #FIXME for funcs we would need ''s
        res_type = pymat.get(self._session, "TMP_CLS__")
        pymat.eval(self._session, "clear TMP_CLS__;")
        return res_type
    
    def _make_proxy(self, varname, parent=None, constructor=MLabObjectProxy):
        """Creates a proxy for a variable.

        XXX create and cache nested proxies also here.
        """
        proxy_val_name = "PROXY_VAL%d__" % self._proxy_count
        self._proxy_count += 1
        pymat.eval(self._session, "%s = %s;" % (proxy_val_name, varname))
        res = constructor(self, proxy_val_name, parent)
        self._proxies[proxy_val_name] = res
        return res

    def _as_mlabable_type(self, arg):
        if   isinstance(arg, (int, float, long, complex)):
            #pymat.eval(self._session, '%s=%r;' % (argnames[-1], arg))
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
        # XXX can currently only handle 1D
        pymat.eval(self._session,
                   "TMP_SIZE_INFO__ = \
                   [min(size(%(vn)s)) == 1 & ndims(%(vn)s) == 2, \
                   max(size(%(vn)s))];" % {'vn':varname})
        is_rank1, cell_len = self._get("TMP_SIZE_INFO__", remove=True).flat
        if is_rank1:
            cell_bits = (["TMP%i%s__" % (i, gensym('_'))
                           for i in range(cell_len)])
            pymat.eval(self._session, '[%s] = deal(%s{:});' %
                       (",".join(cell_bits), varname))
            # !!! this recursive call means we have to take care with
            # overwriting temps!!!
            DEBUG_P("", (("cell_bits", cell_bits), ("varname", varname),))
            return self._get_values(cell_bits)
        else:
            raise MLabConversionError("Not a 1D cell array")
    def _manually_convert(self, varname, vartype):
        if vartype == 'cell':
            return self._get_cell(varname)

            
    def _get_values(self, varnames):
        res = []
        if not varnames: raise ValueError("No varnames") #to prevent clear('')
        for varname in varnames:
            res.append(self._get(varname))
        pymat.eval(self._session, "clear('%s');" % "','".join(varnames))
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
        handle_out = kwargs.get('handle_out', _flush_write_stdout)
        #self._session = self._session or pymat.open()
        # HACK        
        if self._autosync_dirs:
            pymat.eval(self._session,  'cd %s;' % os.getcwd())
        nout =  kwargs.get('nout', 1)
        #XXX what to do with matlab screen output
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
            cmd = "%s(%s)%s" % (cmd, ", ".join(argnames),
                                ('',';')[kwargs.get('show',0)])
        # got three cases for nout:
        # 0 -> None, 1 -> val, >1 -> [val1, val2, ...]
        if nout == 0:
            handle_out(pymat.eval(self._session, cmd))
            if argnames:
                handle_out(pymat.eval(self._session, "clear('%s');" % "', '".join(argnames)))
            return
        # deal with matlab-style multiple value return
        resSL = ((["RES%d__" % i for i in range(nout)]))
        #DEBUG_P("", (("resSL", resSL), ("cmd", cmd),))
        #print ("", (("resSL", resSL), ("cmd", cmd),))
        handle_out(pymat.eval(self._session, '[%s]=%s;' % (", ".join(resSL), cmd)))
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
        varname = name
        vartype = self._var_type(varname)
        if vartype in self._pymat_can_convert:
            var = pymat.get(self._session, varname)
            if type(var) is Numeric.ArrayType:
                if self._flatten_row_vecs and Numeric.shape(var)[0] == 1:
                    DEBUG_P("", (("Numeric.shape(var)", Numeric.shape(var)),))
                    var.shape = var.shape[1:2]
                elif self._flatten_col_vecs and Numeric.shape(var)[1] == 1:
                    var.shape = var.shape[0:1]
                if self._array_cast:
                    var = self._array_cast(var)
        else:
            var = None
            if self._optionally_convert.get(vartype):
                # manual conversions may fail (e.g. for multidimensional
                # cell arrays), in that case just fall back on proxying.
                try:
                    var = self._manually_convert(varname, vartype)
                except MLabConversionError: pass
            if var is None:
                # we can't convert this to a python object, so we just
                # create a proxy, and don't delete the real matlab
                # reference until the proxy is garbage collected
                DEBUG_P("funny res", ())
                var = self._make_proxy(varname)
        if remove:
            pymat.eval(self._session, "clear('%s');" % varname)
        return var
    
    def _set(self, name, value):
        DEBUG_P("", (("name", name), ("value", value),))
        if isinstance(value, MLabObjectProxy):
            pymat.eval(self._session, "%s = %s;" % (name, value._name))
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
        elif typ != 2: # i.e. we have a builtin, mex or similar
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
            """ % attr.upper(), re.X | re.M | re.I)
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
        
mlab = MLabDirect()
__all__ = ['mlab', 'MLabDirect', 'pymat.error']

                 
import Numeric
from MLab import rand
from random import randrange
def _test_sanity():
    for i in range(30):
        a = rand(randrange(1,20),randrange(1,20))
        mlab._set('a', a)
        try:
            mlab_a = mlab._get('a')
            mlab.clear('a')
            assert Numeric.alltrue(a.flat == mlab_a.flat)
        except AssertionError:
            print "A:\n%s\nB:\n%s|n" % (a, mlab._get('a'))
            raise
#XXX just to be sure
#print "STAGE 0"
_test_sanity()
    
DEBUG = 0
#print "STAGE 1"
if __name__ in ("__main__", "__IPYTHON_main__"):
    from awmstools import saveVars, loadVars
    array = Numeric.array
    _test_sanity()
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
    assert not mlab._do("{'a', 'b', {3,4, {5,6}}}") == \
           ['a', 'b', [array([ 3.]), array([ 4.]), [array([ 5.]), array([ 6.])]]]
    mlab._optionally_convert['cell'] = True
    assert mlab._do("{'a', 'b', {3,4, {5,6}}}") == \
           ['a', 'b', [array([ 3.]), array([ 4.]), [array([ 5.]), array([ 6.])]]]
    mlab._optionally_convert['cell'] = False
    mlab.clear('foo')
    try:
        print mlab._get('foo')
    except: print "deletion worked"
    print sct
    print `bct`
    #FIXME: add tests for assigning and nesting proxies
    help(mlab.who)
    mlab._optionally_convert['cell'] = True
    assert mlab.who() == ['HOME', 'PROXY_VAL0__', 'PROXY_VAL1__']
    print "TESTING PICKLING"
    saveVars('/tmp/saveVars', 'sct bct')
    namespace = {}
    loadVars('/tmp/saveVars', 'sct bct', namespace)
    assert len(mlab._proxies) == 4
    print namespace['sct']
    assert namespace['sct'][1].x == 'New Value'
    namespace['sct'][1].x = 'Even Newer Value'
    assert namespace['sct'][1].x ==  'Even Newer Value'
    assert sct[1].x == 'New Value'
    del sct
    del bct
    del namespace['sct']
    del namespace['bct']
    mlab._set('bar', '1234')
    x = []
    mlab._do("disp 'hallo'" ,nout=0, handle_out=x.append)
    assert x[0] == 'hallo\n'
    assert mlab.who() == ['HOME', 'bar']
    mlab._optionally_convert['cell'] = False
