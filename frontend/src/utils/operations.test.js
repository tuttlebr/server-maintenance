import assert from "node:assert/strict";
import test from "node:test";
import { selectedOperationTargets } from "./operations.js";

const operation = { eligible_device_ids: [1, 2, 3] };
test("initial and cleared selections target no devices", () => {
  assert.deepEqual(selectedOperationTargets(operation, []), []);
});
test("mixed-fleet selections target only explicitly selected eligible devices", () => {
  assert.deepEqual(selectedOperationTargets(operation, [2, 4, 2]), [2]);
  assert.deepEqual(selectedOperationTargets(operation, [4]), []);
});
