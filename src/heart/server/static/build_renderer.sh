#!/bin/bash
# Build WebGL renderer using Emscripten

set -e

echo "Building WebGL WASM renderer..."

# Download stb_image.h if not present
if [ ! -f "stb_image.h" ]; then
    echo "Downloading stb_image.h..."
    curl -O https://raw.githubusercontent.com/nothings/stb/master/stb_image.h
fi

# Compile to WASM with WebGL support
emcc renderer.c \
    -o renderer.js \
    -s WASM=1 \
    -s USE_WEBGL2=1 \
    -s FULL_ES2=1 \
    -s EXPORTED_FUNCTIONS='["_init_renderer","_get_jpeg_buffer","_decode_and_render","_cleanup_renderer"]' \
    -s EXPORTED_RUNTIME_METHODS='["cwrap","ccall","HEAPU8"]' \
    -s ALLOW_MEMORY_GROWTH=1 \
    -s MODULARIZE=1 \
    -s EXPORT_NAME='createRendererModule' \
    -s INITIAL_MEMORY=16777216 \
    -O3 \
    --no-entry

echo "Build complete! Generated renderer.js and renderer.wasm"
echo ""
echo "WebGL rendering pipeline is now 100% C/WASM!"

