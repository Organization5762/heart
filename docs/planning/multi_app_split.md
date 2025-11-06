# Plan: Split Runtime into Dedicated Input and Rendering Applications

## Problem Statement

Separate peripheral ingestion from frame rendering so each concern can scale independently while maintaining deterministic communication between services.

## Materials

- Existing `heart` runtime source code and experimental MQTT sidecar.
- Access to MQTT broker infrastructure for testing (e.g., Mosquitto container).
- Profiling data for current peripheral latency and renderer requirements.
- Development environments for both embedded input hosts and rendering hardware.

## Opening Abstract

The monolithic `totem` runtime currently owns both peripheral ingestion and display rendering. This tight coupling complicates deployment on heterogeneous hardware and prevents remote simulators from consuming live input. We will split the system into an input service that normalises peripheral events and a renderer that subscribes to published messages. By introducing explicit contracts and tooling for each service, we enable headless input gateways, remote renderers, and clearer failure isolation.

### Why Now

Upcoming installations require distributing peripheral capture across constrained hosts while rendering on GPU-equipped systems. Formalising the separation now prevents bespoke integrations and provides a foundation for automated testing.

## Success Criteria

| Behaviour | Signal | Owner |
| --- | --- | --- |
| Renderer consumes MQTT-delivered events without local peripherals | End-to-end demo: input service publishes button press → renderer changes mode | Runtime lead |
| Contracts remain versioned and validated | CI test loads Pydantic schema and rejects malformed payloads | Platform engineer |
| Deployment recipe reproducible within one hour | Docker Compose sample boots broker, input, and renderer with documented steps | Developer experience |

## Task Breakdown Checklists

### Discovery

- [ ] Audit `heart.peripheral` modules to catalogue state they expose today.
- [ ] Benchmark current end-to-end latency to set MQTT QoS expectations.
- [ ] Inventory topics used by `experimental/peripheral_sidecar`.

### Implementation – Input Service

- [ ] Promote the sidecar into `src/heart/input_service` with package metadata.
- [ ] Implement message publishing using shared Pydantic models under `heart/contracts`.
- [ ] Add connection supervision, retry/backoff, and health metrics.
- [ ] Provide a `heart-input` CLI that loads configuration from environment variables or TOML.

### Implementation – Rendering Runtime

- [ ] Introduce an MQTT subscription adapter feeding `AppController` events.
- [ ] Allow `GameLoop` initialisation to choose embedded or remote input mode via dependency injection.
- [ ] Update configuration modules to declare their input source.

### Validation & Deployment

- [ ] Extend integration tests with a fake MQTT broker covering publish/subscribe flows.
- [ ] Produce Docker Compose examples for broker + services.
- [ ] Update documentation (`docs/runtime_overview.md`, `docs/code_flow.md`, `docs/program_configuration.md`) to reflect the architecture.

## Narrative Walkthrough

Discovery clarifies the data structures and latency requirements so the contracts and QoS choices are grounded in existing behaviour. Implementation occurs in two streams: hardening the input service with first-class packaging and observability, and adapting the renderer to consume remote events without regressing the embedded configuration. Validation ties the services together with automated tests and deployment artefacts, ensuring that operators and new contributors can boot the split architecture reliably.

## Visual Reference

| Component | Role | Key Interfaces |
| --- | --- | --- |
| Input Service | Runs peripheral workers, publishes MQTT events, exposes health endpoints | `src/heart/input_service`, `heart/contracts` |
| MQTT Broker | Routes events with configured QoS and retention | Mosquitto (Docker), broker configuration |
| Rendering Service | Subscribes to MQTT, updates `AppController`, renders frames | `heart/environment.py`, subscription adapter |

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Early Warning |
| --- | --- | --- | --- | --- |
| MQTT latency exceeds acceptable thresholds | Medium | High | Benchmark under load, enable QoS 1 with bounded payload sizes | Render logs show stale timestamps |
| Contract drift between services | Medium | Medium | Version schemas and enforce validation in both directions | CI fails contract compatibility tests |
| Input service resource usage too high for embedded hosts | Low | High | Profile memory/CPU, offer optional Rust or C extensions for hotspots | Metrics show sustained >80% CPU |

### Mitigation Tasks

- [ ] Add latency instrumentation to both services and emit metrics.
- [ ] Implement contract compatibility tests that load sample payloads from fixtures.
- [ ] Run the input service on target hardware and collect resource profiles.

## Outcome Snapshot

After implementation, the input service can operate on headless gateways while the renderer runs on dedicated hardware or simulators. Both services communicate through versioned MQTT contracts, deployment artefacts document the topology, and automated tests guard the integration path.
