import { describe, expect, it } from "vitest";
import { buildQuery } from "./api";

describe("buildQuery", () => {
  it("serializes defined params", () => {
    expect(buildQuery({ q: "ml", page: 2 })).toBe("?q=ml&page=2");
  });

  it("skips empty and undefined values", () => {
    expect(buildQuery({ q: "", tag: undefined, page: 1 })).toBe("?page=1");
  });

  it("returns empty string when nothing to send", () => {
    expect(buildQuery({})).toBe("");
  });

  it("url-encodes values", () => {
    expect(buildQuery({ tag: "ai / ml" })).toBe("?tag=ai+%2F+ml");
  });
});
