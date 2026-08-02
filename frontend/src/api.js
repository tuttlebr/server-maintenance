import { sortByHostname } from "./utils/hosts.js";

const BASE = "/api/v1";

const DEFAULT_TIMEOUT_MS = 30_000;

function getToken() {
  return localStorage.getItem("fleet_token");
}

export function setToken(token) {
  localStorage.setItem("fleet_token", token);
}

export function clearToken() {
  localStorage.removeItem("fleet_token");
}

export function isAuthenticated() {
  return !!getToken();
}

// Error with friendly message and the raw backend detail attached for "Show details" UIs.
export class ApiError extends Error {
  constructor(message, { status = 0, detail = "", cause = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    if (cause) this.cause = cause;
  }
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }

  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const externalSignal = options.signal;
  const controller = new AbortController();
  const onExternalAbort = () => controller.abort();
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else externalSignal.addEventListener("abort", onExternalAbort, { once: true });
  }
  const timeoutId = timeoutMs > 0 ? setTimeout(() => controller.abort("timeout"), timeoutMs) : null;

  let res;
  try {
    res = await fetch(`${BASE}${path}`, { ...options, headers, signal: controller.signal });
  } catch (err) {
    if (timeoutId) clearTimeout(timeoutId);
    if (externalSignal) externalSignal.removeEventListener("abort", onExternalAbort);
    if (err.name === "AbortError" || controller.signal.aborted) {
      throw new ApiError("Request timed out — the operation may still be running. Check Jobs.", {
        status: 0,
        detail: `Timed out after ${timeoutMs}ms`,
        cause: err,
      });
    }
    throw new ApiError("Network error — unable to reach the server.", {
      status: 0,
      detail: String(err?.message || err),
      cause: err,
    });
  }
  if (timeoutId) clearTimeout(timeoutId);
  if (externalSignal) externalSignal.removeEventListener("abort", onExternalAbort);

  if (res.status === 401) {
    clearToken();
    window.location.hash = "#/login";
    throw new ApiError("Session expired — please sign in again.", { status: 401 });
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = data.detail || `HTTP ${res.status}`;
    throw new ApiError(detail, { status: res.status, detail });
  }

  // Some endpoints may return no body (204 etc.)
  if (res.status === 204) return null;
  return res.json();
}

// Auth
export const login = (username, password) =>
  request("/auth/login", {
    method: "POST",
    body: { username, password },
  });

// Hosts
export const getHosts = () => request("/hosts").then(sortByHostname);
export const getHost = (hostname) => request(`/hosts/${hostname}`);
export const addHost = (data) => request("/hosts", { method: "POST", body: data });
export const updateHost = (hostname, data) => request(`/hosts/${hostname}`, { method: "PUT", body: data });
export const deleteHost = (hostname) => request(`/hosts/${hostname}`, { method: "DELETE" });
export const bulkAddHosts = (data) => request("/hosts/bulk-add", { method: "POST", body: data });
export const bulkAddHostsCsv = (formData) =>
  request("/hosts/bulk-add-csv", { method: "POST", body: formData });
export const previewHostEnrollment = (data) =>
  request("/hosts/enrollment-preview", { method: "POST", body: data, timeoutMs: 45_000 });
export const enrollHosts = (data) =>
  request("/hosts/bulk-enroll", { method: "POST", body: data, timeoutMs: 120_000 });
export const scanHost = (hostname) => request(`/hosts/${hostname}/scan`, { method: "POST" });
export const scanAllHosts = () => request("/hosts/scan-all", { method: "POST" });

// Users
export const getUsers = () => request("/users");
export const bulkAddUsers = (data) => request("/users/bulk-add", { method: "POST", body: data });
export const bulkAddUsersCsv = (formData) =>
  request("/users/bulk-add-csv", { method: "POST", body: formData });
export const bulkUpdateUsers = (data) => request("/users/bulk-update", { method: "PUT", body: data });
export const changePassword = (username, data) =>
  request(`/users/${username}/change-password`, { method: "POST", body: data });
export const bulkPasswordReset = (data) =>
  request("/users/bulk-password-reset", { method: "POST", body: data });
export const addSudoers = (username, data) =>
  request(`/users/${username}/add-sudoers`, { method: "POST", body: data || {} });
export const removeSudoers = (username, data) =>
  request(`/users/${username}/remove-sudoers`, { method: "POST", body: data || {} });
export const removeUser = (username, data) =>
  request(`/users/${username}`, { method: "DELETE", body: data || {} });

// Jobs
export const getJobs = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/jobs${qs ? "?" + qs : ""}`);
};
export const getJob = (jobId) => request(`/jobs/${jobId}`);
export const cancelJob = (jobId) => request(`/jobs/${jobId}/cancel`, { method: "POST" });

// Drivers
export const getDriverStatus = () => request("/drivers").then(sortByHostname);
export const upgradeDrivers = (data) => request("/drivers/upgrade", { method: "POST", body: data });

// Networking
export const getNetworkingStatus = () => request("/networking/status").then(sortByHostname);
export const manageFabricManager = (action, data) =>
  request(`/networking/fabric-manager/${action}`, { method: "POST", body: data || {} });

// Maintenance
export const runPackageUpdate = (data) =>
  request("/maintenance/package-update", { method: "POST", body: data || {} });
export const runDockerCleanup = (data) =>
  request("/maintenance/docker-cleanup", { method: "POST", body: data || {} });
export const runPreflightCheck = (data) =>
  request("/maintenance/preflight-check", { method: "POST", body: data || {} });
export const runHealthDiagnostics = (data) =>
  request("/maintenance/health-diagnostics", { method: "POST", body: data || {} });
export const runHostBootstrap = (data) =>
  request("/maintenance/host-bootstrap", { method: "POST", body: data || {} });
export const runFirmwareInventory = (data) =>
  request("/maintenance/firmware-inventory", { method: "POST", body: data || {} });
export const runFirmwareUpdate = (data) =>
  request("/maintenance/firmware-update", { method: "POST", body: data || {} });
export const runDrainAction = (action, data) =>
  request(`/maintenance/drain/${action}`, { method: "POST", body: data || {} });
export const runMigAction = (action, data) =>
  request(`/maintenance/mig/${action}`, { method: "POST", body: data || {} });
export const getRebootRequired = () => request("/maintenance/reboot-required").then(sortByHostname);
export const rebootHosts = (data) =>
  request("/maintenance/reboot", { method: "POST", body: data || {} });
export const getMaintenanceOverview = () => request("/maintenance/overview");
export const runStorageAnalysis = (data) =>
  request("/maintenance/storage-analysis", { method: "POST", body: data || {} });
export const getStorageAnalysis = () => request("/maintenance/storage-analysis").then(sortByHostname);
export const runGpuUsage = (data) =>
  request("/maintenance/gpu-usage", { method: "POST", body: data || {} });
export const getGpuUsage = () => request("/maintenance/gpu-usage").then(sortByHostname);
export const getDiskUsage = () => request("/maintenance/disk-usage").then(sortByHostname);

// Chat
export const getChatStatus = () => request("/chat/status");
export const getDocsIndexStatus = () => request("/chat/index-status");
export const reindexDocs = () => request("/chat/reindex-docs", { method: "POST" });

// Job output streaming — uses fetch streaming so the bearer token sits in a
// real Authorization header instead of the URL (no token leak in logs/history).
export async function streamJobOutput(jobId, { onLine, onDone, onError, signal } = {}) {
  const token = getToken();
  try {
    const res = await fetch(`${BASE}/jobs/${jobId}/stream`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      signal,
    });

    if (res.status === 401) {
      clearToken();
      window.location.hash = "#/login";
      throw new ApiError("Session expired — please sign in again.", { status: 401 });
    }
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new ApiError(data.detail || `Stream failed: ${res.status}`, {
        status: res.status,
        detail: data.detail || "",
      });
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let doneStatus = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // SSE events split on blank lines (\n\n), individual fields on \n
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep partial last line
      for (const line of lines) {
        if (line.startsWith("event: done")) {
          // Next data: line carries the final status. Easiest path: keep a flag and
          // capture on the next iteration's data line.
          doneStatus = "pending";
          continue;
        }
        if (line.startsWith("data: ")) {
          const payload = line.slice(6);
          if (doneStatus === "pending") {
            doneStatus = payload;
            continue;
          }
          onLine?.(payload);
        }
      }
    }
    onDone?.(doneStatus || "success");
  } catch (err) {
    if (err.name === "AbortError") return; // caller-initiated cancel; not an error
    onError?.(err);
  }
}

// Stream a chat response from the backend. Callback shape:
//   { onContent(text), onStatus(text), onDone(), onError(err), signal? }
// Backwards compatible: a single function callback receives only content chunks.
export async function streamChat(messages, handlersOrChunkFn, legacyOnDone, legacyOnError) {
  const handlers = typeof handlersOrChunkFn === "function"
    ? { onContent: handlersOrChunkFn, onDone: legacyOnDone, onError: legacyOnError }
    : (handlersOrChunkFn || {});
  const onContent = handlers.onContent || (() => {});
  const onStatus = handlers.onStatus || (() => {});
  const onDone = handlers.onDone || (() => {});
  const onError = handlers.onError || (() => {});

  const token = getToken();
  try {
    const res = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ messages }),
      signal: handlers.signal,
    });

    if (res.status === 401) {
      clearToken();
      window.location.hash = "#/login";
      throw new ApiError("Session expired — please sign in again.", { status: 401 });
    }

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new ApiError(data.detail || `Chat failed: ${res.status}`, {
        status: res.status,
        detail: data.detail || "",
      });
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith("event: done")) {
          onDone();
          return;
        }
        if (line.startsWith("data: ")) {
          try {
            const payload = JSON.parse(line.slice(6));
            // New typed envelope: {type: "content"|"status"|"error", ...}
            if (payload.type === "content" && payload.content) {
              onContent(payload.content);
            } else if (payload.type === "status" && payload.text) {
              onStatus(payload.text);
            } else if (payload.type === "error") {
              onError(new Error(payload.message || "Chat error"));
              return;
            }
            // Legacy shape (untyped): {content} or {error}
            else if (payload.error) {
              onError(new Error(payload.error));
              return;
            } else if (payload.content) {
              onContent(payload.content);
            }
          } catch {
            // skip malformed JSON
          }
        }
      }
    }
    onDone();
  } catch (err) {
    if (err.name === "AbortError") return;
    onError(err);
  }
}
