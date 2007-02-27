##############################################################################
################### test_mlabwrap: unittests for mlabwrap ####################
##############################################################################
##
## o author: Alexander Schmolck (a.schmolck@gmx.net)
## o created: 2003-07-00 00:00:00+00:00
## o last modified: $Date$
## o Note: Some optional but useful tests require
##   <http://mexcdf.sourceforge.net/>!
import sys, os, re
try:
    import numpy
    from numpy.random import rand, randn
    toscalar = lambda a:a.item()
except ImportError:
    import Numeric as numpy
    from MLab import rand, randn
    toscalar = lambda a:a.toscalar()
from tempfile import mktemp
try: # python >= 2.3 has better mktemp
    from tempfile import mkstemp as _mkstemp
    mktemp = lambda *args,**kwargs: _mkstemp(*args, **kwargs)[1]
except ImportError: pass
degensym_proxy = lambda s, rex=re.compile(r'(PROXY_VAL)\d+'): rex.sub(r'\1',s)


import unittest
TestCase = unittest.TestCase
TestSuite = unittest.TestSuite
try: 
    import awmstest
    TestCase = awmstest.PermeableTestCase2
    TestSuite = awmstest.RotatingTestSuite
except ImportError: pass

from awmstools import indexme, without
from mlabwrap import *

#XXX for testing in running session with existing mlab
## mlab
## mlab = MlabWrap()
mlab._dont_proxy['cell'] = True
WHO_AT_STARTUP = mlab.who()
mlab._dont_proxy['cell'] = False
# FIXME should do this differentlya
funnies = without(WHO_AT_STARTUP, ['HOME', 'V', 'WLVERBOSE', 'MLABRAW_ERROR_'])
if funnies:
    print >> sys.stderr, "Hmm, got some funny stuff in matlab env: %s" % funnies

#FIXME both below untested
def fitString(s, maxCol=79, newlineReplacement="\\n"):
    if newlineReplacement or isinstance(newlineReplacement, basestring):
        s = s.replace("\n", newlineReplacement)
    if maxCol is not None and len(s) > maxCol:
        s = "%s..." % s[:maxCol-3]
    return s
class NumericTestCase(TestCase):
    """Simple extensio to TestCase to handle array equality tests 'correctly'
       (i.e. work around rich comparisons). Since array repr's can also be
       very large, the printing of large reprs is controlled by
       ``maxReprLength`` (None to print everything) and
       ``reprNewlineReplacement`` (None not to replace newlines in the repr).
       """
    maxReprLength          = 30   #
    reprNewlineReplacement = "\\n"
    def _reallyEqual(self, first, second, testShape=True):
        #FIXME should this check for identical argument type, too?
        res = first == second
        # find out if are dealing with a sized object; looking for a __len__
        # attr does *NOT* work, because of #$@-C extension crap
        try:
            len(res)
        except TypeError:
            return res
        else:
            # HACK
            if len(first) == len(second) == 0:
                return `first` == `second` # deal with empty arrays
            res = ((not testShape or numpy.shape(first) == numpy.shape(second)) and 
                   # it is necessary to exclude 0 element arrays, because

                   # identical zero-element arrays don't compare true (``and True`` normalizes)
                   (not len(first) and not len(second)
                    or bool(numpy.alltrue((numpy.ravel(first == second))))))
        return res
    def _smallRepr(self, *args):
        return tuple([fitString(repr(arg), maxCol=self.maxReprLength,
                                  newlineReplacement=self.reprNewlineReplacement)
                      for arg in args])
    def assertEqual(self, first, second, msg=None):
        if not self._reallyEqual(first, second):
            raise self.failureException, \
                  (msg or '%s != %s' % self._smallRepr(first, second))

    assertEqual = failUnlessEqual = assertEqual
    def assertNotEqual(self, first, second, msg=None):
        if self._reallyEqual(first, second):
            raise self.failureException, \
                  (msg or '%s == %s' % self._smallRepr(first, second))
    assertNotEquals = failIfEqual = assertNotEqual
    def assertAlmostEqual(self, first, second, places=7, msg=None):
        if not (numpy.shape(first) == numpy.shape(second) and \
                self._reallyEqual(numpy.around(second-first, places), 0, testShape=False)):
            raise self.failureException, \
                  (msg or '%s != %s within %s places' % self._smallRepr(first,second,places))
    assertAlmostEquals = failUnlessAlmostEqual = assertAlmostEqual
    def assertNotAlmostEqual(self, first, second, places=7, msg=None):
        if not (numpy.shape(first) == numpy.shape(second) and \
                not self._reallyEqual(numpy.around(second-first, places), 0, testShape=False)):
            raise self.failureException, \
                  (msg or '%s == %s within %s places' % self._smallRepr(first,second,places))
    failIfAlmostEqual =  assertNotAlmostEquals = assertNotAlmostEqual
    
    
class mlabwrapTC(NumericTestCase):
##     def assertEqual(self, first, second):
##         res = first == second
##         if len(res):
##             res = numpy.shape(first) == numpy.shape(second) and \
##                   bool(numpy.alltrue((numpy.ravel(a1 == a2))))
##         super(TestCase, self).assertEquals(res, True)
        
    def testBasic(self):
        """Test basic behavior."""
        array = numpy.array
        from random import randrange
        "This largely tests basic mlabraw conversion functionality"
        for i in range(30):
            if i % 4: # every 4th is a flat vector
                a = rand(randrange(1,20))
            else:
                #FIXME add other ranks and shapes
##                 if i % 3:
##                     a = rand(randrange())
                a = rand(randrange(1,3),randrange(1,3))
            a1 = a.copy()
            mlab._set('a', a)
            if numpy.rank(a) == 2:
                self.assertEqual(a, mlab._get('a'))
            else:
                self.assertEqual(a, numpy.ravel(mlab._get('a')))
            self.assertEqual(a, a1)
            # make sure strides also work OK!
            mlab._set('a', a[::-2])
            if numpy.rank(a) == 2:
                self.assertEqual(a[::-2], mlab._get('a'))
            else:
                self.assertEqual(a[::-2], numpy.ravel(mlab._get('a')))
            self.assertEqual(a, a1)                
            if numpy.rank(a) == 2:
                mlab._set('a', a[0:-3:3,::-1])
                self.assertEqual(a[0:-3:3,::-1], mlab._get('a'))
                # test there are no aliasing problems
                newA = mlab._get('a')
                newA -= 1e4
                self.assertEqual(a,a1)
                if len(newA):
                    self.assertNotEqual(newA, mlab._get('a'))
            self.assertEqual(a, a1)                
            mlab.clear('a')
        # Complex
        for i in range(30):
            if i % 4: # every 4th is a flat vector
                a = rand(randrange(1,20));
                a = a + 1j*rand(*a.shape)
            else:
                #FIXME add other ranks and shapes
##                 if i % 3:
##                     a = rand(randrange())
                a = rand(randrange(1,3),randrange(1,3)) + 1j*rand(randrange(1,3),randrange(1,3))
            a1 = a.copy()
            mlab._set('a', a)
            if numpy.rank(a) == 2:
                self.assertEqual(a, mlab._get('a'))
            else:
                self.assertEqual(a, numpy.ravel(mlab._get('a')))
            self.assertEqual(a, a1)
            # make sure strides also work OK!
            mlab._set('a', a[::-2])
            if numpy.rank(a) == 2:
                self.assertEqual(a[::-2], mlab._get('a'))
            else:
                self.assertEqual(a[::-2], numpy.ravel(mlab._get('a')))
            self.assertEqual(a, a1)                
            if numpy.rank(a) == 2:
                mlab._set('a', a[0:-3:3,::-1])
                self.assertEqual(a[0:-3:3,::-1], mlab._get('a').astype('D')) # XXX
                # test there are no aliasing problems
                newA = mlab._get('a')
                newA -= 1e4
                self.assertEqual(a,a1)
                if len(newA):
                    self.assertNotEqual(newA, mlab._get('a'))
            self.assertEqual(a, a1)                
            mlab.clear('a')

            
        # the tricky diversity of empty arrays
        mlab._set('a', [[]])
        self.assertEqual(mlab._get('a'), numpy.zeros((1, 0), 'd'))
        mlab._set('a', numpy.zeros((0,0)))
        self.assertEqual(mlab._get('a'), numpy.zeros((0, 0), 'd'))
        mlab._set('a', [])
        self.assertEqual(mlab._get('a'), numpy.zeros((0, 0), 'd'))
        # complex empty
        mlab._set('a', numpy.zeros((0,0), 'D'))
        self.assertEqual(mlab._get('a'), numpy.zeros((0, 0), 'd')) #XXX
        # 0d
        mlab._set('a', -2)
        self.assertEqual(mlab._get('a'), array([       [-2.]]))
        mlab._set('a', array(-2))
        self.assertEqual(mlab._get('a'), array([       [-2.]]))
        # complex 1D
        mlab._set('a', [1+3j, -4+2j, 6-5j])
        self.assertEqual(mlab._get('a'),array([[1.+3.j],[-4.+2.j],[6.-5.j]]))
        # complex 2D
        mlab._set('a', [[1+3j, -4+2j, 6+5j], [9+3j, 1, 3-2j]])
        self.assertEqual(mlab._get('a'), array([[1.+3.j,-4.+2.j,6.+5.j]
                                                ,[9.+3.j,1.+0.j,3.-2.j]]))
        mlab.clear('a')
        # try basic error handling
        self.failUnlessRaises(TypeError, mlab._set, 'a', [[[1]]])
        self.failUnlessRaises(MlabError, mlab._get, 'dontexist')
        self.failUnlessRaises(MlabError,mlab.round)
        try: # also check errormessage for above
            mlab.round()
        except MlabError, msg:
            pass
            #FIXME unfortunately these messages keep changing
##             assert str(msg).strip() == \
##                    'Error using ==> round\nIncorrect number of inputs.'
        else:
            assert False
    def testDoc(self):
        """Test that docstring extraction works OK."""
        mlab.who.__doc__.index('WHO lists the variables in the current workspace')
    def setUp(self):
        """Back up options."""
        self.backup = {}
        for opt in """\
        _array_cast  
        _autosync_dirs
        _flatten_row_vecs 
        _flatten_col_vecs 
        _clear_call_args 
        _session 
        _proxies 
        _proxy_count 
        _mlabraw_can_convert 
        _dont_proxy""".split():
           self.backup[opt] = mlab.__dict__[opt]
    def tearDown(self):
        """Reset options."""
        mlab.__dict__.update(self.backup)
    def testCallArgs(self):
        mlab._dont_proxy['cell'] = True
        try:
            mlab._clear_call_args = False
            mlab.sin(1.23)
            assert mlab._get('arg0__', True) == 1.23
            mlab._clear_call_args = True
            mlab.sin(1.23)
            assert not 'arg0__' in mlab.who()
        finally:
            mlab._clear_call_args = True            
            mlab._dont_proxy['cell'] = False
    def testXXXSubtler(self):
        """test more subtle stuff. This must come last, hence the XXX"""
        import os, cPickle
        array = numpy.array
        # simple strings:
        assert (mlab._do("''"), mlab._do("'foobar'")) == ('', 'foobar')
        self.assertEqual(mlab.sort(1), numpy.array([[1.]]))
        self.assertEqual(mlab.sort([3,1,2]), numpy.array([[1.], [2.], [3.]]))
        self.assertEqual(mlab.sort(numpy.array([3,1,2])), numpy.array([[1.], [2.], [3.]]))
        sct = mlab._do("struct('type',{'big','little'},'color','red','x',{3 4})")
        bct = mlab._do("struct('type',{'BIG','little'},'color','red')")
        self.assertEqual(sct[1].x, numpy.array([[4]]))
        self.assertEqual(sct[0].x, numpy.array([[3]]))
        #FIXME sct[:].x wouldn't work, but currently I'm not sure that's my fault
        sct[1].x  = 'New Value'
        assert sct[1].x == 'New Value'
        assert bct[0].type == 'BIG' and sct[0].type == 'big'
        mlab._set('foo', 1)
        assert mlab._get('foo') == numpy.array([1.])
        assert not mlab._do("{'a', 'b', {3,4, {5,6}}}") == \
               ['a', 'b', [array([ 3.]), array([ 4.]), [array([ 5.]), array([ 6.])]]]
        mlab._dont_proxy['cell'] = True
        assert mlab._do("{'a', 'b', {3,4, {5,6}}}") == \
               ['a', 'b', [array([ 3.]), array([ 4.]), [array([ 5.]), array([ 6.])]]]
        mlab._dont_proxy['cell'] = False
        mlab.clear('foo')
        self.assertRaises(MlabError, mlab._get, 'foo')
        assert degensym_proxy(repr(sct)) == (
            "<MlabObjectProxy of matlab-class: 'struct'; "
            "internal name: 'PROXY_VAL__'; has parent: no>\n"
            "1x2 struct array with fields:\n"
            "    type\n    color\n    x\n\n")
        #FIXME: add tests for assigning and nesting proxies
        ## ensure proxies work OK as arguments
        self.assertEqual(mlab.size(sct), array([[1., 2.]]))
        self.assertEqual(mlab.size(sct, 1), array([[1]]))
        # test that exceptions on calls with proxy arguments don't result in
        # trouble
        self.assertRaises(MlabError, mlab.svd, sct)
        self.assertEqual(mlab.size(sct, [2]), array([[2]]))
        mlab._dont_proxy['cell'] = True
        assert map(degensym_proxy,without(mlab.who(), WHO_AT_STARTUP)) == (['PROXY_VAL__', 'PROXY_VAL__'])
        # test pickling
        pickleFilename = mktemp()
        f = open(pickleFilename, 'wb')
        try:
            cPickle.dump({'sct': sct, 'bct': bct},f,1)
            f.close()
            f = open(pickleFilename, 'rb')
            namespace = cPickle.load(f)
            f.close()
        finally:
            os.remove(pickleFilename)
        assert len(mlab._proxies) == 4
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
        mlab._dont_proxy['cell'] = False
        
    def testAnEvenSubtlerProxyStuff(self):
        "time for some advanced proxied __getitem__ and __setitem___."
        if not mlab.exist('netcdf'):
            print >>sys.stderr, "Couldn't test subtle proxy stuff"
            return
        tmp_filename = mktemp(".nc")
        try:
            # This example may look a bit uhm, confusing, because the netcdf
            # class overloads matlab's already bizzarre syntax in dubious
            # ways.
            
            # create a new netcdf file
            ncf = mlab.netcdf(tmp_filename, 'clobber')
            ncf['dimension1'] = 10
            ncf['dimension2'] = 20
            #ncf['dimensionToDelete'] = 666
            ncf.someGlobalAttributeStr = "A random comment"
            ncf.someGlobalAttributeDouble = 2.0
            # use foo._[bar] for matlab's ``foo{'bar'}`` (instead of default
            # indexing foo[bar], which corresponds to ``foo('bar')``;
            # classes can support both styles of indexing, and indeed this one
            # does -- blech)
            ncf._['someVariable'] = 'dimension1'
            ncf._['someOtherVariable'] = 'dimension2'
            ncf._['someVariable'].someUnit = 'pixel'
            ncf._['someVariable'][:] = range(10)
            assert list(numpy.ravel(ncf._['someVariable'][:])) == range(10)
            ncf._['someVariable'][2:5] = [22,33,44]
            assert list(numpy.ravel(ncf._['someVariable'][:])) == [0,1,22,33,44,5,6,7,8,9]
            ncf._['someOtherVariable'][0:20] = range(20)
            mlab.close(ncf)

            # open netcdf file for reading and check everything's OK
            ncf = mlab.netcdf(tmp_filename, 'read')
            assert list(numpy.ravel(ncf._['someOtherVariable'][:])) == range(20)
            assert list(numpy.ravel(ncf._['someVariable'][:])) == [0,1,22,33,44,5,6,7,8,9]
            self.assertRaises(ValueError, ncf._['someVariable'].__getitem__,slice(2, None, None))
            self.assertRaises(ValueError, ncf._['someVariable'].__getitem__,slice(2, 4, -1))
            assert toscalar(ncf.someGlobalAttributeDouble[:]) == 2.0
            assert ncf.someGlobalAttributeStr[:] == "A random comment"
            assert ncf._['someVariable'].someUnit[:] == 'pixel'
            assert ncf.someGlobalAttributeStr[:] == "A random comment"
            mlab.close(ncf)
##             mlab._set('d1', ncf['dimension1'])
##             mlab._set('d2', ncf['dimension2'])
        finally:
            if os.path.exists(tmp_filename): os.remove(tmp_filename)
    def testMlabraw(self):
        """A few explicit tests for mlabraw"""
        import mlabraw
        #print "test mlabraw"
        self.assertRaises(TypeError, mlabraw.put, 33, 'a',1)
        self.assertRaises(TypeError, mlabraw.get, object(), 'a')
        self.assertRaises(TypeError, mlabraw.eval, object(), '1')
        self.assertEqual(mlabraw.eval(mlab._session, r"fprintf('1\n')"),'1\n')
        try:
            self.assertEqual(mlabraw.eval(mlab._session, r"1"),'')
        finally:
            mlabraw.eval(mlab._session,'clear ans')
        #print "tested mlabraw"
    
    def testOrder(self):
        """"Testing order flags cause no problems""""
        try: import numpy
        except ImportError: return
        fa=numpy.array([[1,2,3],[4,5,6]],order='F')
        self.assertEqual(mlab.conj(fa),fa)
        self.assertEqual([[2]],mlab.subsref(fa, mlab.struct('type', '()', 'subs',mlab._do('{{1,2}}'))))

suite = TestSuite(map(unittest.makeSuite,
                               (mlabwrapTC,
                                )))
unittest.TextTestRunner(verbosity=2).run(suite)

#FIXME strangely enough we can't test this in the function!
import gc
gc.collect()
mlab._dont_proxy['cell'] = True
# XXX got no idea where HOME comes from, not there under win
assert without(mlab.who(), WHO_AT_STARTUP) == ['bar']
mlab.clear()
assert without(mlab.who(), ['MLABRAW_ERROR_']) == [] == mlab._do('{}')
mlab._dont_proxy['cell'] = False
