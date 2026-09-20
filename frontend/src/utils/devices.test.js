import assert from "node:assert/strict";
import test from "node:test";
import { deviceMatchesSearch, devicePlatformName } from "./devices.js";

test("device platform prefers the DGX pretty name", () => {
  const device = {
    facts: { dgx: { name: "DGX Spark", pretty_name: "  NVIDIA DGX Spark  " } },
  };

  assert.equal(devicePlatformName(device), "NVIDIA DGX Spark");
});

test("device platform falls back to the DGX name", () => {
  assert.equal(
    devicePlatformName({ facts: { dgx: { name: "DGX Spark", pretty_name: "" } } }),
    "DGX Spark",
  );
  assert.equal(devicePlatformName({ vendor: "NVIDIA" }), "");
});

test("device search includes DGX metadata and existing identity fields", () => {
  const device = {
    name: "daedalus-06",
    vendor: "ASUSTeK COMPUTER INC.",
    model: "GX10",
    endpoint: "192.0.2.6",
    facts: {
      dgx: {
        name: "DGX Spark",
        pretty_name: "NVIDIA DGX Spark",
        platform: "GX10DGX",
      },
    },
  };

  assert.equal(deviceMatchesSearch(device, "dgx spark"), true);
  assert.equal(deviceMatchesSearch(device, "gx10dgx"), true);
  assert.equal(deviceMatchesSearch(device, "asustek"), true);
  assert.equal(deviceMatchesSearch(device, "asustek computer inc. gx10"), true);
  assert.equal(deviceMatchesSearch(device, "192.0.2.6"), true);
  assert.equal(deviceMatchesSearch(device, "reachy"), false);
});
