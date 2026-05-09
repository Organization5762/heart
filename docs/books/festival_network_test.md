# Festival Network Test

## Goal

Validate that the Raspberry Pi can run without venue Wi-Fi or internet while still serving the
Beats web UI, accepting WebSocket connections, and allowing SSH from a laptop.

Expected festival addresses:

- Pi hotspot SSID: `MyTotem`
- Pi hotspot IP: `192.168.4.1`
- Beats web UI: `http://totem/phone`
- Beats web UI fallback: `http://192.168.4.1/phone`
- Beats WebSocket: `ws://192.168.4.1:8765`
- SSH: `ssh -i keys/rpi_common_ed25519 <pi-user>@192.168.4.1`

## Preflight Before Leaving Home

Run the reusable network setup while the Pi still has internet access:

```bash
cd ~/heart
sudo env \
  HOTSPOT_PASSWORD='REPLACE_WITH_HOTSPOT_PASSWORD' \
  scripts/setup_pi_network.sh \
    --app-dir "$PWD" \
    --app-user "$USER" \
    --wifi-file scripts/pi_network_profiles.local.tsv
```

See [Raspberry Pi network setup](./pi_network_setup.md) for the reusable installer and Wi-Fi profile
file format.

Make sure SSH is enabled on the Pi:

```bash
sudo systemctl enable --now ssh
```

Make sure the laptop key is installed for the `pi` user. From the laptop, while the Pi is reachable
on home Wi-Fi:

```bash
chmod 600 keys/rpi_common_ed25519
ssh-copy-id -i keys/rpi_common_ed25519.pub pi@totem.local
ssh -i keys/rpi_common_ed25519 pi@totem.local 'hostname'
```

Make sure Python dependencies and Beats `node_modules` are installed before the offline test:

```bash
cd ~/heart
uv run totem run --configuration lib_2024 --with-beats-web
```

Stop it after the web UI starts. The systemd service installed by `setup_pi_network.sh` uses
`--no-install-beats-deps` so it does not try to download packages when offline.

## Pi-Side Diagnostic

With the runtime running, open a second SSH session or local terminal on the Pi:

```bash
cd ~/heart
scripts/check_festival_network.sh
```

The script should report:

- `ssh`, `NetworkManager`, `nginx`, and `heart-beats-web` active.
- `192.168.4.1` assigned to an interface.
- TCP listener on public port `80`.
- TCP listener on local Beats web port `5173`.
- TCP listeners on `0.0.0.0:8765` or `192.168.4.1:8765`.
- Local HTTP check passes for `http://192.168.4.1/phone`.

## Laptop and Phone Test

1. Disconnect the laptop from home Wi-Fi.
2. Connect the laptop to the Pi hotspot SSID.
3. Verify SSH:
   ```bash
   ssh -i keys/rpi_common_ed25519 <pi-user>@192.168.4.1 'hostname && ip -brief addr'
   ```
4. Open the web UI from the laptop:
   ```text
   http://totem/phone
   ```
5. Connect the phone to the same hotspot.
6. Open the web UI from the phone:
   ```text
   http://totem/phone
   ```
7. Confirm the UI shows a live WebSocket connection and that phone controls affect the running
   totem.

It is normal for phones to show a "No Internet" warning on this Wi-Fi network. Keep the phone on the
network anyway.

## Pass Criteria

The setup is festival-ready when all of these work with home Wi-Fi unavailable:

- Laptop can SSH to `<pi-user>@192.168.4.1`.
- Phone can load `http://totem/phone`.
- Browser WebSocket connects to `ws://192.168.4.1:8765`.
- UI controls change the live Pi runtime.
- Rebooting the Pi brings the hotspot and SSH back without manual home-network access.

## If It Fails

- Website does not load: check that nginx is listening on `0.0.0.0:80` and that the local Beats web
  server is listening on `127.0.0.1:5173`.
- `totem` does not resolve: check `/etc/NetworkManager/dnsmasq-shared.d/totem.conf` and reconnect
  the hotspot profile.
- WebSocket does not connect: check that the runtime is listening on `0.0.0.0:8765`.
- SSH times out: check `systemctl status ssh`, confirm the laptop is connected to the Pi hotspot,
  and verify the Pi owns `192.168.4.1`.
- Phone disconnects from hotspot: disable mobile data assist / auto-join alternatives for the test,
  or mark the Pi network as one to stay connected to despite no internet.
