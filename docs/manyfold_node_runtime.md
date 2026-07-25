# ManyFold node runtime

Heart owns one `ManyfoldNodeRuntime` per process. The runtime container starts it
before peripheral detection, the game loop calls its bounded `poll()`, and
shutdown closes it before the process exits.

The integration uses only public APIs from ManyFold main commit
`726f64d72b36d8bd134bda63e29ebd80472736b6`. Canonical
`manyfold.cluster.NodeRuntime` owns signer acquisition, discovery,
mutually-authenticated bootstrap links, membership, SWIM, reconnect, and
shutdown. Heart composes the public `TransportMesh` beside it because PubSub
mesh construction is deliberately outside `NodeRuntime`. There are no
compatibility aliases, runtime version checks, Heart transports, or Heart
keepalives.

## Trust and liveness

A discovery result is an address candidate only. It does not enter membership
until the canonical bootstrap link authenticates a short-lived process
credential issued by the local `MachineSignerService`. The certificate is
rooted in cluster enrollment and binds:

```text
manyfold://identity/<cluster_id>/<node_id>
```

SWIM owns probing, suspicion, death, leave dissemination, and incarnation
changes. `ManyfoldNodeRuntime.poll()` only coalesces low-rate sensor state,
drains at most 64 queued mesh publications, and reads immutable snapshots.
Discovery, loss detection, and reconnect remain on upstream workers instead of
blocking the game loop.

## Distribution policy

`HEART_TOPIC_POLICIES` is the authoritative policy.
`topic_policy_manifest()` exposes the same policy as JSON.

| Named topic | Delivery | Durable | Raft |
| --- | --- | --- | --- |
| `heart.node.status` | Mesh best-effort | No | No |
| `heart.input.navigation` | Mesh best-effort | No | No |
| `heart.sensor.external.state` | Mesh coalesced at 10 Hz | No | No |
| `heart.frame_tick` | Local | No | No |
| `heart.rendered_frame` | Local | No | No |
| `heart.microphone.level` | Local | No | No |
| `heart.input` | Local debug tap | No | No |

Heart subscribes the mesh to exactly the first three topics. Navigation and
sensor envelopes carry a globally unique event ID. The origin ignores its mesh
echo, each process retains a bounded 4,096-ID duplicate window, and remote
events retain their ID when republished locally. This prevents one physical
navigation action from being applied twice when multiple peers observe it or a
mesh contains cycles.

Sensor updates are last-value coalesced. Frames, frame ticks, microphone-rate
samples, and debug taps never enter mesh, durable delivery, or Raft.

## Configuration

Set `HEART_MANYFOLD_CONFIG` to a strict JSON file. Leaving it unset disables
distributed operation without starting workers. The machine signer must
already be running and the node must already be enrolled.

Bootstrap TCP and SWIM UDP share the numeric `listen_port`. The PubSub mesh
listener uses a separate port.

```json
{
  "cluster_id": "heart",
  "node_id": "totem1",
  "instance_id": "totem1-boot-20260725",
  "incarnation": 12,
  "listen_host": "0.0.0.0",
  "listen_port": 7443,
  "signer_socket": "/run/manyfold/signer.sock",
  "connector_server_hostname": "totem2.local",
  "swim_key_hex": "<64 hexadecimal characters>",
  "peers": [
    {
      "node_id": "totem2",
      "bootstrap_host": "totem2.local",
      "bootstrap_port": 7443,
      "mesh_host": "totem2.local",
      "mesh_port": 7444,
      "swim_key_hex": "<totem2's 64 hexadecimal characters>",
      "mesh_role": "connect"
    }
  ]
}
```

The listener side uses `mesh_role: "listen"` and adds
`mesh_listen_host`/`mesh_listen_port` to the peer entry. A process restart must
use a fresh `instance_id` and a higher incarnation. Signer state and SWIM keys
are deployment secrets and must not be committed.

## Real-process qualification

PR 945 is the prerequisite Heart migration. The dependency is pinned to the
canonical ManyFold commit, so the qualification needs no `PYTHONPATH` override:

```sh
HEART_MANYFOLD_TEST_ARTIFACT=/tmp/heart-manyfold-mesh.json \
uv run pytest -n 0 \
tests/runtime/test_manyfold_node_mesh.py::test_real_process_mesh_story -q
```

The test runs two spawned Heart processes plus two real machine signer services
over TCP, UDP, and Unix sockets. In one continuous story it proves:

1. An offline discovered address remains unauthenticated and outside membership.
1. Enrollment-backed mutual TLS authenticates the peer, SWIM admits it, and
   three PubSub interests converge.
1. One navigation event and one accelerometer update reach each process once.
1. Killing a peer causes SWIM death and reconnect status while foreground poll
   CPU remains below 50 ms.
1. Restarting with a new instance and incarnation restores bootstrap, SWIM,
   mesh, subscriptions, navigation, and sensor delivery.
1. Duplicate counts remain bounded and both surviving processes shut down with
   no ManyFold worker threads.

The command writes `/tmp/heart-manyfold-mesh.json`. Machine assertions include
exactly-once navigation/sensor counts, all story booleans, the exact upstream
commit, and:

```json
{
  "durable_delivery_topics": [],
  "raft_topics": [],
  "local_only_topics": [
    "heart.frame_tick",
    "heart.rendered_frame",
    "heart.microphone.level",
    "heart.input"
  ]
}
```

Those fields are the consumer gate proving hot paths do not enter durable
delivery or Raft. `max_poll_seconds_during_story` is per-thread CPU time, so
parallel CI scheduling cannot be mistaken for inline discovery or SWIM work.
