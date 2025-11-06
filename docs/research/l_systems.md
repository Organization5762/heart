# L-System Experiments

## Problem Statement

Evaluate whether L-system generated geometry is practical for Heart renderers given runtime constraints and controllability requirements.

## Materials

- Prototype renderer capable of interpreting L-system grammars.
- Benchmark scenes for performance comparison.
- Tooling to profile memory usage as grammar depth increases.

## Technical Approach

1. Generate representative L-system patterns with varying recursion depth.
1. Measure memory growth, frame time, and parameter sensitivity in the renderer.
1. Compare visual controllability and performance against existing procedural techniques.

## Findings

- Grammar size grows rapidly, stressing memory and increasing frame build time.
- Parameter tuning is difficult; small rule changes lead to large visual swings.
- Alternative procedural generators provide similar aesthetics with better control.

## Conclusion

L-systems are not a strong fit for the current runtime without additional tooling for pruning and parameter smoothing. Future exploration should focus on constrained subsets or hybrid approaches if we revisit the technique.
