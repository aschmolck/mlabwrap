##############################################################################
################### test_mlabwrap: unittests for mlabwrap ####################
##############################################################################
##
## o author: Alexander Schmolck (a.schmolck@gmx.net)
## o created: 2003-07-00 00:00:00+00:00
## o last modified: $Date$


import unittest
TestCase = unittest.TestCase
try: 
    import awmstest
    TestCase = awmstest.PermeableTestCase2
except ImportError: pass

from mlabwrap import *

class mlabwrapTC(TestCase):
    def testBasic(self):
        """Test basic behavior."""
        import Numeric
        array = Numeric.array
        from MLab import rand
        from random import randrange
        "This largely tests basic mlabraw conversion functionality"
        for i in range(30):
            if i % 4: # every 4th is a flat vector
                a = rand(randrange(1,20))
            else:
                a = rand(randrange(1,3),randrange(1,3))
            mlab._set('a', a)
            if Numeric.rank(a) == 2:
                assert `a` == `mlab._get('a')`
            else:
                assert `a` == `mlab._get('a').flat`
            # make sure strides also work OK!
            mlab._set('a', a[::-2])
            if Numeric.rank(a) == 2:
                assert `a[::-2]` == `mlab._get('a')`
            else:
                assert `a[::-2]` == `mlab._get('a').flat`
            if Numeric.rank(a) == 2:
                mlab._set('a', a[0:-3:3,::-1])
                assert `a[0:-3:3,::-1]` == `mlab._get('a')`
            mlab.clear('a')                
            # the tricky diversity of empty arrays
            mlab._set('a', [[]])
            assert `mlab._get('a')` == "zeros((1, 0), 'd')"
            mlab._set('a', Numeric.zeros((0,0)))
            assert `mlab._get('a')` == "zeros((0, 0), 'd')"
            mlab._set('a', [])
            assert `mlab._get('a')` == "zeros((0, 0), 'd')"
            # 0d
            mlab._set('a', -2)
            assert `mlab._get('a')` == "array([       [-2.]])"
            mlab._set('a', array(-2))
            assert `mlab._get('a')` == "array([       [-2.]])"
            # complex 1D
            mlab._set('a', [1+3j, -4+2j, 6-5j])
            assert `mlab._get('a')`.replace(" ", "") == "array([[1.+3.j],\n[-4.+2.j],\n[6.-5.j]])"
            # complex 2D
            mlab._set('a', [[1+3j, -4+2j, 6+5j], [9+3j, 1, 3-2j]])
            assert `mlab._get('a')`.replace(" ", "") == 'array([[1.+3.j,-4.+2.j,6.+5.j],\n[9.+3.j,1.+0.j,3.-2.j]])'
            mlab.clear('a')
        # try basic error handling
        self.failUnlessRaises(TypeError, mlab._set, 'a', [[[1]]])
        self.failUnlessRaises(MlabError, mlab._get, 'dontexist')
        self.failUnlessRaises(MlabError,mlab.round)
        try: # also check errormessage for above
            mlab.round()
        except MlabError, msg:
            assert str(msg).strip() == \
                   'Error using ==> round\nIncorrect number of inputs.'
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
        _optionally_convert""".split():
           self.backup[opt] = mlab.__dict__[opt]
    def tearDown(self):
        """Reset options."""
        mlab.__dict__.update(self.backup)
    def testCallArgs(self):
        mlab._optionally_convert['cell'] = True
        try:
            mlab._clear_call_args = False
            mlab.sin(1.23)
            assert mlab._get('arg0__', True) == 1.23
            mlab._clear_call_args = True
            mlab.sin(1.23)
            assert not 'arg0__' in mlab.who()
        finally:
            mlab._clear_call_args = True            
            mlab._optionally_convert['cell'] = False
    def testSubtler(self):
        """test more subtle stuff"""
        import Numeric
        import os, cPickle
        array = Numeric.array
        # simple strings:
        assert (mlab._do("''"), mlab._do("'foobar'")) == ('', 'foobar')
        assert mlab.sort(1) == Numeric.array([1.])
        assert mlab.sort([3,1,2]) == Numeric.array([1., 2., 3.])
        assert mlab.sort(Numeric.array([3,1,2])) == Numeric.array([1., 2., 3.])
        sct = mlab._do("struct('type',{'big','little'},'color','red','x',{3 4})")
        bct = mlab._do("struct('type',{'BIG','little'},'color','red')")
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
        self.assertRaises(MlabError, mlab._get, 'foo')
        assert `sct` == ("<MlabObjectProxy of matlab-class: 'struct'; "
                         "internal name: 'PROXY_VAL0__'; has parent: no>\n"
                         "1x2 struct array with fields:\n"
                         "    type\n    color\n    x\n\n")
        #FIXME: add tests for assigning and nesting proxies
        mlab._optionally_convert['cell'] = True
        # XXX got no idea where HOME comes from, not there under win
        assert mlab.who() in (['PROXY_VAL0__', 'PROXY_VAL1__'],
                              ['HOME', 'PROXY_VAL0__', 'PROXY_VAL1__'])
        # test pickling
        pickleFilename = os.tempnam()
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
        mlab._optionally_convert['cell'] = False

suite = unittest.TestSuite(map(unittest.makeSuite,
                               (mlabwrapTC,
                                )))
unittest.TextTestRunner().run(suite)

#FIXME strangely enough we can't test this in the function!
import gc
gc.collect()
mlab._optionally_convert['cell'] = True
# XXX got no idea where HOME comes from, not there under win
assert mlab.who() in (['HOME', 'bar'], ['bar'])
mlab._optionally_convert['cell'] = False
