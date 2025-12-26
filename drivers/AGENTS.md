# Drivers Agent Instructions

## CircuitPython constraints
- Assume these drivers will run under CircuitPython first and CPython second. Keep dependencies to the built-ins that ship with CircuitPython or a clearly documented external bundle.
- Avoid dynamic imports, reflection, or heavy use of Python metaprogramming features that CircuitPython omits.
- Prefer small, synchronous functions. CircuitPython lacks threads and has very limited heap space, so do not allocate large temporary buffers or rely on recursion.
- Keep tunable thresholds as module-level constants so they are easy to discover and adjust.

## Debugging guidance
- When adding diagnostic output, use `print` statements guarded behind a module-level `DEBUG` flag rather than logging frameworks that CircuitPython does not ship with by default.
- Keep exception handling minimal; allow errors to propagate so they can be inspected over the serial REPL. Only catch exceptions when you can recover or to add chip-specific hints.
- Include docstrings that describe how to reproduce hardware issues via the REPL so that future debugging does not require the full game runtime.

## Testing philosophy
- Provide a pure-Python shim or simulator whenever practical so unit tests can run on CI. Hardware-specific modules should be isolated behind thin adapters that can be mocked.
- Document any hardware timing requirements (debounce, sensor warm-up delays, etc.) in the module docstring.
