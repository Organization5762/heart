# World coordination

Heart uses ManyFold's next coordinator contracts for a deliberately small
control plane. Raft stores only durable, low-rate facts that must survive a
device or leader restart:

- device identity, physical position, dimensions, and capabilities;
- the selected active mode, immutable configuration ID, and owning device.

World reads use `RpcEndpoint` directly through the typed `WorldRpcClient` and
`WorldRpcServer` domain codecs. Mode activation uses `DurableDelivery` after
the corresponding Raft command commits. These transports use separate
`TcpTransport` links because each ManyFold endpoint owns its receive stream.

## Data boundary

| Data | Path | Durable / Raft |
| --- | --- | --- |
| Device identity, position, dimensions, capabilities | Raft command and world RPC read | Yes |
| Active mode, configuration ID, owner | Raft command; durable delivery to the owner | Yes |
| Navigation events | Existing data plane | No |
| Sensor and microphone samples | Existing data plane | No |
| Frame ticks and rendered frames | Existing data plane | No |
| Debug and tracing data | Existing observability paths | No |

The code enforces this boundary with exactly two accepted command kinds:
`heart.world.device.put` and `heart.world.mode.select`. The delivery consumer
accepts only committed mode commands on `heart.world.mode.command`. It rejects
other channels and command kinds without ACKing them.

## Failure semantics

- **Idempotency:** the caller supplies a stable Raft `command_id`. ManyFold
  returns the original committed sequence for an identical retry and rejects
  conflicting content. The same ID becomes the durable delivery `message_id`
  and RPC correlation ID for the mode command.
- **Exactly-once application:** `WorldState` records applied command IDs and
  treats the state changes as idempotent assignments. A delivery is ACKed only
  after projection. After restart, rebuild `WorldState` from the local Raft log
  before resuming the durable inbox; a redelivery then produces no second
  command transition and is ACKed.
- **Deadlines:** every Heart RPC read requires an explicit positive deadline.
  The ManyFold endpoint propagates the remaining deadline to the handler and
  raises `RpcTimeout` locally when it expires. Raft write callers similarly
  provide an operation timeout.
- **Cancellation:** ManyFold sends typed cancellation on caller cancellation,
  deadline expiry, disconnect, or endpoint disposal. Heart handlers check the
  supplied `RpcCancellation` before and after reading the projection.
- **Leader failure:** writes discover and retry the new Raft leader using the
  same command ID. An unknown timeout outcome is therefore safe to retry.
- **Reconnect:** RPC does not replay an ambiguous request across sessions; old
  calls fail with `RpcDisconnected`, and callers issue a new request after the
  endpoint handshake. Durable delivery does replay its journaled mode command
  until an ACK arrives.
- **Stale responses:** every world read includes the locally applied Raft
  revision. `WorldRpcClient` remembers the highest observed revision and raises
  `StaleWorldResponseError` instead of accepting an older follower response.

Production links must use ManyFold mutual TLS. The proof uses the explicit
loopback-only insecure development mode. Retention limits, message TTL, dedupe
retention, queue sizes, and storage bounds are required `DeliveryConfig` and
`TransportConfig` choices; size them from the longest supported device outage.

## Reproducible proof

Run the real three-process story and write a machine-readable artifact:

```shell
uv run python scripts/verify_manyfold_world_coordination.py \
  --output .artifacts/heart-manyfold-coordination.json
```

The script:

1. creates a configurable three-member ManyFold Raft cluster;
1. commits and reads a Heart device record;
1. kills the current leader and waits for a different leader;
1. commits the active-mode command, retries its command ID, and verifies the
   retry retains one sequence;
1. restarts the failed member and verifies all three logs and Heart projections
   converge;
1. reads the recovered device projection over real ManyFold typed RPC;
1. journals the committed mode command, restarts the receiver before ACK,
   reconnects, applies it once, ACKs it, and verifies the sender outbox drains.

The artifact contains process and leader identities, per-node command IDs and
revisions, RPC read results, durable-delivery ACK/application counters, and the
explicit hot-path exclusion list. It also records the installed ManyFold
distribution version, installation kind, installation root, and PEP 610 direct
URL metadata under `manyfold_installation`.

To qualify an installed candidate wheel without letting `uv run` restore the
Git-pinned dependency:

```shell
uv sync --locked
uv pip install --python .venv/bin/python --reinstall \
  /absolute/path/to/manyfold-0.1.42-cp310-abi3-platform.whl
.venv/bin/python scripts/verify_manyfold_world_coordination.py \
  --output .artifacts/heart-manyfold-wheel-coordination.json
```

The wheel artifact must report
`manyfold_installation.install_kind == "wheel"` and the candidate version and
wheel URL in `distribution_version` and `direct_url`. Its coordination fields
must report `raft.node_count == 3`, `raft.leader_changed == true`,
`raft.mode_sequence == raft.duplicate_mode_sequence == 2`, every
`raft.node_revisions` value as `2`, `world_rpc.device_id == "totem3"`,
`durable_delivery.receiver_restarted == true`,
`durable_delivery.applied_count == 1`,
`durable_delivery.receiver_acknowledgements == 1`, and
`durable_delivery.sender_outbox_items == 0`.

The CI entrypoint is:

```shell
uv run pytest tests/test_world.py tests/test_world_coordination.py -q
```

Mesh consumer PR949 (`0926ac90923fb21e88ba63fbb74606c755c420b5`) is based on
the signer PR948 merge (`09ef33b3386e37018cfdba3484ac1f428c8ad034`) and pins
public ManyFold commit `726f64d72b36d8bd134bda63e29ebd80472736b6`.
Replace that Git pin with its qualified released version after the stack lands;
do not add a Graph compatibility path.
