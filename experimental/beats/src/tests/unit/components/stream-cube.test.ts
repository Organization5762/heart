import { describe, expect, it } from "vitest";

import { getNormalizedStripRect } from "@/components/stream-cube";

describe("stream cube strip normalization", () => {
  it("preserves a native 4:1 strip", () => {
    expect(getNormalizedStripRect(256, 64)).toEqual({
      left: 0,
      top: 0,
      size: 64,
    });
  });

  it("center-crops tall frames into a square-per-face strip", () => {
    expect(getNormalizedStripRect(256, 128)).toEqual({
      left: 0,
      top: 32,
      size: 64,
    });
  });

  it("center-crops wide frames into a square-per-face strip", () => {
    expect(getNormalizedStripRect(512, 64)).toEqual({
      left: 128,
      top: 0,
      size: 64,
    });
  });
});
