import Papa from "papaparse";

export const DEVICE_CSV_COLUMNS = [
  "name",
  "endpoint",
  "transport",
  "ssh_user",
  "ssh_password",
  "become_password",
  "passwordless_ssh",
  "bootstrap_password",
  "daemon_port",
];

export function deviceCsvRows(devices) {
  return devices.map((device) => {
    const transport = device.transport || "ssh";
    return {
      name: device.inventory_name || device.name,
      endpoint: device.endpoint || "",
      transport,
      ssh_user: transport === "ssh" ? device.ssh_user || "" : "",
      ssh_password: "",
      become_password: "",
      passwordless_ssh: transport === "ssh" ? String(device.passwordless_ssh ?? true) : "true",
      bootstrap_password: "",
      daemon_port: transport === "reachy_daemon" ? device.daemon_port || 8000 : "",
    };
  });
}

export function createDeviceCsv(devices) {
  return Papa.unparse(deviceCsvRows(devices), {
    columns: DEVICE_CSV_COLUMNS,
    newline: "\r\n",
  });
}
