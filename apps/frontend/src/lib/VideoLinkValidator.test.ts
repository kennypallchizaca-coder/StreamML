import { describe, expect, it } from "vitest";

import { validateVdoNinjaLink } from "./VideoLinkValidator";


describe("validateVdoNinjaLink", () => {
  it("accepts and normalizes a VDO.Ninja view URL", () => {
    const result = validateVdoNinjaLink("  https://vdo.ninja/?view=streamml-demo  ");
    expect(result).toMatchObject({ isValid: true, type: "view", isError: false });
    expect(result.sanitizedUrl).toBe("https://vdo.ninja/?view=streamml-demo");
  });

  it("rejects the phone push URL because it is not a viewing source", () => {
    const result = validateVdoNinjaLink("https://vdo.ninja/?push=streamml-demo");
    expect(result).toMatchObject({ isValid: false, type: "push", isError: true });
  });

  it.each([
    "javascript:alert(1)",
    "http://vdo.ninja/?view=demo",
    "https://attacker.example/?view=demo",
  ])("rejects unsafe input: %s", (value) => {
    expect(validateVdoNinjaLink(value).isValid).toBe(false);
  });
});
