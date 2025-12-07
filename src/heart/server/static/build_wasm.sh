#!/bin/bash
# Build WASM decoder using Emscripten

set -e

echo "Building WASM JPEG decoder..."

# Check if emscripten is installed
if ! command -v emcc &> /dev/null; then
    echo "Error: Emscripten not found. Install from: https://emscripten.org/docs/getting_started/downloads.html"
    exit 1
fi

# Download stb_image.h if not present
if [ ! -f "stb_image.h" ]; then
    echo "Downloading stb_image.h..."
    curl -O https://raw.githubusercontent.com/nothings/stb/master/stb_image.h
fi

# Compile to WASM
emcc decoder.c \
    -o decoder.js \
    -s WASM=1 \
    -s EXPORTED_FUNCTIONS='["_init_decoder","_decode_jpeg","_get_jpeg_buffer","_cleanup_decoder"]' \
    -s EXPORTED_RUNTIME_METHODS='["cwrap","ccall","HEAPU8"]' \
    -s ALLOW_MEMORY_GROWTH=1 \
    -s MODULARIZE=1 \
    -s EXPORT_NAME='createDecoderModule' \
    -s INITIAL_MEMORY=16777216 \
    -O3 \
    --no-entry

echo "Build complete! Generated decoder.js and decoder.wasm"
echo ""
echo "To use in production, run this script on a machine with Emscripten installed."
echo "For now, using JavaScript fallback in index.html"


