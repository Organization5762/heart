# World coordination

Heart's durable control plane contains only facts that must survive device and
leader loss:

- device identity, position, dimensions, and capabilities;
- selected mode, immutable configuration ID, and owning device.

ManyFold's persistent Raft log is the sole owner. Heart projects committed
`heart.world.device.put` and `heart.world.mode.select` commands into
`WorldState`, and serves revisioned reads through typed coordinator RPC.
There is no second durable-delivery transport or manual ACK envelope after a
commit.

## Failure semantics

- The caller supplies a stable command ID. Identical retries return the original
  committed sequence; conflicting reuse is rejected.
- `WorldState` applies commands in committed sequence order and treats an
  identical command replay as unchanged.
- Each RPC read carries the applied revision. Clients reject responses older
  than the highest revision they have observed.
- After restart, Heart rebuilds the projection from the public committed log.
- Leader loss is handled by retrying the same command ID against the newly
  elected leader.

Frames, frame ticks, audio, navigation, sensors, and debug events are explicitly
outside this boundary.

## Reproducible Raft proof

The focused proof starts three real coordinator processes, commits a device,
kills the leader, commits and retries the selected mode, restarts the failed
member, verifies all logs and projections converge, and reads the recovered
device over typed RPC:

```sh
HEART_PI5_MATRIX_BACKEND=simulated \
  .venv/bin/python scripts/verify_manyfold_world_coordination.py \
  --output .artifacts/heart-manyfold-coordination.json
```

For the complete mesh, replay, expiry, role-failure, pixel-resync, lifecycle,
and clean-shutdown story, run the shared exact-wheel consumer gate documented
in [ManyFold mesh integration](manyfold_node_runtime.md).
