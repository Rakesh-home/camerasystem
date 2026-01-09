#include "rgb_correction.h"
#include <algorithm>
#include <cmath>

// Clamp value to [0, 255]
inline unsigned char clamp_byte(int value) {
    if (value < 0) return 0;
    if (value > 255) return 255;
    return (unsigned char)value;
}

// Max function to prevent division by zero
inline int max_one(int value) {
    return (value < 1) ? 1 : value;
}

/**
 * BLC/SLC Correction - EXACT formula from frmGenRGB.cs lines 326-417
 * Formula: corrected = (raw - BLC) × 255 ÷ MAX(1, SLC - BLC)
 */
void apply_blc_slc_correction(
    unsigned char* frame,
    int width,
    int height,
    const int* blc_r,
    const int* blc_g,
    const int* blc_b,
    const int* slc_r,
    const int* slc_g,
    const int* slc_b,
    int blc_offset,
    int slc_offset
) {
    const int total_pixels = width * height;
    
    // Process frame in BGR order (OpenCV format)
    for (int i = 0; i < total_pixels; i++) {
        int y = i / width;
        int x = i % width;
        int pixel_idx = i * 3;  // BGR format (3 channels)
        
        // Blue channel
        int valB = frame[pixel_idx];
        int blcB_offset = blc_b[i] + blc_offset;
        int slcB_offset = slc_b[i] + slc_offset;
        int corrB = valB - blcB_offset;
        corrB = (corrB * 255) / max_one(slcB_offset - blcB_offset);
        frame[pixel_idx] = clamp_byte(corrB);
        
        // Green channel
        int valG = frame[pixel_idx + 1];
        int blcG_offset = blc_g[i] + blc_offset;
        int slcG_offset = slc_g[i] + slc_offset;
        int corrG = valG - blcG_offset;
        corrG = (corrG * 255) / max_one(slcG_offset - blcG_offset);
        frame[pixel_idx + 1] = clamp_byte(corrG);
        
        // Red channel
        int valR = frame[pixel_idx + 2];
        int blcR_offset = blc_r[i] + blc_offset;
        int slcR_offset = slc_r[i] + slc_offset;
        int corrR = valR - blcR_offset;
        corrR = (corrR * 255) / max_one(slcR_offset - blcR_offset);
        frame[pixel_idx + 2] = clamp_byte(corrR);
    }
}

/**
 * GLC Correction - EXACT formula from frmGenRGB.cs lines 458-532
 * Applies grey level correction with split at mid=127
 */
void apply_glc_correction(
    unsigned char* channel,
    int total_pixels,
    const int* glc_map
) {
    const int maxv = 255;
    const int mid = maxv >> 1;      // 127
    const int midp = mid + 1;       // 128
    
    for (int i = 0; i < total_pixels; i++) {
        int iVal = channel[i];
        int g_raw = glc_map[i];
        
        // Clamp GLC value
        if (g_raw < 0) g_raw = 0;
        else if (g_raw > maxv) g_raw = maxv;
        
        if (g_raw != 0) {
            int c = iVal;
            
            if (g_raw < mid) {
                // Dark region - boost shadows
                int g = (g_raw < 1) ? 1 : g_raw;
                
                if (c > g) {
                    int denom = (maxv - g);
                    c = (denom > 0) 
                        ? mid + ((c - g) * midp) / denom
                        : mid;
                } else {
                    c = (c * mid) / g;
                }
            }
            else if (g_raw > mid) {
                // Bright region - compress highlights
                int g = (g_raw < 1) ? 1 : g_raw;
                
                if (c > g) {
                    int denom = (maxv - g);
                    c = (denom > 0)
                        ? mid + ((c - g) * mid) / denom
                        : maxv;
                } else {
                    c = (c * midp) / g;
                }
            }
            
            // Clamp result
            if (c < 0) c = 0;
            else if (c > maxv) c = maxv;
            
            iVal = c;
        }
        
        channel[i] = (unsigned char)iVal;
    }
}

/**
 * Dark GLC Correction - EXACT formula from frmGenRGB.cs lines 1226-1291
 * Enhances shadow details (0-128 range)
 */
void apply_dark_glc_correction(
    unsigned char* channel,
    int total_pixels,
    const int* dark_glc_map
) {
    const int maxv = 255;
    const int quarter = (maxv + 1) / 4;  // 64
    const int half = (maxv + 1) / 2;     // 128
    
    for (int i = 0; i < total_pixels; i++) {
        int c = channel[i];
        int a = c;  // Original value for blending
        int dg = dark_glc_map[i];
        
        if (dg != 0) {
            float glc_correction;
            
            if (dg < quarter) {
                // Very dark reference
                if ((c > dg) && (c < half)) {
                    c = quarter + (int)((float)(c - dg) / ((float)(half - dg) / (float)quarter));
                }
                else if (c < quarter) {
                    glc_correction = ((float)quarter / (float)dg);
                    c = (int)((float)c * glc_correction);
                }
            }
            else if ((dg > quarter) && (dg < half)) {
                // Moderately dark reference
                if (c > dg) {
                    glc_correction = ((float)quarter / (float)(half - dg));
                    c = quarter + (int)((float)(c - dg) * glc_correction);
                    c = (a + c) >> 1;  // Blend with original (average)
                } else {
                    c = (int)((float)c / ((float)dg / (float)quarter));
                    c = (a + c) >> 1;  // Blend with original
                }
            }
            
            // Clamp result
            if (c > maxv) c = maxv;
            if (c < 0) c = 0;
        }
        
        channel[i] = (unsigned char)c;
    }
}

/**
 * Main correction function - applies selected corrections in order
 * Order: BLC/SLC → GLC → Dark GLC
 */
void apply_corrections(
    unsigned char* frame,
    int width,
    int height,
    const int* blc_r,
    const int* blc_g,
    const int* blc_b,
    const int* slc_r,
    const int* slc_g,
    const int* slc_b,
    const int* glc_r,
    const int* glc_g,
    const int* glc_b,
    const int* dark_glc_r,
    const int* dark_glc_g,
    const int* dark_glc_b,
    bool enable_blc_slc,
    bool enable_glc,
    bool enable_dark_glc,
    int blc_offset,
    int slc_offset
) {
    const int total_pixels = width * height;
    
    // STEP 1: Apply BLC/SLC correction (if enabled)
    if (enable_blc_slc && blc_r != nullptr && slc_r != nullptr) {
        apply_blc_slc_correction(
            frame, width, height,
            blc_r, blc_g, blc_b,
            slc_r, slc_g, slc_b,
            blc_offset, slc_offset
        );
    }
    
    // STEP 2: Apply GLC correction (if enabled)
    if (enable_glc && glc_r != nullptr) {
        // Create separate channel buffers
        unsigned char* channel_b = new unsigned char[total_pixels];
        unsigned char* channel_g = new unsigned char[total_pixels];
        unsigned char* channel_r = new unsigned char[total_pixels];
        
        // Extract BGR channels
        for (int i = 0; i < total_pixels; i++) {
            channel_b[i] = frame[i * 3];
            channel_g[i] = frame[i * 3 + 1];
            channel_r[i] = frame[i * 3 + 2];
        }
        
        // Apply GLC to each channel
        apply_glc_correction(channel_b, total_pixels, glc_b);
        apply_glc_correction(channel_g, total_pixels, glc_g);
        apply_glc_correction(channel_r, total_pixels, glc_r);
        
        // Merge back to BGR frame
        for (int i = 0; i < total_pixels; i++) {
            frame[i * 3] = channel_b[i];
            frame[i * 3 + 1] = channel_g[i];
            frame[i * 3 + 2] = channel_r[i];
        }
        
        delete[] channel_b;
        delete[] channel_g;
        delete[] channel_r;
    }
    
    // STEP 3: Apply Dark GLC correction (if enabled)
    if (enable_dark_glc && dark_glc_r != nullptr) {
        // Create separate channel buffers
        unsigned char* channel_b = new unsigned char[total_pixels];
        unsigned char* channel_g = new unsigned char[total_pixels];
        unsigned char* channel_r = new unsigned char[total_pixels];
        
        // Extract BGR channels
        for (int i = 0; i < total_pixels; i++) {
            channel_b[i] = frame[i * 3];
            channel_g[i] = frame[i * 3 + 1];
            channel_r[i] = frame[i * 3 + 2];
        }
        
        // Apply Dark GLC to each channel
        apply_dark_glc_correction(channel_b, total_pixels, dark_glc_b);
        apply_dark_glc_correction(channel_g, total_pixels, dark_glc_g);
        apply_dark_glc_correction(channel_r, total_pixels, dark_glc_r);
        
        // Merge back to BGR frame
        for (int i = 0; i < total_pixels; i++) {
            frame[i * 3] = channel_b[i];
            frame[i * 3 + 1] = channel_g[i];
            frame[i * 3 + 2] = channel_r[i];
        }
        
        delete[] channel_b;
        delete[] channel_g;
        delete[] channel_r;
    }
}
