import assert from "node:assert/strict";
import test from "node:test";
import Papa from "papaparse";
import { createDeviceCsv, DEVICE_CSV_COLUMNS } from "./deviceCsv.js";

test("device CSV matches the importer and excludes stored credentials", () => {
  const csv = createDeviceCsv([
    {
      name: "Friendly lab server",
      inventory_name: "compute-01",
      endpoint: "192.0.2.10",
      transport: "ssh",
      ssh_user: "fleetadmin",
      passwordless_ssh: false,
      ssh_password: "must-not-export",
      become_password: "must-not-export",
      bootstrap_password: "must-not-export",
    },
    {
      name: "Reachy Lab",
      inventory_name: "reachy-lab",
      endpoint: "reachy-mini.local",
      transport: "reachy_daemon",
      daemon_port: 8123,
    },
  ]);
  const parsed = Papa.parse(csv, { header: true, skipEmptyLines: true });

  assert.deepEqual(parsed.meta.fields, DEVICE_CSV_COLUMNS);
  assert.deepEqual(parsed.data, [
    {
      name: "compute-01",
      endpoint: "192.0.2.10",
      transport: "ssh",
      ssh_user: "fleetadmin",
      ssh_password: "",
      become_password: "",
      passwordless_ssh: "false",
      bootstrap_password: "",
      daemon_port: "",
    },
    {
      name: "reachy-lab",
      endpoint: "reachy-mini.local",
      transport: "reachy_daemon",
      ssh_user: "",
      ssh_password: "",
      become_password: "",
      passwordless_ssh: "true",
      bootstrap_password: "",
      daemon_port: "8123",
    },
  ]);
});
