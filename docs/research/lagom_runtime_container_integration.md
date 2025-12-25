# Lagom Runtime Container Integration Notes

## Problem Statement

Runtime services were wired manually in `GameLoop`, and provider registrations relied on a global container living in the peripheral providers package. This split wiring made it difficult to override dependencies consistently and obscured ownership of runtime services.

## Materials

- Source modules under `src/heart/runtime/` and `src/heart/peripheral/core/providers/`.
- CLI entry point in `src/heart/cli/commands/game_loop.py`.
- Runtime flow diagram in `docs/code_flow.md`.

## Source Review

- `src/heart/runtime/container.py` defines the Lagom container builder used for runtime service registration.
- `src/heart/runtime/game_loop_components.py` resolves `GameLoop` dependencies from the container instead of constructing them inline.
- `src/heart/runtime/game_loop.py` accepts the container instance and keeps orchestration logic in one place.
- `src/heart/peripheral/core/providers/registry.py` tracks provider registrations and applies them to registered containers.
- `src/heart/cli/commands/game_loop.py` builds the container before creating the loop to keep wiring consistent.

## Integration Notes

The container builder registers `Device`, `RendererVariant`, and runtime singletons so they can be resolved wherever needed. Provider registration is now centralized in a registry that can apply to any runtime container, allowing late imports (such as renderer modules) to update active containers without a global `Container` instance. This keeps Lagom integration consistent across runtime components while still allowing tests to override dependencies in a single place.
