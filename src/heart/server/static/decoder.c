/**
 * WASM JPEG Decoder and Canvas Renderer
 * Compiles to WebAssembly for fast image decoding
 */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_JPEG
#define STBI_NO_STDIO
#include "stb_image.h"

// Frame buffer for decoded image (RGBA output)
static uint8_t* frame_buffer = NULL;
static int frame_width = 0;
static int frame_height = 0;

// Input buffer for JPEG data (reused every frame)
static uint8_t* jpeg_buffer = NULL;
static int jpeg_buffer_size = 0;

/**
 * Initialize the decoder with canvas dimensions
 */
void init_decoder(int width, int height) {
    frame_width = width;
    frame_height = height;
    
    // Allocate frame buffer (RGBA output)
    if (frame_buffer != NULL) {
        free(frame_buffer);
    }
    frame_buffer = (uint8_t*)malloc(width * height * 4);
    
    // Allocate input buffer for JPEG (max size ~64KB for safety)
    jpeg_buffer_size = 65536;
    if (jpeg_buffer != NULL) {
        free(jpeg_buffer);
    }
    jpeg_buffer = (uint8_t*)malloc(jpeg_buffer_size);
}

/**
 * Decode JPEG from size
 * JavaScript should copy JPEG bytes to jpeg_buffer first
 * Returns pointer to RGBA buffer on success, NULL on failure
 */
uint8_t* decode_jpeg(int jpeg_size) {
    int width, height, channels;
    
    // Decode JPEG directly into frame_buffer (zero-copy!)
    uint8_t* img = stbi_load_from_memory(
        jpeg_buffer, 
        jpeg_size, 
        &width, 
        &height, 
        &channels, 
        4  // Force RGBA
    );
    
    if (img == NULL) {
        return NULL;
    }
    
    // stb_image allocated a new buffer, but we want to use our static one
    // Copy is still needed (stb_image doesn't support custom allocators easily)
    // But we could eliminate this by using a custom JPEG decoder
    if (width == frame_width && height == frame_height) {
        memcpy(frame_buffer, img, width * height * 4);
    }
    
    stbi_image_free(img);
    return frame_buffer;
}

/**
 * Get pointer to JPEG input buffer
 */
uint8_t* get_jpeg_buffer() {
    return jpeg_buffer;
}

/**
 * Get max size of JPEG buffer
 */
int get_jpeg_buffer_size() {
    return jpeg_buffer_size;
}

/**
 * Get pointer to frame buffer (for JavaScript to read)
 */
uint8_t* get_frame_buffer() {
    return frame_buffer;
}

/**
 * Get frame buffer size in bytes
 */
int get_buffer_size() {
    return frame_width * frame_height * 4;
}

/**
 * Cleanup
 */
void cleanup_decoder() {
    if (frame_buffer != NULL) {
        free(frame_buffer);
        frame_buffer = NULL;
    }
    if (jpeg_buffer != NULL) {
        free(jpeg_buffer);
        jpeg_buffer = NULL;
    }
}


