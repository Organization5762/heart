---
name: tetris-vnc
description: Bring up the Heart Tetris TigerVNC display on a Raspberry Pi, configure it to autostart at boot, and open the VNC screen from the local Mac. Use when working on or debugging the Tetris display on totem3.local or another Heart Pi without X11 forwarding.
---

# Tetris VNC

Use TigerVNC instead of X11 forwarding for the Heart Tetris renderer on a Pi.

Default target:

- Host: `totem3.local`
- SSH user: `michael`
- Service: `totem.service`
- VNC display: `:1`
- VNC port: `5901`
- VNC geometry: `2304x576`
- Pi repo path: `/home/michael/Desktop/heart`

## Pi setup

From the Pi checkout, run:

```bash
scripts/setup_tetris_vnc_autostart.sh --repo /home/michael/Desktop/heart
```

This installs TigerVNC if needed and configures the system `totem.service` as the default owner of both the VNC screen and the Tetris process. It writes:

- `/etc/systemd/system/totem.service`
- `/etc/default/totem`
- `/usr/local/bin/setup-tetris-vnc.sh`, which starts TigerVNC on display `:1`
- `/usr/local/bin/start-heart.sh`, which runs `uv run totem run --configuration tetris --no-add-low-power-mode`

It also removes the older per-user `heart-tetris.service` and `heart-tetris-vnc.service` if they exist, enables `totem.service`, and starts it immediately. Use `--no-start` when you only want to install and enable the service.

## Local open

From the local checkout, run:

```bash
scripts/open_tetris_vnc_viewer.sh --host totem3.local --start-remote
```

This restarts the remote services over SSH, then opens TigerVNC Viewer locally. If the viewer is not at the default macOS path, pass:

```bash
scripts/open_tetris_vnc_viewer.sh --viewer "/path/to/TigerVNC Viewer" --host totem3.local
```

## Debugging

Check remote services:

```bash
ssh michael@totem3.local 'sudo systemctl status totem.service'
```

Restart remote services:

```bash
ssh michael@totem3.local 'sudo systemctl restart totem.service'
```

Check VNC socket:

```bash
ssh michael@totem3.local 'ss -ltnp | grep :5901 || true'
```
