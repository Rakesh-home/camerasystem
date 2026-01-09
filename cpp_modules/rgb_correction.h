#ifndef RGB_CORRECTION_H
#define RGB_CORRECTION_H

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT
#endif

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Apply RGB corrections to a BGR frame (OpenCV format)
 * 
 * @param frame         BGR frame data (continuous buffer)
 * @param width         Frame width
 * @param height        Frame height
 * @param blc_r         Black Level Correction - Red channel [height * width]
 * @param blc_g         Black Level Correction - Green channel
 * @param blc_b         Black Level Correction - Blue channel
 * @param slc_r         Saturation Level Correction - Red channel
 * @param slc_g         Saturation Level Correction - Green channel
 * @param slc_b         Saturation Level Correction - Blue channel
 * @param glc_r         Grey Level Correction - Red channel (can be NULL)
 * @param glc_g         Grey Level Correction - Green channel
 * @param glc_b         Grey Level Correction - Blue channel
 * @param dark_glc_r    Dark GLC - Red channel (can be NULL)
 * @param dark_glc_g    Dark GLC - Green channel
 * @param dark_glc_b    Dark GLC - Blue channel
 * @param enable_blc_slc Enable BLC/SLC correction
 * @param enable_glc     Enable GLC correction
 * @param enable_dark_glc Enable Dark GLC correction
 * @param blc_offset    BLC offset (default 0)
 * @param slc_offset    SLC offset (default 0)
 */
DLL_EXPORT void apply_corrections(
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
);

#ifdef __cplusplus
}
#endif

#endif // RGB_CORRECTION_H
