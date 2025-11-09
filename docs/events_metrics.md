# Keyed metric conventions

The helper classes in [`src/heart/events/metrics.py`](../src/heart/events/metrics.py)
now expose a common scaffolding for keyed aggregates. Use
`heart.events.metrics.KeyedMetric` when creating a new metric so the
following behaviours remain consistent:

- **`observe(key, ...)`** records data for the key without mutating prior
  snapshots.
- **`get(key)`** returns the latest aggregate value for a single key. Metrics
  may return `None` when they have no observations.
- **`snapshot()`** returns a fresh mapping that callers can mutate safely.
- **`reset(key=None)`** clears the stored data for a key or, when omitted, every
  key. Unknown keys are ignored so the method stays idempotent.

`RollingAverageByKey` demonstrates how lightweight wrappers can delegate the
heavy lifting to `RollingStatisticsByKey` while still complying with the
interface. New metrics can follow the same pattern to reuse the rolling window
utilities without exposing internal state.
