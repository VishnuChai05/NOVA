import { describe, expect, test } from "vitest";

describe("frontend smoke", () => {
  test("sanity", () => {
    expect(1 + 1).toBe(2);
  });
});
