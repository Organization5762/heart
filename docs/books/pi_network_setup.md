# Raspberry Pi Network Setup

## Goal

Configure a Raspberry Pi so it can run the Beats web controller in both normal development and
offline festival settings:

- Join trusted Wi-Fi networks when they are available.
- Fall back to a Pi-hosted hotspot when trusted Wi-Fi is unavailable.
- Serve the phone UI at `http://totem/phone` on the hotspot.
- Keep SSH reachable on the hotspot at `192.168.4.1`.
- Start the web controller automatically after reboot.

The reusable installer is `scripts/setup_pi_network.sh`.

## Network Model

The Pi uses NetworkManager profiles with explicit priorities:

- Higher priority trusted Wi-Fi wins when available.
- The hotspot has a lower priority and is the fallback.
- The hotspot uses NetworkManager `ipv4.method shared`, which provides DHCP and DNS for clients.
- nginx owns port `80` and proxies to the local Beats web server on `127.0.0.1:5173`.
- The totem runtime websocket listens on `0.0.0.0:8765`.

Festival clients connect to the hotspot and use:

```text
http://totem/phone
```

Fallback URLs:

```text
http://192.168.4.1/phone
ssh <pi-user>@192.168.4.1
```

## Prepare Wi-Fi Profiles

Do not commit real Wi-Fi passwords. Copy the example file and fill in local credentials:

```bash
cp scripts/pi_network_profiles.example.tsv scripts/pi_network_profiles.local.tsv
```

Example:

```text
San Frantoria	90	wpa-psk	REPLACE_WITH_PASSWORD
The Commons WiFi by Meter	80	open
```

Priority convention:

- `100`: primary home/dev Wi-Fi, usually the existing `preconfigured` profile.
- `90`: secondary trusted Wi-Fi.
- `80`: trusted open venue Wi-Fi.
- `10`: fallback hotspot, configured by the installer.

## Install On A Pi

Run this from the Pi checkout after dependencies have already been installed:

```bash
cd ~/heart
sudo env \
  HOTSPOT_PASSWORD='REPLACE_WITH_HOTSPOT_PASSWORD' \
  scripts/setup_pi_network.sh \
    --app-dir "$PWD" \
    --app-user "$USER" \
    --wifi-file scripts/pi_network_profiles.local.tsv
```

The hotspot password must be at least 8 characters.

The installer configures:

- NetworkManager trusted Wi-Fi profiles.
- NetworkManager hotspot profile `MyTotem`.
- DNS aliases `totem` and `totem.local` for hotspot clients.
- nginx reverse proxy on port `80`.
- systemd service `heart-beats-web.service`, running `lib_2024` by default.

Use `--configuration <name>` if a Pi should boot into a different playlist.

## Verify

At home, reboot the Pi and confirm it returns on trusted Wi-Fi:

```bash
ssh <pi-user>@<home-wifi-ip> 'systemctl is-active nginx heart-beats-web.service'
curl -I http://<home-wifi-ip>/phone
```

In hotspot mode, connect a laptop or phone to `MyTotem` and test:

```bash
curl -I http://192.168.4.1/phone
ssh <pi-user>@192.168.4.1 'scripts/check_festival_network.sh'
```

From a phone, open:

```text
http://totem/phone
```

## Manual Network Switching

Switch to hotspot mode from home Wi-Fi:

```bash
ssh <pi-user>@<home-wifi-ip> 'sudo nmcli connection up MyTotem'
```

That SSH session will drop when the Pi leaves home Wi-Fi. Connect the laptop to `MyTotem`, then SSH
through the hotspot:

```bash
ssh <pi-user>@192.168.4.1
```

Switch back to the home Wi-Fi profile without rebooting:

```bash
ssh <pi-user>@192.168.4.1 'sudo nmcli connection up preconfigured'
```

At home, a reboot should also return to the highest-priority trusted Wi-Fi profile.
