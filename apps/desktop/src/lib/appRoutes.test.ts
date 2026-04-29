import { expect, test } from "vitest";

import { resolveRoute, routeToHash } from "./appRoutes";

test("resolves creative writing route", () => {
  expect(resolveRoute("#/creative-writing")).toBe("creative-writing");
  expect(routeToHash("creative-writing")).toBe("#/creative-writing");
});

test("resolves upgrade proposal route", () => {
  expect(resolveRoute("#/upgrade-proposals")).toBe("upgrade-proposals");
  expect(routeToHash("upgrade-proposals")).toBe("#/upgrade-proposals");
});
