/*
  PYMAT -- A Python module that exposes the MATLAB(TM) engine interface
  and supports passing Numeric arrays back and forth.


  - FIXME:
    * __array__ should also lead to autoconversion
    * rename
    * add test cases (different array types and 0d arrays)
    * remove all dodgy conversion (tuples, lists, nums); 0-d is currently
      unhandled, but if we switch to accept only 2D, that's fine

  Revision History
  ================

  Version 1.1 -- 2003-01-21 Alexander Schmolck (a.schmolck@gmx.net)
  -----------------------------------------------------------------
   * Interface changes:
     - removed (buggy and conceptually dubious) autoconversion of matlab(tm)
       1xN or Nx1 matrices to Numeric flat vectors 1x.
     - added proper error reporting: if something goes wrong during a matlab
       Execution, now a `pymat.error`, is raised (not `RuntimeError`) with an
       appropriate error message (from matlab(tm), if applicable) is raised
       (rather a kludge, thanks to matlab(tm)'s braindead C-interface). Also,
       passing incorrect types to the functions of this module now raises
       TypeErrors. Bizzarre violations (out of matlab(tm)-memory) continue to
       raise RuntimeErrors.
       
   * Bug fixes:
     - fixed serious memory violation bug: conversion of all flat Numeric
       vectors caused illegal memory access (in the copyNumeric... routines).
     - fixed other segfaults that resulted from passing 'wrong' argument types
       to `put` (0-d arrays (now converted), numbers (now converted) and other
       non-array types (now should cause a warning message))
     - removed broken autoconversion (see above)
     
   * Misc:
     - reformated source code
     - reformated and adapted documentation.

  Version 1.0 -- December 26, 1998, Andrew Sterian (asterian@umich.edu)
  ---------------------------------------------------------------------
   * Initial release

  Copyright & Disclaimer
  ======================
  Copyright (c) 2002, 2003 Alexander Schmolck <a.schmolck@gmx.net>

  Copyright (c) 1998,1999 Andrew Sterian. All Rights Reserved. mailto: steriana@gvsu.edu

  Copyright (c) 1998,1999 THE REGENTS OF THE UNIVERSITY OF MICHIGAN. ALL RIGHTS RESERVED 

  Permission to use, copy, modify, and distribute this software and its
  documentation for any purpose and without fee is hereby granted, provided
  that the above copyright notices appear in all copies and that both these
  copyright notices and this permission notice appear in supporting
  documentation, and that the name of The University of Michigan not be used
  in advertising or publicity pertaining to distribution of the software
  without specific, written prior permission.

  THIS SOFTWARE IS PROVIDED AS IS, WITHOUT REPRESENTATION AS TO ITS FITNESS
  FOR ANY PURPOSE, AND WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR
  IMPLIED, INCLUDING WITHOUT LIMITATION THE IMPLIED WARRANTIES OF
  MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. THE REGENTS OF THE
  UNIVERSITY OF MICHIGAN SHALL NOT BE LIABLE FOR ANY DAMAGES, INCLUDING
  SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, WITH RESPECT TO ANY
  CLAIM ARISING OUT OF OR IN CONNECTION WITH THE USE OF THE SOFTWARE, EVEN IF
  IT HAS BEEN OR IS HEREAFTER ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.

*/

#define PYMAT_VERSION "1.0"

// We're not building a MEX file, we're building a standalone app.
#undef MATLAB_MEX_FILE

#ifdef WIN32
#include <windows.h>
#endif

#include <Python.h>
#include <Numeric/arrayobject.h>
#include <stdio.h> // AWMS
#include <engine.h>

#define AND &&
#define OR  ||
#define EQ  ==
#define NEQ !=

#ifndef max
#define max(x,y) ((x) > (y) ? (x) : (y))
#define min(x,y) ((x) < (y) ? (x) : (y))
#endif

static PyObject* pymat_error = PyErr_NewException("pymat.error", NULL, NULL);

static void pyGenericError(PyObject *pException, const char *fmt, ...)
{
  char *lBuf = new char[2*strlen(fmt) + 1024];

  va_list ap;
  va_start(ap, fmt);
  vsprintf(& lBuf[0], fmt, ap);
  va_end(ap);

  strcat(& lBuf[0], "\n");

  PyErr_SetString(pException, & lBuf[0]);
  delete [] lBuf;
}

#define pyassert(x,y) if (! (x)) { _pyassert(y); goto error_return; }

static void _pyassert(const char *pStr)
{
  PyErr_SetString(PyExc_RuntimeError, pStr);
}

//////////////////////////////////////////////////////////////////////////////

static PyStringObject *mx2char(const mxArray *pArray)
{
  int buflen;
  char *buf;
  PyStringObject *lRetval;

  buflen = mxGetM(pArray)*mxGetN(pArray) + 1;
  buf = (char *)mxCalloc(buflen, sizeof(char));
  pyassert(buf, "Out of MATLAB(TM) memory");

  if (mxGetString(pArray, buf, buflen)) {
    pyGenericError(pymat_error, "Unable to extract MATLAB(TM) string");
    mxFree(buf);
    return 0;
  }

  lRetval = (PyStringObject *)PyString_FromString(buf);
  mxFree(buf);
  return lRetval;

 error_return:
  return 0;
}

static PyArrayObject *mx2numeric(const mxArray *pArray)
{
  int nd;
  const int *dims;
  PyArrayObject *lRetval = 0;
  int lRows, lCols;
  const double *lPR;
  const double *lPI;

  pyassert(PyArray_API, 
           "Unable to perform this function without NumPy installed");

  nd = mxGetNumberOfDimensions(pArray);
  if (nd > 2) {
    pyGenericError(PyExc_TypeError, 
                   "Only 1-D and 2-D arrays are currently supported");
    return 0;
  }

  dims = mxGetDimensions(pArray);
  lRetval = (PyArrayObject *)PyArray_FromDims(nd, const_cast<int *>(dims), 
                                              mxIsComplex(pArray) ? 
                                              PyArray_CDOUBLE : PyArray_DOUBLE);
  if (lRetval EQ 0) return 0;

  lRows = mxGetM(pArray);
  lCols = mxGetN(pArray);
  lPR = mxGetPr(pArray);
  if (mxIsComplex(pArray)) {
    lPI = mxGetPi(pArray);

    for (int lCol = 0; lCol < lCols; lCol++) {
      double *lDst = (double *)(lRetval->data) + 2*lCol;
      for (int lRow = 0; lRow < lRows; lRow++, lDst += 2*lCols) {
        lDst[0] = *lPR++;
        lDst[1] = *lPI++;
      }
    }
  } else {
    for (int lCol = 0; lCol < lCols; lCol++) {
      double *lDst = (double *)(lRetval->data) + lCol;
      for (int lRow = 0; lRow < lRows; lRow++, lDst += lCols) {
        *lDst = *lPR++;
      }
    }
  }

  return lRetval;

 error_return:
  return 0;
}

template <class T>
inline void copyNumericVector2Mx(T *pSrc, int pRows, double *pDst, int *pStrides)
{
  // this is a horrible HACK for 0-D arrays (which have no strides);
  // it should also work for shape (1,) 1D arrays.
  // XXX: check that 1Ds are always OK!
  if (pRows == 1){               
    *pDst = *pSrc;
    return;
  }
  int lRowDelta = pStrides[0]/sizeof(T);
  for (int lRow=0; lRow < pRows; lRow++, pSrc += lRowDelta) {
    *pDst++ = *pSrc;
  }
}

template <class T>
inline void copyNumeric2Mx(T *pSrc, int pRows, int pCols, double *pDst, int *pStrides)
{
  int lRowDelta = pStrides[1]/sizeof(T);
  int lColDelta = pStrides[0]/sizeof(T);
  for (int lCol=0; lCol < pCols; lCol++) {
    T *lSrc = pSrc + lCol*lRowDelta;
    for (int lRow=0; lRow < pRows; lRow++, lSrc += lColDelta) {
      *pDst++ = *lSrc;
    }
  }
}
template <class T>
inline void copyCplxNumericVector2Mx(T *pSrc, int pRows, double *pRData, 
                              double *pIData, int *pStrides)
{
  int lRowDelta = pStrides[0]/sizeof(T);
  for (int lRow=0; lRow < pRows; lRow++, pSrc += lRowDelta) {
    *pRData++ = pSrc[0];
    *pIData++ = pSrc[1];
  }
}

template <class T>
inline void copyCplxNumeric2Mx(T *pSrc, int pRows, int pCols, double *pRData, 
                        double *pIData, int *pStrides)
{
  int lRowDelta = pStrides[1]/sizeof(T);
  int lColDelta = pStrides[0]/sizeof(T);

  for (int lCol=0; lCol < pCols; lCol++) {
    T *lSrc = pSrc + lCol*lRowDelta;
    for (int lRow=0; lRow < pRows; lRow++, lSrc += lColDelta) {
      *pRData++ = lSrc[0];
      *pIData++ = lSrc[1];
    }
  }
}

static mxArray *makeMxFromNumeric(const PyArrayObject *pSrc)
{
  int lRows, lCols;
  bool lIsComplex;
  bool lIsNotAMatrix = false;
  double *lR = 0;
  double *lI = 0;
  mxArray *lRetval = 0;
    
  switch (pSrc->nd) {
  case 0:                       // XXX the evil 0D
    lRows = 1;
    lCols = 1;
    lIsNotAMatrix = true;
    break;
  case 1:
    lRows = pSrc->dimensions[0];
    lCols = min(1, lRows); // for array([]): to avoid zeros((0,1)) !
    lIsNotAMatrix = true;       
    break;
  case 2:
    lCols = pSrc->dimensions[1];
    lRows = pSrc->dimensions[0];
    break;
  default:
    char strbuff[1024];
    sprintf(strbuff, 
            "Only arrays with up to 2D are currently supported (not %dD)",
            pSrc->nd);
    PyErr_SetString(PyExc_TypeError, strbuff);
    goto error_return;
  }

  switch (pSrc->descr->type_num) {
  case PyArray_OBJECT:
    pyGenericError(PyExc_TypeError, "Non-numeric array types not supported");
    return 0;
        
  case PyArray_CFLOAT:
  case PyArray_CDOUBLE:
    lIsComplex = true;
    break;
        
  default:
    lIsComplex = false;
  }
    
  lRetval = mxCreateDoubleMatrix(lRows, lCols, lIsComplex ? mxCOMPLEX : mxREAL);

  if (lRetval EQ 0) return 0;

  lR = mxGetPr(lRetval);
  lI = mxGetPi(lRetval);
  if (lIsNotAMatrix) {
    switch (pSrc->descr->type_num) {
    case PyArray_CHAR:
      copyNumericVector2Mx((char *)(pSrc->data), lRows, lR, pSrc->strides);
      break;

    case PyArray_UBYTE:
      copyNumericVector2Mx((unsigned char *)(pSrc->data), lRows, lR, pSrc->strides);
      break;

    case PyArray_SBYTE:
      copyNumericVector2Mx((signed char *)(pSrc->data), lRows, lR, pSrc->strides);
      break;

    case PyArray_SHORT: 
      copyNumericVector2Mx((short *)(pSrc->data), lRows, lR, pSrc->strides);
      break;

    case PyArray_INT:
      copyNumericVector2Mx((int *)(pSrc->data), lRows, lR, pSrc->strides);
      break;

    case PyArray_LONG:
      copyNumericVector2Mx((long *)(pSrc->data), lRows, lR, pSrc->strides);
      break;

    case PyArray_FLOAT:
      copyNumericVector2Mx((float *)(pSrc->data), lRows, lR, pSrc->strides);
      break;

    case PyArray_DOUBLE:
      copyNumericVector2Mx((double *)(pSrc->data), lRows, lR, pSrc->strides);
      break;

    case PyArray_CFLOAT:
      copyCplxNumericVector2Mx((float *)(pSrc->data), lRows, lR, lI, pSrc->strides);
      break;

    case PyArray_CDOUBLE:
      copyCplxNumericVector2Mx((double *)(pSrc->data), lRows, lR, lI, pSrc->strides);
      break;
    }
  } else {
    switch (pSrc->descr->type_num) {
    case PyArray_CHAR:
      copyNumeric2Mx((char *)(pSrc->data), lRows, lCols, lR, pSrc->strides);
      break;

    case PyArray_UBYTE:
      copyNumeric2Mx((unsigned char *)(pSrc->data), lRows, lCols, lR, pSrc->strides);
      break;

    case PyArray_SBYTE:
      copyNumeric2Mx((signed char *)(pSrc->data), lRows, lCols, lR, pSrc->strides);
      break;

    case PyArray_SHORT: 
      copyNumeric2Mx((short *)(pSrc->data), lRows, lCols, lR, pSrc->strides);
      break;

    case PyArray_INT:
      copyNumeric2Mx((int *)(pSrc->data), lRows, lCols, lR, pSrc->strides);
      break;

    case PyArray_LONG:
      copyNumeric2Mx((long *)(pSrc->data), lRows, lCols, lR, pSrc->strides);
      break;

    case PyArray_FLOAT:
      copyNumeric2Mx((float *)(pSrc->data), lRows, lCols, lR, pSrc->strides);
      break;

    case PyArray_DOUBLE:
      copyNumeric2Mx((double *)(pSrc->data), lRows, lCols, lR, pSrc->strides);
      break;

    case PyArray_CFLOAT:
      copyCplxNumeric2Mx((float *)(pSrc->data), lRows, lCols, lR, lI, pSrc->strides);
      break;

    case PyArray_CDOUBLE:
      copyCplxNumeric2Mx((double *)(pSrc->data), lRows, lCols, lR, lI, pSrc->strides);
      break;
    }
  }
  return lRetval;

 error_return:
  return 0;
}

static mxArray *makeMxFromSeq(const PyObject *pSrc)
{
  mxArray *lRetval = 0;
  int i, lSize;

  PyArrayObject *lArray = 
    (PyArrayObject *) PyArray_ContiguousFromObject(const_cast<PyObject *>(pSrc), 
                                                   PyArray_CDOUBLE, 0, 0);
  if (lArray EQ 0) return 0;

  // If all imaginary components are 0, this is not a complex array.
  lSize = PyArray_SIZE(lArray);
  // Get at first imaginary element
  const double *lPtr = (const double *)(lArray->data) + 1;
  for (i=0; i < lSize; i++, lPtr += 2) {
    if (*lPtr NEQ 0.0) break;
  }
  if (i >= lSize) {
    PyArrayObject *lNew = (PyArrayObject *)PyArray_Cast(lArray, PyArray_DOUBLE);
    Py_DECREF(lArray);
    lArray = lNew;
  }

  lRetval = makeMxFromNumeric(lArray);
  Py_DECREF(lArray);

  return lRetval;
}
// XXX de const'ed pSrc
static mxArray *numeric2mx(PyObject *pSrc)
{
  mxArray *lDst = 0;

  pyassert(PyArray_API, "Unable to perform this function without NumPy installed");

  if (PyArray_Check(pSrc)) {
    lDst = makeMxFromNumeric((const PyArrayObject *)pSrc);
  } else if (PySequence_Check(pSrc)) {
    lDst = makeMxFromSeq(pSrc);
  } else if (PyObject_HasAttrString(pSrc, "__array__")) {
    PyObject *arp;
    arp = PyObject_CallMethod(pSrc, "__array__", NULL);
    lDst = makeMxFromNumeric((const PyArrayObject *)arp);
    Py_DECREF(arp);             // FIXME check this is correct;
  } 
    else if (PyInt_Check(pSrc) || PyLong_Check(pSrc) ||
             PyFloat_Check(pSrc) || PyComplex_Check(pSrc)){
    PyObject *t;
    t = PyTuple_New(1);
    PyTuple_SetItem(t, 0, pSrc);
    lDst = makeMxFromSeq(t);
  } else {
    
  }
  return lDst;

 error_return:
  return 0;
  }

static mxArray *char2mx(const PyObject *pSrc)
{
  mxArray *lDst = 0;

  lDst = mxCreateString(PyString_AsString(const_cast<PyObject *>(pSrc)));
  if (lDst EQ 0) {
    pyGenericError(pymat_error, "Unable to create MATLAB(TM) string");
    return 0;
  }

  return lDst;
}

//////////////////////////////////////////////////////////////////////////////
static char open_doc[] = 
#ifdef WIN32
"open() -> handle\n"
"\n"
"Opens a MATLAB(TM) engine session\n"
"This function returns a handle to a new MATLAB(TM) engine session.\n"
"For compatibility with the UNIX version of the PyMat module, this\n"
"function takes a single optional string parameter, but this parameter\n"
"is always ignored under Win32.\n"
#else
"open([str]) -> handle\n"
"\n"
"Opens a MATLAB(TM) engine session\n"
"This function returns a handle to a new MATLAB(TM) engine session.\n"
"The optional 'str' parameter determines how MATLAB(TM) is started.\n"
"If empty or not specified, the session is started by executing\n"
"the simple command 'matlab'. Other options include specifying\n"
"a host name or a verbatim string to use to invoke the MATLAB\n"
"program. See the `engOpen()` documentation in the MATLAB(TM) API\n"
"reference for more information.\n"
#endif
;

PyObject * pymat_open(PyObject *, PyObject *args)
{
  Engine *ep;
  char *lStr = 0;
  if (! PyArg_ParseTuple(args, "|s:open", &lStr)) return 0;

  pyassert(sizeof(int) >= sizeof(Engine *), 
         "Oops! Pointers on this architecture are too big to fit in integers");

#ifdef WIN32
  ep = engOpen(NULL);
#else
  ep = engOpen(lStr);
#endif
  if (ep EQ 0) {
    pyGenericError(pymat_error, "Unable to start MATLAB(TM) engine");
    return 0;
  }

  return Py_BuildValue("i", int(ep));

 error_return:
  return 0;
}

static char close_doc[] = 
"close(handle)\n"
"\n"
"Closes MATLAB(TM) session\n"
"\n"
"This function closes the MATLAB(TM) session whose handle was returned\n"
"by a previous call to open().\n"
;
PyObject * pymat_close(PyObject *, PyObject *args)
{
  int lHandle;

  if (! PyArg_ParseTuple(args, "i:close", &lHandle)) return 0;

  if (engClose((Engine *)lHandle) NEQ 0) {
    pyGenericError(pymat_error, "Unable to close session");
    return 0;
  }

  Py_INCREF(Py_None);
  return Py_None;
}
// #define BUFSIZE 10000
static char eval_doc[] = 
"eval(handle, string) -> str\n"
"\n"
"Evaluates string in MATLAB(TM) session\n"
"This function evaluates the given string in the MATLAB(TM) session\n"
"associated with the handle. The handle is returned from a previous\n"
"call to open().\n"
"\n"
"The output of the command is returned as a string.\n"
"\n"
"If there is an error a `pymat.error` with the error description is raised.\n"
;

PyObject * pymat_eval(PyObject *, PyObject *args)
{
  //XXX how large should this be?
  const int  BUFSIZE=10000;
  char buffer[BUFSIZE];
  char *lStr;
  char *retStr;
  PyObject *ret;
  int lHandle;
    
  if (! PyArg_ParseTuple(args, "is:eval", &lHandle, &lStr)) return 0;
  engOutputBuffer((Engine *)lHandle, buffer, BUFSIZE-1);
  if (engEvalString((Engine *)lHandle, lStr) NEQ 0) {
    pyGenericError(pymat_error, 
                   "Unable to evaluate string in MATLAB(TM) workspace");
    return 0;
  }
  // "??? " is how an error message begins in matlab
  // obviously there is no proper way to test whether a command was
  // succesful... AAARGH
  if (strstr(buffer, ">> ??? ") EQ buffer) {
    pyGenericError(pymat_error, buffer);
    return 0;
  }
  // AWMS XXX skip first three chars of prompt
  if (strcmp(">> ", buffer) <= 0)
    retStr = buffer + 3;
  else
    retStr = buffer;
  ret = (PyObject *)PyString_FromString(retStr);
  return ret;
}

static char get_doc[] = 
"get(handle, name) -> array\n"
"\n"
"Gets a matrix from the MATLAB(TM) session\n"
"\n"
"This function extracts the matrix with the given name from a MATLAB\n"
"session associated with the handle. The handle is the return value from\n"
"a previous call to open(). The name parameter must be a string describing\n"
"the name of a matrix in the MATLAB(TM) workspace. On Win32 platforms,\n"
"only double-precision floating point arrays (real or complex) are supported.\n"
"1-D character strings are supported on UNIX platforms.\n"
"\n"
"Only 2-dimensional arrays are currently supported. Cell\n"
"arrays, structure arrays, etc. are not yet supported.\n"
"\n"
"The return value is a NumPy array with the same shape and elements as the\n"
"MATLAB(TM) array.\n"
;
PyObject * pymat_get(PyObject *, PyObject *args)
{
  char *lName;
  int lHandle;
  mxArray *lArray = 0;
  PyObject *lDest = 0;

  if (! PyArg_ParseTuple(args, "is:get", &lHandle, &lName)) return 0;

  lArray = engGetArray((Engine *)lHandle, lName);
  if (lArray EQ 0) {
    pyGenericError(pymat_error, 
                   "Unable to get matrix from MATLAB(TM) workspace");
    return 0;
  }

  if (mxIsChar(lArray)) {
    lDest = (PyObject *)mx2char(lArray);
  } else if (mxIsDouble(lArray)) {
    lDest = (PyObject *)mx2numeric(lArray);
  } else {                      // FIXME and numbers... and sequences...
    pyGenericError(PyExc_TypeError, "Only strings and Numeric arrays are supported.");
    return 0;
  }
  mxDestroyArray(lArray);

  return lDest;
}

static char put_doc[] = 
"put(handle, name, array).\n"
"\n"
"Places a matrix into the MATLAB(TM) session.\n"
"This function places the given array into a MATLAB(TM) workspace under the\n"
"name given with the 'name' parameter (which must be a string). The handle\n"
"is a value previously obtained from a call to open().\n"
"\n"
"The 'array' parameter must be either a NumPy array, list, or tuple\n"
"containing numbers, or a number, or a string. The MATLAB(TM) \n"
"array will have the same shape and values, with the following\n"
"exceptions: the element type will always double or complex and the\n"
"array-rank will always be 2 (i.e. a matrix).\n"
"\n"
"A string parameter is converted to a MATLAB char-valued array.\n"
;
PyObject * pymat_put(PyObject *, PyObject *args)
{
  char *lName;
  int lHandle;
  PyObject *lSource;
  mxArray *lArray = 0;

  if (! PyArg_ParseTuple(args, "isO:put", &lHandle, &lName, &lSource)) return 0;
  Py_INCREF(lSource);

  if (PyString_Check(lSource)) {
    lArray = char2mx(lSource);
  } else {
    lArray = numeric2mx(lSource);
  }
  Py_DECREF(lSource);

  if (lArray EQ 0) {
    return 0;   // Above converter already set error message
  }

  mxSetName(lArray, lName);

  if (engPutArray((Engine *)lHandle, lArray) NEQ 0) {
    pyGenericError(pymat_error, 
                   "Unable to put matrix into MATLAB(TM) workspace");
    mxDestroyArray(lArray);
    return 0;
  }

  //mxDestroyArray(lArray);

  Py_INCREF(Py_None);
  return Py_None;
}

static PyMethodDef PymatMethods[] = {
  { "open",       pymat_open,       1, open_doc },
  { "close",      pymat_close,      1, close_doc },
  { "eval",       pymat_eval,       1, eval_doc },
  { "get",        pymat_get,        1, get_doc },
  { "put",        pymat_put,        1, put_doc },
  { 0, 0}
};

extern "C" void initpymat(void);

void initpymat(void)
{
  PyObject *module = 
    Py_InitModule4("pymat",
      PymatMethods,
"PyMat -- Low-level MATLAB(tm) Engine Interface\n"
"\n"
"  open  - Open a MATLAB(tm) engine session\n"
"  close - Close a MATLAB(tm) engine session\n"
"  eval  - Evaluates a string in the MATLAB(tm) session\n"
"  get   - Gets a matrix from the MATLAB(tm) session\n"
"  put   - Places a matrix into the MATLAB(tm) session\n"
"\n"



"The Numeric package must be installed for this module to be used.\n"
"\n"
"Copyright & Disclaimer\n"
"======================\n"
"Copyright (c) 2002, 2003 Alexander Schmolck <a.schmolck@gmx.net>\n"
"\n"
"Copyright (c) 1998,1999 Andrew Sterian. All Rights Reserved. mailto: steriana@gvsu.edu\n"
"\n"
"Copyright (c) 1998,1999 THE REGENTS OF THE UNIVERSITY OF MICHIGAN. ALL RIGHTS RESERVED \n"
"\n"
"Permission to use, copy, modify, and distribute this software and its\n"
"documentation for any purpose and without fee is hereby granted, provided\n"
"that the above copyright notices appear in all copies and that both these\n"
"copyright notices and this permission notice appear in supporting\n"
"documentation, and that the name of The University of Michigan not be used\n"
"in advertising or publicity pertaining to distribution of the software\n"
"without specific, written prior permission.\n"
"\n"
"THIS SOFTWARE IS PROVIDED AS IS, WITHOUT REPRESENTATION AS TO ITS FITNESS\n"
"FOR ANY PURPOSE, AND WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR\n"
"IMPLIED, INCLUDING WITHOUT LIMITATION THE IMPLIED WARRANTIES OF\n"
"MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. THE REGENTS OF THE\n"
"UNIVERSITY OF MICHIGAN SHALL NOT BE LIABLE FOR ANY DAMAGES, INCLUDING\n"
"SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, WITH RESPECT TO ANY\n"
"CLAIM ARISING OUT OF OR IN CONNECTION WITH THE USE OF THE SOFTWARE, EVEN IF\n"
"IT HAS BEEN OR IS HEREAFTER ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.\n"
"\n",
       0,
       PYTHON_API_VERSION);

  /* This macro, defined in arrayobject.h, loads the Numeric API interface */
  import_array();

  PyObject *dict = PyModule_GetDict(module);
  PyObject *item = PyString_FromString(PYMAT_VERSION);
  PyDict_SetItemString(dict, "__version__", item);
  Py_XDECREF(item);
  PyDict_SetItemString(dict, "error", pymat_error);
}
