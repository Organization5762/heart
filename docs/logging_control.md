# Logging sample control

The render loop and other high-frequency components now share a central
controller that manages log sampling and verbosity overrides. The controller
is exposed through `heart.utilities.logging_control.get_logging_controller()`
and can be tuned with environment variables at runtime.

## Default behaviour

- The default sample interval is one second. When a call site uses the shared
  controller, the first log entry is emitted at its requested level and any
  additional entries within the one-second window fall back to `DEBUG` level.
- Set `HEART_LOG_DEFAULT_INTERVAL=none` to disable the global throttle or to a
  floating-point value (seconds) to choose a different cadence.

## Per-key overrides

The `HEART_LOG_RULES` variable accepts a comma-separated list of rules with the
following shape:

```
<key>=<interval>[:<LEVEL>[:<FALLBACK>]]
```

- `<key>`: logical identifier supplied by the call site (e.g. `render.loop`).
- `<interval>`: either `none` to disable sampling or the interval (seconds)
  between primary log emissions.
- `<LEVEL>`: optional log level name (e.g. `INFO`, `WARNING`) to force the
  primary emission to a specific verbosity.
- `<FALLBACK>`: optional level used when a log is suppressed by sampling.
  Provide `none` to drop suppressed logs entirely.

Example: `HEART_LOG_RULES="render.loop=0.5:INFO:DEBUG,ble.poll=none:WARNING:none"`.

These settings allow tuning busy subsystems without editing source code while
keeping structured extras intact for every emission.
