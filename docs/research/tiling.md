# Tiling References

## Problem Statement

Identify tiling systems suitable for procedural background generation in Heart renderers.

## Materials

- Research references for Wang, Truchet, rhombitriheptagonal, and Pythagorean tilings.
- Prototype renderer capable of sampling tiles from sprite sheets.
- Tooling to evaluate seamless transitions and repetition artefacts.

## Technical Approach

Survey common tiling schemes and catalogue their constraints for renderer implementation. Focus on edge-matching rules, rotational symmetry, and tile set size to estimate memory and preprocessing requirements.

## Reference Links

- [Wang Tiles](https://en.wikipedia.org/wiki/Wang_tile)
- [Truchet Tiles](https://en.wikipedia.org/wiki/File:Truchet_base_tiling.svg)
- [Rhombitriheptagonal tiling](https://en.wikipedia.org/wiki/Rhombitriheptagonal_tiling)
- [Pythagorean tiling](https://en.wikipedia.org/wiki/Pythagorean_tiling#/media/File:Academ_Periodic_tiling_by_squares_of_two_different_sizes.svg)

## Notes

Evaluate how each tiling handles seams when mapped to the LED matrix and document requirements for tile atlas preparation.
