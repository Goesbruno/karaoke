import { describe, expect, it } from "vitest";
import { mapYtError } from "./ytErrors";

describe("mapYtError (referrer)", () => {
  it("explica o erro 153", () => {
    expect(mapYtError(153)).toMatch(/Referer/);
  });
});
