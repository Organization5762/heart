# Heart

Visual display project for LED screens.

## Development

**Installation**

`make dev_install` or `make pi_install`

**Formatting**

`make format` should install and run the correct formatting and linting tools

**Testing Locally**

The command: `totem run --configuration full_screen_test` should display a scene locally. If you see a scene, then the setup is correct.

**Supported Platforms**

- MacOSX for local development
- An appropriately setup Raspberry Pi 4 for portable use

## WebSocket Streaming

Stream the LED display to a web browser for remote viewing with full interactive controls. **Much faster than X11 forwarding!**

**Quick Start:**

1. Install dependencies: `pip install -e .`
2. Run with virtual display: 
   ```bash
   HEART_USE_LOCAL_SCREEN=1 DISPLAY=:99 xvfb-run -a -s "-screen 0 1280x720x24" totem run --configuration lib_2025
   ```
3. Open browser: `http://<raspberry-pi-ip>:8000`

**Features:**
- ✨ Real-time 60fps video streaming with WASM-accelerated JPEG decoding
- 🎮 Full bidirectional controls (keyboard, mouse, scroll wheel)
- 📊 Live FPS and latency metrics
- 🔄 Auto-reconnect on disconnect
- 📱 Works on desktop, tablet, and mobile

**How it works:**
- Pygame renders to virtual display (Xvfb) on the Pi
- Frames are captured, JPEG-compressed in background thread, and streamed via WebSocket
- Browser input events (clicks, keys, scrolling) are sent back to Pi and injected into pygame
- Feels like a native remote desktop for your pygame app!

**To disable:** Pass `enable_streaming=False` to GameLoop constructor.

## Drivers setup

### ANT

For ant you will need to run drivers/ant_dongle/setup.sh on the raspberry pi. Then unplug and replug the dongle
