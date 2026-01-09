# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True

import numpy as np
cimport numpy as np
from cython.parallel import prange
from libc.stdlib cimport malloc, free

# Define types
ctypedef unsigned char uint8_t
ctypedef int int32_t

# ═══════════════════════════════════════════════════════════════════════
# STAGE 1: BLC/SLC CORRECTION (Multi-threaded)
# ═══════════════════════════════════════════════════════════════════════

def apply_blc_slc_fast(
    np.ndarray[uint8_t, ndim=3] frame,
    np.ndarray[int32_t, ndim=2] blc_r,
    np.ndarray[int32_t, ndim=2] blc_g,
    np.ndarray[int32_t, ndim=2] blc_b,
    np.ndarray[int32_t, ndim=2] slc_diff_r,
    np.ndarray[int32_t, ndim=2] slc_diff_g,
    np.ndarray[int32_t, ndim=2] slc_diff_b
):
    """
    Fast BLC/SLC correction with multi-threading
    Formula: corrected = (raw - BLC) × 255 ÷ (SLC - BLC)
    """
    cdef int height = frame.shape[0]
    cdef int width = frame.shape[1]
    cdef int y, x
    cdef int val, corrected
    
    # Process in parallel (each thread handles different rows)
    with nogil:
        # Blue channel
        for y in prange(height, schedule='static'):
            for x in range(width):
                val = frame[y, x, 0]
                corrected = (val - blc_b[y, x]) * 255 // slc_diff_b[y, x]
                if corrected < 0:
                    corrected = 0
                elif corrected > 255:
                    corrected = 255
                frame[y, x, 0] = <uint8_t>corrected
        
        # Green channel
        for y in prange(height, schedule='static'):
            for x in range(width):
                val = frame[y, x, 1]
                corrected = (val - blc_g[y, x]) * 255 // slc_diff_g[y, x]
                if corrected < 0:
                    corrected = 0
                elif corrected > 255:
                    corrected = 255
                frame[y, x, 1] = <uint8_t>corrected
        
        # Red channel
        for y in prange(height, schedule='static'):
            for x in range(width):
                val = frame[y, x, 2]
                corrected = (val - blc_r[y, x]) * 255 // slc_diff_r[y, x]
                if corrected < 0:
                    corrected = 0
                elif corrected > 255:
                    corrected = 255
                frame[y, x, 2] = <uint8_t>corrected


# ═══════════════════════════════════════════════════════════════════════
# STAGE 2: GLC CORRECTION (Multi-threaded)
# ═══════════════════════════════════════════════════════════════════════

cdef inline int glc_correct_pixel(int c, int g) nogil:
    """
    GLC correction for single pixel
    Matches frmGenRGB.cs lines 458-532
    """
    cdef int maxv = 255
    cdef int mid = 127
    cdef int midp = 128
    cdef int result, denom
    
    if g == 0:
        return c
    
    # Clamp g
    if g < 0:
        g = 0
    elif g > maxv:
        g = maxv
    
    if g < mid:
        # Dark region
        if g < 1:
            g = 1
        
        if c > g:
            denom = maxv - g
            if denom > 0:
                result = mid + ((c - g) * midp) // denom
            else:
                result = mid
        else:
            result = (c * mid) // g
    
    elif g > mid:
        # Bright region
        if g < 1:
            g = 1
        
        if c > g:
            denom = maxv - g
            if denom > 0:
                result = mid + ((c - g) * mid) // denom
            else:
                result = maxv
        else:
            result = (c * midp) // g
    else:
        result = c
    
    # Clamp result
    if result < 0:
        return 0
    elif result > maxv:
        return maxv
    return result


def apply_glc_fast(
    np.ndarray[uint8_t, ndim=3] frame,
    np.ndarray[int32_t, ndim=2] glc_r,
    np.ndarray[int32_t, ndim=2] glc_g,
    np.ndarray[int32_t, ndim=2] glc_b
):
    """Fast GLC correction with multi-threading"""
    cdef int height = frame.shape[0]
    cdef int width = frame.shape[1]
    cdef int y, x, val
    
    with nogil:
        # Blue channel
        for y in prange(height, schedule='static'):
            for x in range(width):
                val = frame[y, x, 0]
                frame[y, x, 0] = <uint8_t>glc_correct_pixel(val, glc_b[y, x])
        
        # Green channel
        for y in prange(height, schedule='static'):
            for x in range(width):
                val = frame[y, x, 1]
                frame[y, x, 1] = <uint8_t>glc_correct_pixel(val, glc_g[y, x])
        
        # Red channel
        for y in prange(height, schedule='static'):
            for x in range(width):
                val = frame[y, x, 2]
                frame[y, x, 2] = <uint8_t>glc_correct_pixel(val, glc_r[y, x])


# ═══════════════════════════════════════════════════════════════════════
# STAGE 3: DARK GLC CORRECTION (Multi-threaded)
# ═══════════════════════════════════════════════════════════════════════

cdef inline int dark_glc_correct_pixel(int c, int dg) nogil:
    """
    Dark GLC correction for single pixel
    Matches frmGenRGB.cs lines 1226-1291
    """
    cdef int maxv = 255
    cdef int quarter = 64
    cdef int half = 128
    cdef int a = c
    cdef float glc_corr
    
    if dg == 0:
        return c
    
    if dg < quarter:
        # Very dark
        if (c > dg) and (c < half):
            c = quarter + <int>(<float>(c - dg) / ((<float>(half - dg) / <float>quarter)))
        elif c < quarter:
            if dg > 0:
                glc_corr = <float>quarter / <float>dg
                c = <int>(<float>c * glc_corr)
    
    elif (dg > quarter) and (dg < half):
        # Moderately dark
        if c > dg:
            glc_corr = <float>quarter / <float>(half - dg)
            c = quarter + <int>(<float>(c - dg) * glc_corr)
            c = (a + c) >> 1  # Blend
        else:
            c = <int>(<float>c / (<float>dg / <float>quarter))
            c = (a + c) >> 1  # Blend
    
    # Clamp
    if c > maxv:
        c = maxv
    if c < 0:
        c = 0
    
    return c


def apply_dark_glc_fast(
    np.ndarray[uint8_t, ndim=3] frame,
    np.ndarray[int32_t, ndim=2] dark_glc_r,
    np.ndarray[int32_t, ndim=2] dark_glc_g,
    np.ndarray[int32_t, ndim=2] dark_glc_b
):
    """Fast Dark GLC correction with multi-threading"""
    cdef int height = frame.shape[0]
    cdef int width = frame.shape[1]
    cdef int y, x, val
    
    with nogil:
        # Blue channel
        for y in prange(height, schedule='static'):
            for x in range(width):
                val = frame[y, x, 0]
                frame[y, x, 0] = <uint8_t>dark_glc_correct_pixel(val, dark_glc_b[y, x])
        
        # Green channel
        for y in prange(height, schedule='static'):
            for x in range(width):
                val = frame[y, x, 1]
                frame[y, x, 1] = <uint8_t>dark_glc_correct_pixel(val, dark_glc_g[y, x])
        
        # Red channel
        for y in prange(height, schedule='static'):
            for x in range(width):
                val = frame[y, x, 2]
                frame[y, x, 2] = <uint8_t>dark_glc_correct_pixel(val, dark_glc_r[y, x])
