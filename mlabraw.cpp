/*
    PYMAT -- A Python module that exposes the MATLAB engine interface
             and supports passing NumPy arrays back and forth.

  Revision History
  ----------------

  Version 1.0 -- December 26, 1998, Andrew Sterian (asterian@umich.edu)
     * Initial release
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
    pyassert(buf, "Out of MATLAB memory");

    if (mxGetString(pArray, buf, buflen)) {
        pyGenericError(PyExc_RuntimeError, "Unable to extract MATLAB string");
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
    int lMyDim;
    PyArrayObject *lRetval = 0;
    int lRows, lCols;
    const double *lPR;
    const double *lPI;

    pyassert(PyArray_API, "Unable to perform this function without NumPy installed");

    nd = mxGetNumberOfDimensions(pArray);
    if (nd > 2) {
        pyGenericError(PyExc_RuntimeError, "Only 1-D and 2-D arrays are currently supported");
        return 0;
    }

    dims = mxGetDimensions(pArray);

//     if ((nd EQ 2 AND dims[0] EQ 1 OR dims[1] EQ 1) AND (dims[0] != 0 AND dims[1] != 0)) { //AWMS
//         // It's really 1-D
//         lMyDim = max(dims[0], dims[1]);
//         dims = & lMyDim;
//         nd=1;
//     }

    lRetval = (PyArrayObject *)PyArray_FromDims(nd, const_cast<int *>(dims), 
                            mxIsComplex(pArray) ? PyArray_CDOUBLE : PyArray_DOUBLE);
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
void copyNumeric2Mx(T *pSrc, int pRows, int pCols, double *pDst, int *pStrides)
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
void copyCplxNumeric2Mx(T *pSrc, int pRows, int pCols, double *pRData, double *pIData, int *pStrides)
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
    double *lR = 0;
    double *lI = 0;
    mxArray *lRetval = 0;

    pyassert(pSrc->nd <= 2, "Only 1D or 2D arrays are currently supported");

    lRows = pSrc->dimensions[0];
    if (pSrc->nd < 2) {
        lCols = 1;
    } else {
        lCols = pSrc->dimensions[1];
    }

    switch (pSrc->descr->type_num) {
    case PyArray_OBJECT:
        pyGenericError(PyExc_RuntimeError, "Non-numeric array types not supported");
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

    return lRetval;

error_return:
    return 0;
}

static mxArray *makeMxFromSeq(const PyObject *pSrc)
{
    mxArray *lRetval = 0;
    int i, lSize;

    PyArrayObject *lArray = (PyArrayObject *)PyArray_ContiguousFromObject(const_cast<PyObject *>(pSrc), PyArray_CDOUBLE, 0, 0);
    if (lArray EQ 0) return 0;

    // If all imaginary components are 0, this is not a complex array.
    lSize = PyArray_SIZE(lArray);
    const double *lPtr = (const double *)(lArray->data) + 1;  // Get at first imaginary element
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

static mxArray *numeric2mx(const PyObject *pSrc)
{
    mxArray *lDst = 0;

    pyassert(PyArray_API, "Unable to perform this function without NumPy installed");

    if (PyArray_Check(pSrc)) {
        lDst = makeMxFromNumeric((const PyArrayObject *)pSrc);
    } else {
        lDst = makeMxFromSeq(pSrc);
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
        pyGenericError(PyExc_RuntimeError, "Unable to create MATLAB string");
        return 0;
    }

    return lDst;
}

//////////////////////////////////////////////////////////////////////////////
static char open_doc[] = 
#ifdef WIN32
"handle open() : Opens a MATLAB engine session\n"
"\n"
"This function returns a handle to a new MATLAB engine session.\n"
"For compatibility with the UNIX version of the PyMat module, this\n"
"function takes a single optional string parameter, but this parameter\n"
"is always ignored under Win32.\n"
#else
"handle open([str]) : Opens a MATLAB engine session\n"
"\n"
"This function returns a handle to a new MATLAB engine session.\n"
"The optional 'str' parameter determines how MATLAB is started.\n"
"If empty or not specified, the session is started by executing\n"
"the simple command 'matlab'. Other options include specifying\n"
"a host name or a verbatim string to use to invoke the MATLAB\n"
"program. See the engOpen() documentation in the MATLAB API\n"
"reference for more information.\n"
#endif
;

PyObject * pymat_open(PyObject *, PyObject *args)
{
	Engine *ep;
    char *lStr = 0;
    puts("C###DEBUG opening session");
	if (! PyArg_ParseTuple(args, "|s:open", &lStr)) return 0;

    pyassert(sizeof(int) >= sizeof(Engine *), "Oops! Pointers on this architecture are too big to fit in integers");

#ifdef WIN32
    ep = engOpen(NULL);
#else
    ep = engOpen(lStr);
#endif
    if (ep EQ 0) {
        pyGenericError(PyExc_RuntimeError, "Unable to start MATLAB engine");
        return 0;
    }

    return Py_BuildValue("i", int(ep));

error_return:
    return 0;
}

static char close_doc[] = 
"void close(handle) : Closes MATLAB session\n"
"\n"
"This function closes the MATLAB session whose handle was returned\n"
"by a previous call to open().\n"
;
PyObject * pymat_close(PyObject *, PyObject *args)
{
	int lHandle;

	if (! PyArg_ParseTuple(args, "i:close", &lHandle)) return 0;

    if (engClose((Engine *)lHandle) NEQ 0) {
        pyGenericError(PyExc_RuntimeError, "Unable to close session");
        return 0;
    }

	Py_INCREF(Py_None);
	return Py_None;
}

static char eval_doc[] = 
"void eval(handle, string) : Evaluates string in MATLAB session\n"
"\n"
"This function evaluates the given string in the MATLAB session\n"
"associated with the handle. The handle is returned from a previous\n"
"call to open().\n"
"\n"
"Note that this routine always succeeds without any exceptions unless\n"
"the handle is invalid, EVEN IF THE STRING EVALUATION FAILED IN THE\n"
"MATLAB WORKSPACE!\n"
;

PyObject * pymat_eval(PyObject *, PyObject *args)
{
	char *lStr;
    int lHandle;
    
	if (! PyArg_ParseTuple(args, "is:eval", &lHandle, &lStr)) return 0;

    if (engEvalString((Engine *)lHandle, lStr) NEQ 0) {
        pyGenericError(PyExc_RuntimeError, "Unable to evaluate string in MATLAB workspace");
        return 0;
    }
    

    Py_INCREF(Py_None);
    return Py_None;
}

static char get_doc[] = 
"array get(handle, name) : Gets a matrix from the MATLAB session\n"
"\n"
"This function extracts the matrix with the given name from a MATLAB\n"
"session associated with the handle. The handle is the return value from\n"
"a previous call to open(). The name parameter must be a string describing\n"
"the name of a matrix in the MATLAB workspace. On Win32 platforms,\n"
"only double-precision floating point arrays (real or complex) are supported.\n"
"1-D character strings are supported on UNIX platforms.\n"
"\n"
"Only 1-dimensional and 2-dimensional arrays are currently supported. Cell\n"
"arrays, structure arrays, etc. are not yet supported.\n"
"\n"
"The return value is a NumPy array with the same shape and elements as the\n"
"MATLAB array.\n"
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
        pyGenericError(PyExc_RuntimeError, "Unable to get matrix from MATLAB workspace");
        return 0;
    }

    if (mxIsChar(lArray)) {
        lDest = (PyObject *)mx2char(lArray);
    } else if (mxIsDouble(lArray)) {
        lDest = (PyObject *)mx2numeric(lArray);
    } else {
        pyGenericError(PyExc_RuntimeError, "Only floating-point and character arrays are currently supported");
    }
    mxDestroyArray(lArray);

    return lDest;
}

static char put_doc[] = 
"void put(handle, name, array) : Places a matrix into the MATLAB session\n"
"\n"
"This function places the given array into a MATLAB workspace under the\n"
"name given with the 'name' parameter (which must be a string). The handle\n"
"is a value previously obtained from a call to open().\n"
"\n"
"The 'array' parameter must be either a NumPy array, list, or tuple\n"
"containing real or complex numbers, or a string. The MATLAB array will\n"
"have the same shape and same values, after conversion to double-precision\n"
"floating point, if necessary. A string parameter is converted to a MATLAB\n"
"char-valued array.\n"
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
        pyGenericError(PyExc_RuntimeError, "Unable to put matrix into MATLAB workspace");
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
    PyObject *module = Py_InitModule4("pymat",
                    PymatMethods,
"PyMat -- MATLAB Engine Interface\n"
"\n"
"  open  - Open a MATLAB engine session\n"
"  close - Close a MATLAB engine session\n"
"  eval  - Evaluates a string in the MATLAB session\n"
"  get   - Gets a matrix from the MATLAB session\n"
"  put   - Places a matrix into the MATLAB session\n"
"\n"
"The NumPy Numeric package must be installed for this module to be used.\n"
,
					0,
					PYTHON_API_VERSION);

    /* This macro, defined in arrayobject.h, loads the Numeric API interface */
    import_array();

    PyObject *dict = PyModule_GetDict(module);
    PyObject *item = PyString_FromString(PYMAT_VERSION);
    PyDict_SetItemString(dict, "__version__", item);
    Py_XDECREF(item);
}
