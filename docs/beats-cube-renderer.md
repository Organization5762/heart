# Beats cube renderer integration

## Overview

The Beats Electron renderer now draws streamed PNG frames onto a rotating WebGL cube instead of an `<img>` element. The cube is implemented in `experimental/beats/src/components/stream-cube.tsx` and consumes frame updates from `ImageProvider` via the existing `useStreamedImage()` hook. The previous image-based path remains available as a fallback when WebGL cannot initialise.

## Key behaviours

- The cube uses a Three.js `WebGLRenderer` with a `BoxGeometry` and six `MeshStandardMaterial` instances so incoming textures wrap every face.
- When `imgURL` is `null`, the renderer shows a generated checkerboard texture to keep the GPU pipeline stable during stream gaps.
- Failed WebGL context creation triggers a transparent fallback to the legacy `<img>` rendering path in `experimental/beats/src/components/stream.tsx`.
- The render loop animates the cube on both the X and Y axes and resizes in response to a `ResizeObserver` attached to the container element.
- Texture lifecycles are managed by disposing previous maps on update and tearing down the renderer, materials, and fallback texture on unmount.

## Touchpoints

- Rendering: `experimental/beats/src/components/stream-cube.tsx`
- Stream view composition and fallback handling: `experimental/beats/src/components/stream.tsx`
- Frame source: `experimental/beats/src/actions/ws/providers/ImageProvider.tsx`
