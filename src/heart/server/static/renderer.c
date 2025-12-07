/**
 * WebGL Renderer for Heart Display
 * Handles JPEG decoding and GPU-accelerated rendering entirely in C
 */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <GLES2/gl2.h>
#include <emscripten/html5.h>

#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_JPEG
#define STBI_NO_STDIO
#include "stb_image.h"

// Canvas and buffers
static int canvas_width = 0;
static int canvas_height = 0;
static uint8_t* jpeg_buffer = NULL;
static int jpeg_buffer_size = 65536;

// WebGL resources
static GLuint texture = 0;
static GLuint program = 0;
static GLuint vbo = 0;

// Vertex shader (textured quad)
static const char* vertex_shader_src = 
    "attribute vec2 pos;\n"
    "attribute vec2 uv;\n"
    "varying vec2 vUV;\n"
    "void main() {\n"
    "    vUV = uv;\n"
    "    gl_Position = vec4(pos, 0.0, 1.0);\n"
    "}\n";

// Fragment shader (texture sampling)
static const char* fragment_shader_src =
    "precision mediump float;\n"
    "varying vec2 vUV;\n"
    "uniform sampler2D tex;\n"
    "void main() {\n"
    "    gl_FragColor = texture2D(tex, vUV);\n"
    "}\n";

/**
 * Compile shader
 */
static GLuint compile_shader(GLenum type, const char* source) {
    GLuint shader = glCreateShader(type);
    glShaderSource(shader, 1, &source, NULL);
    glCompileShader(shader);
    
    GLint success;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &success);
    if (!success) {
        char log[512];
        glGetShaderInfoLog(shader, 512, NULL, log);
        emscripten_log(EM_LOG_ERROR, "Shader compilation failed: %s", log);
        return 0;
    }
    
    return shader;
}

/**
 * Initialize WebGL renderer
 */
int init_renderer(const char* canvas_id, int width, int height) {
    canvas_width = width;
    canvas_height = height;
    
    // Allocate JPEG input buffer
    jpeg_buffer = (uint8_t*)malloc(jpeg_buffer_size);
    if (!jpeg_buffer) return 0;
    
    // Create WebGL2 context
    EmscriptenWebGLContextAttributes attrs;
    emscripten_webgl_init_context_attributes(&attrs);
    attrs.alpha = 0;
    attrs.depth = 0;
    attrs.stencil = 0;
    attrs.antialias = 0;
    attrs.majorVersion = 2;
    attrs.minorVersion = 0;
    attrs.enableExtensionsByDefault = 1;
    
    EMSCRIPTEN_WEBGL_CONTEXT_HANDLE ctx = emscripten_webgl_create_context(canvas_id, &attrs);
    if (ctx <= 0) {
        // Try WebGL 1 as fallback
        attrs.majorVersion = 1;
        ctx = emscripten_webgl_create_context(canvas_id, &attrs);
        if (ctx <= 0) {
            emscripten_log(EM_LOG_ERROR, "Failed to create WebGL context (tried v2 and v1)");
            return 0;
        }
    }
    emscripten_webgl_make_context_current(ctx);
    
    // Compile shaders
    GLuint vs = compile_shader(GL_VERTEX_SHADER, vertex_shader_src);
    GLuint fs = compile_shader(GL_FRAGMENT_SHADER, fragment_shader_src);
    if (!vs || !fs) return 0;
    
    // Link program
    program = glCreateProgram();
    glAttachShader(program, vs);
    glAttachShader(program, fs);
    glLinkProgram(program);
    
    GLint success;
    glGetProgramiv(program, GL_LINK_STATUS, &success);
    if (!success) {
        emscripten_log(EM_LOG_ERROR, "Program linking failed");
        return 0;
    }
    
    glDeleteShader(vs);
    glDeleteShader(fs);
    glUseProgram(program);
    
    // Create texture
    glGenTextures(1, &texture);
    glBindTexture(GL_TEXTURE_2D, texture);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    
    // Allocate texture on GPU
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
    
    // Create fullscreen quad
    float vertices[] = {
        // pos (x,y)    uv (s,t)
        -1.0f, -1.0f,   0.0f, 1.0f,  // Bottom-left
         1.0f, -1.0f,   1.0f, 1.0f,  // Bottom-right
        -1.0f,  1.0f,   0.0f, 0.0f,  // Top-left
         1.0f,  1.0f,   1.0f, 0.0f,  // Top-right
    };
    
    glGenBuffers(1, &vbo);
    glBindBuffer(GL_ARRAY_BUFFER, vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(vertices), vertices, GL_STATIC_DRAW);
    
    // Setup vertex attributes
    GLint posLoc = glGetAttribLocation(program, "pos");
    GLint uvLoc = glGetAttribLocation(program, "uv");
    
    glEnableVertexAttribArray(posLoc);
    glVertexAttribPointer(posLoc, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)0);
    
    glEnableVertexAttribArray(uvLoc);
    glVertexAttribPointer(uvLoc, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)(2 * sizeof(float)));
    
    emscripten_log(EM_LOG_CONSOLE, "WebGL renderer initialized");
    return 1;
}

/**
 * Get pointer to JPEG input buffer
 */
uint8_t* get_jpeg_buffer() {
    return jpeg_buffer;
}

/**
 * Decode JPEG and render to canvas via WebGL
 * All in C - no JavaScript!
 */
int decode_and_render(int jpeg_size) {
    int width, height, channels;
    
    // Decode JPEG
    uint8_t* rgba = stbi_load_from_memory(
        jpeg_buffer,
        jpeg_size,
        &width,
        &height,
        &channels,
        4  // Force RGBA
    );
    
    if (!rgba) return 0;
    
    // Upload to GPU texture
    glBindTexture(GL_TEXTURE_2D, texture);
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, rgba);
    
    // Free decoded image
    stbi_image_free(rgba);
    
    // Clear and render
    glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    
    glUseProgram(program);
    glBindTexture(GL_TEXTURE_2D, texture);
    glBindBuffer(GL_ARRAY_BUFFER, vbo);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    
    return 1;
}

/**
 * Cleanup
 */
void cleanup_renderer() {
    if (jpeg_buffer) {
        free(jpeg_buffer);
        jpeg_buffer = NULL;
    }
    if (texture) {
        glDeleteTextures(1, &texture);
        texture = 0;
    }
    if (program) {
        glDeleteProgram(program);
        program = 0;
    }
    if (vbo) {
        glDeleteBuffers(1, &vbo);
        vbo = 0;
    }
}

