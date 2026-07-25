# Manyfold signer deployment

Heart uses one Manyfold signer per totem machine. The signer alone reads the
durable machine private key. Every Heart process generates an ephemeral key and
uses the protected local socket to obtain a short-lived process certificate.
Heart contains no signing implementation.

## Totem topology

Supervisor starts the processes in this order:

1. `heart-xvfb`
1. `heart-manyfold-signer`
1. `heart-app`
1. `heart-rp1-scanner`

The signer runs from the same locked Heart environment as the app but has a
separate lifecycle and restart policy. Its defaults are:

| Setting | Value |
| --- | --- |
| State directory | `/var/lib/heart/manyfold-signer` |
| Unix socket | `/run/heart-manyfold/signer.sock` |
| Socket mode | `0600` |
| Allowed uid | Signer service uid (`root` in the existing totem deployment) |
| Maximum concurrent clients | 16 |
| Maximum audit entries | 256 |
| Process credential lifetime | 300 seconds |

`bootstrap-supervisord.sh` runs idempotent Manyfold identity initialization
after `uv sync` and before Supervisor starts. On an empty state directory,
Manyfold creates a local authority and machine identity with strict
permissions. That is suitable for an isolated totem or the first trusted
authority. A member of an existing cluster must instead receive a state
directory produced by Manyfold's authenticated enrollment flow before this
bootstrap runs; the status check then reuses it without creating a second
authority. The initialization command's one-time enrollment token is discarded
without entering Heart logs.

For member enrollment, place the one-time token in a root-owned `0600` file and
make the authority signer's Unix socket available locally, for example through
an authenticated SSH Unix-socket forward. Set:

```text
HEART_MANYFOLD_ENROLLMENT_AUTHORITY_SOCKET=/run/heart-manyfold/authority.sock
HEART_MANYFOLD_ENROLLMENT_TOKEN_FILE=/run/heart-manyfold/enrollment.token
```

The bootstrap uses Manyfold's `--token-file` input, never places the bearer
token in argv or logs, and removes the one-time file only after enrollment
succeeds. Supplying only one of the two settings fails before initialization.

The shared `/etc/default/totem` file contains only the socket, cluster identity,
node identity, and lifecycle policy. It does not contain a key, certificate, or
process credential. The Heart client reads no signer state path.

The legacy systemd path uses `manyfold-signer.service`; `totem.service`
requires it, and Heart's startup credential gate verifies signer readiness.
Do not enable both the systemd and Supervisor signer units on one machine.
Install the legacy units with:

```sh
sudo install -m 0755 drivers/totem/heart-supervisor-signer.sh \
  /usr/local/bin/heart-supervisor-signer.sh
sudo install -m 0755 drivers/totem/heart-supervisor-common.sh \
  /usr/local/bin/heart-supervisor-common.sh
sudo install -m 0644 drivers/totem/manyfold-signer.service \
  /etc/systemd/system/manyfold-signer.service
sudo install -m 0644 drivers/totem/totem.service \
  /etc/systemd/system/totem.service
sudo systemctl daemon-reload
sudo systemctl enable --now manyfold-signer.service totem.service
```

## Heart client lifecycle

Set:

```text
HEART_MANYFOLD_SIGNER_ENABLED=1
HEART_MANYFOLD_SIGNER_SOCKET=/run/heart-manyfold/signer.sock
HEART_MANYFOLD_CLUSTER_ID=heart
HEART_MANYFOLD_NODE_ID=totem3
```

Optional bounded-policy variables are:

- `HEART_MANYFOLD_SIGNER_POLL_INTERVAL_SECONDS`
- `HEART_MANYFOLD_SIGNER_RETRY_MAX_ATTEMPTS`
- `HEART_MANYFOLD_SIGNER_RETRY_DELAY_SECONDS`

Manyfold constrains attempts to 1–5 and retry delay to 0–1 second. Heart
validates those bounds before starting.

When enabled, `totem run` requires an initial credential before the game loop
starts. A Heart-owned renewal thread advances Manyfold's
`empty`, `ready`, `renewal_due`, `renewal_failed`, `unavailable`, `expired`,
and `closed` states. A signer outage preserves a still-valid credential in
`renewal_failed` while bounded renewal continues. At certificate expiry,
transport credential access fails closed until renewal succeeds. Shutdown joins
renewal before discarding the process credential.

Logs contain state, generation, and expiry only. They do not render credential
objects, PEM data, or signer state paths.

## Qualification consumer gate

Install the candidate Manyfold wheel in Heart's environment, then run:

```sh
uv pip install --python .venv/bin/python \
  --force-reinstall --no-deps /path/to/manyfold_candidate.whl
.venv/bin/python scripts/qualify_manyfold_signer.py \
  --signer-executable .venv/bin/manyfold-machine-signer \
  --enrollment-executable .venv/bin/manyfold-enrollment \
  --output .artifacts/manyfold-signer-qualification.json
.venv/bin/pytest tests/runtime/test_manyfold_signer.py \
  tests/test_totem_manyfold_signer_deployment.py -q
```

The JSON artifact records the exact initialization and signer commands plus:

- observed `0700` signer state/socket-directory modes and `0600` socket mode;
- authority-socket member enrollment from a `0600` token file, followed by
  removal of that one-time file with no bearer token in recorded argv;
- two simultaneous spawned Heart client processes bootstrapping through one
  signer and receiving distinct certificate serials;
- rejection of a real local process whose uid is outside signer policy;
- bounded failure when no signer is available at bootstrap;
- a valid credential retained while the signer is down;
- a new credential generation after signer restart;
- fail-closed expiry while the signer remains unavailable;
- clean client closure;
- Python audit-hook evidence from each spawned Heart process that none of the
  exact durable CA or machine private-key paths were opened.

The signer process necessarily opens the durable keys. The qualification claim
is scoped to Heart client PIDs, and each result carries
`durable_private_key_opened=false`. The artifact contains paths, state names,
serial numbers, and timestamps only; it contains no PEM or private-key bytes.
The outage row also records `is_usable=true`; the expiry row must record
`is_usable=false`, and rejected clients retain the explicit `unavailable`
credential lifecycle state.

For an installed candidate wheel, the focused multiprocess command is:

```sh
.venv/bin/pytest \
  tests/runtime/test_manyfold_signer.py::test_real_multiprocess_signer_qualification \
  -q
```

Use the environment executables directly after installing the wheel. Running
`uv run` may synchronize the lockfile version over the candidate before the
gate executes.
