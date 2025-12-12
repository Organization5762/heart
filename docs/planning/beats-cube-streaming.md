# Refactor plan: render streamed images on a cube in the Beats Electron renderer

## Problem Statement

The Beats Electron renderer currently draws streamed PNG frames directly into an `<img>` tag via `src/components/stream.tsx`, so there is no ability to map the texture onto 3D geometry. We need a plan to refactor the renderer so the streamed image is applied to a WebGL cube while preserving the existing websocket-driven frame pipeline and status overlays.

## Materials

- Node.js and npm as defined in `experimental/beats/package.json` (Electron 39, Vite 7, React 19, TypeScript 5.9).
- Existing websocket frame source provided by `src/actions/ws/providers/ImageProvider.tsx` and `frameStream`.
- Rendering components under `experimental/beats/src`, especially `components/stream.tsx` and layout wrappers that host the viewer area.
- Three.js (or a lightweight alternative such as `@react-three/fiber` and `three`) for WebGL rendering on the renderer side.
- Access to the Electron renderer build (Vite) to validate GPU context creation and hot reload behaviour.
- Design assets (placeholder checkerboard texture) for bootstrapping when no stream frames are available.

## Opening Abstract

This refactor introduces a WebGL-backed rendering path for streamed camera frames. Instead of piping the base64 frame data straight into an `<img>` element, the frames will be decoded into textures and applied to a cube mesh within a dedicated canvas component. The refactor keeps websocket connectivity, FPS smoothing, and status indicators intact while isolating the WebGL lifecycle in a single React component. By hard-coding the mesh to a cube, we simplify MVP scope and leave hooks for future shape selection.

## Success Criteria

| Behaviour | Validation signal | Owner |
| --- | --- | --- |
| Streamed frames appear on all six faces of a cube rendered in the viewer area | Visual confirmation in the renderer window with real or mocked frames | Renderer developer |
| FPS display and websocket status remain accurate | `fps` value from `useStreamedImage()` matches incoming frame cadence; status badge still toggles | Frontend engineer |
| Rendering path handles stream interruptions gracefully | When `imgURL` is null, the cube uses a fallback texture and avoids crashes | Renderer developer |
| Cube rendering does not regress existing layout | Surrounding UI (footer, separators) retains sizing and alignment in `stream.tsx` | UI maintainer |

## Task Breakdown Checklists

### Discovery

- [ ] Audit `src/components/stream.tsx` and identify the container element where the canvas can replace the `<img>` tag.
- [ ] Verify how `ImageProvider` cleans up object URLs to ensure texture disposal will not leak GPU memory.
- [ ] Confirm Vite/Electron build supports WebGL context creation and whether `three` is already a dependency.
- [ ] Map keyboard/mouse interaction requirements (e.g., auto-rotation only) to avoid over-scoping controls.

### Implementation

- [ ] Add rendering dependencies (`three` and optionally `@react-three/fiber`) to `experimental/beats/package.json` if absent.
- [ ] Create `src/components/stream-cube.tsx` that owns a `<canvas>` and renders a cube textured with the latest frame.
- [ ] Convert `imgURL` blob URLs into `THREE.Texture` objects, disposing previous textures when frames update.
- [ ] Drive cube rotation with a requestAnimationFrame loop to keep motion even when frames are static.
- [ ] Replace `<StreamedImage>` usage in `stream.tsx` with the cube component while keeping footer/status elements unchanged.
- [ ] Provide a fallback texture (checkerboard or solid colour) when `imgURL` is null to avoid flashing blank faces.
- [ ] Wire cleanup to dispose of renderer, scene, and textures when the component unmounts or when websocket disconnects.

### Validation

- [ ] Use a mock frame generator to send static and rapidly changing frames, verifying texture updates across all cube faces.
- [ ] Check that FPS readouts match expected frame counts during test streams.
- [ ] Resize the window to confirm the cube resizes correctly within the existing flex layout.
- [ ] Run `npm run lint` and `npm run test` (or `make test` at repo root) to ensure no regressions elsewhere.

## Narrative Walkthrough

The current stream viewer is a thin wrapper that decodes base64 PNG strings into blob URLs and feeds them into an `<img>` tag. The refactor replaces this passive image element with a small WebGL scene. A new `StreamCube` component will mount a `<canvas>` inside the existing viewer region and initialise a Three.js scene containing a single cube mesh. On every incoming frame, the component converts the blob URL provided by `useStreamedImage()` into a texture, applies it to a `THREE.MeshStandardMaterial`, and swaps it onto the cube. As frames arrive, previous textures are disposed to keep GPU memory bounded. The cube will rotate slowly along two axes via a requestAnimationFrame loop so the mapped image is visible from multiple angles without user input.

`stream.tsx` keeps its layout responsibilities: it reserves vertical space for the viewer, renders the cube canvas in place of the `<StreamedImage>` wrapper, and retains the separator and footer. The websocket address display and `StreamStatus` indicator continue to consume `useWS()` and `useStreamedImage()` outputs, so no backend contract changes are required. To make error handling predictable, the cube uses a fallback texture whenever `imgURL` is `null`; this keeps the GPU pipeline stable during stream outages while allowing the status badge to show inactivity.

Lifecycle management is critical because Electron windows may be opened and closed repeatedly during development. The plan emphasises disposing of render targets, textures, and event listeners when the cube component unmounts. Because `ImageProvider` already revokes object URLs, the cube only needs to release Three.js resources it owns. The rendering loop should pause when the component is not visible or when the websocket disconnects to conserve CPU/GPU cycles.

## Visual Reference

```mermaid
graph TD
  A[frameStream payload (base64 PNG)] --> B[ImageProvider converts to blob URL]
  B --> C[StreamCube loads URL into THREE.Texture]
  C --> D[Cube mesh with 6 material slots]
  D --> E[Rotating render loop on <canvas>]
  E --> F[Stream footer (FPS, status, URL)]
```

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Early warning |
| --- | --- | --- | --- | --- |
| GPU resource leaks from repeated texture creation | Medium | High | Dispose textures on each frame update; reuse materials; profile with Chrome DevTools | Renderer memory grows over time or GPU crashes |
| WebGL context fails in some environments | Low | Medium | Detect context creation failure and fall back to existing `<img>` path | Console errors about context loss |
| Frame-rate drops due to render loop overhead | Medium | Medium | Cap rotation update rate and throttle texture uploads to frame arrivals | FPS readout diverges from expected input |
| Layout regressions in stream view | Low | Medium | Keep container sizing identical and test responsive breakpoints | Misaligned footer or overflow clipping |

### Mitigation Checklist

- [ ] Add a guard that falls back to `<img>` rendering when `THREE.WebGLRenderer` cannot initialise.
- [ ] Instrument texture creation/disposal with debug logs during development builds.
- [ ] Profile render loop and texture upload timings using Chromium performance tools in Electron.
- [ ] Keep viewer container styles unchanged to minimize CSS churn.

## Outcome Snapshot

After the refactor, the Beats Electron renderer will show the streamed feed wrapped around a rotating cube inside the existing viewer panel. Status badges still indicate websocket health and FPS, and the viewer remains responsive to window resizes. The rendering code is isolated in `StreamCube`, making it easy to swap in different shapes later or extend the material pipeline without disturbing websocket or layout logic.
