# Plan: Split runtime into dedicated input and rendering applications

## Objective

- Decouple peripheral ingestion from frame rendering so each concern can evolve independently.
- Allow the input pipeline to run headless (e.g., on embedded gateways) while renderers run on dedicated hardware or simulator hosts.
- Introduce clear API contracts between input and rendering services to simplify testing and deployment.

## Current state snapshot

- The `totem` CLI bootstraps a monolithic runtime where `heart.environment.GameLoop` orchestrates renderers and consumes peripheral events directly.
- Peripheral integrations under `heart/peripheral/` push state into the in-process `AppController` via shared data structures.
- An experimental MQTT sidecar (`experimental/peripheral_sidecar`) already mirrors some peripheral data onto MQTT topics but is not a first-class entry point.
- Rendering assumes access to local peripheral state; there is no formal contract for remote publishers.

## Proposed high-level architecture

1. **Input service (MQTT-driven)**
   - Runs the peripheral workers and publishes normalized events to MQTT topics.
   - Owns responsibility for device discovery, smoothing/aggregation logic, and health reporting.
   - Provides a gRPC/HTTP control plane (optional stretch) for configuration and metrics.
1. **Rendering service**
   - Focuses on frame composition and display output.
   - Subscribes to MQTT topics (directly or via a lightweight adapter) to receive peripheral-derived actions and state snapshots.
   - Exposes hooks for simulators (pygame window) and physical LED devices.
1. **Shared contract**
   - Define versioned schemas for MQTT payloads, ideally as JSON or MessagePack with Pydantic models stored under `heart/contracts/`.
   - Document topic naming conventions and QoS expectations.

## Work breakdown

### Phase 0 – Discovery & prerequisites

- Audit `heart.peripheral` modules to list required data structures and update `docs/code_flow.md` to reflect the current monolithic flow.
- Inventory MQTT topics already used by the experimental sidecar and decide which can be promoted versus replaced.
- Draft contract definitions (Pydantic models) capturing the minimum viable event payloads.

### Phase 1 – Harden the input service

- Promote the experimental sidecar into a supported package under `src/heart/input_service`.
- Integrate all existing peripheral workers so that they publish via the shared contract rather than directly mutating shared state.
- Implement connection supervision, retry/backoff, and metrics collection for MQTT publishing.
- Provide a CLI entry point (`heart-input`) that starts the service with configuration pulled from environment variables or a TOML file.

### Phase 2 – Adapt the rendering runtime

- Add an MQTT subscription client to the renderer app that translates inbound events into the structures expected by `AppController`.
- Refactor `GameLoop` initialization so that peripheral state comes from a stream adapter instead of in-process workers.
- Introduce dependency injection to allow running in "detached" mode (pure renderer) or "embedded" mode (current monolith for backwards compatibility).
- Update configuration modules to request either embedded or remote input sources.

### Phase 3 – Deployment and tooling

- Extend `docs/runtime_overview.md` and `docs/program_configuration.md` with the new split-application architecture.
- Provide docker-compose samples (e.g., `deploy/mqtt-input.yaml`) for running the input service, MQTT broker, and renderer together.
- Update CI/tests to spin up fake MQTT brokers (reuse `tests/test_peripheral_mqtt_integration.py`) for integration coverage across both services.

## Migration considerations

- Maintain compatibility layers so existing scenes continue to operate while the new input bridge matures.
- Ensure MQTT topics encapsulate sufficient context (timestamp, device id, calibration) to support deterministic rendering decisions.
- Plan for version negotiation: include schema version fields in every payload and log warnings for mismatches.
- Decide ownership of persistent configuration (e.g., playlists, device calibration) and how it syncs between services.

## Open questions & risks

- Latency tolerance for MQTT-delivered events: do renderers require sub-50ms updates, and can QoS/retained messages meet that bar?
- Security: evaluate authentication/authorization for MQTT when deploying beyond trusted networks.
- Resource constraints on embedded hosts running the input service, especially with Python + Paho MQTT.
- Failure handling: what happens when the broker or a subscriber disconnects? Define backoff and reconnection semantics.

## Success criteria

- Renderer service can run on a machine without physical peripherals and still respond to simulated input from the MQTT service.
- Automated tests cover the end-to-end flow: peripheral event → MQTT broker → renderer state update → frame output.
- Documentation and sample configs allow a new contributor to deploy the split architecture within an hour.
