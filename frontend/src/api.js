import { readSse } from "./utils/sse.js";
import { ACTIVE } from "./utils/maintenance.js";

const BASE = "/api/v2";

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

  try {
    const res = await fetch(`${BASE}${path}`, { ...options, headers, signal: controller.signal });
    if (res.status === 401 && path !== "/auth/login") {
      clearToken();
      window.location.hash = "#/login";
      throw new ApiError("Session expired. Please sign in again.", { status: 401 });
    }
    if (!res.ok) {
      const data = await res.json().catch(error => {
        if (controller.signal.aborted) throw error;
        return {};
      });
      const detail = Array.isArray(data.detail) ? data.detail.map(item => `${(item.loc || []).filter(part => part !== "body").join(".")}: ${item.msg}`).join("; ") : data.detail || `HTTP ${res.status}`;
      throw new ApiError(detail, { status: res.status, detail });
    }
    if (res.status === 204) return null;
    return await res.json();
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (externalSignal?.aborted) throw new DOMException("Request cancelled", "AbortError");
    if (controller.signal.aborted) {
      throw new ApiError("Request timed out. The operation may still be running; check Activity.", {
        detail: `Timed out after ${timeoutMs}ms`, cause: err,
      });
    }
    throw new ApiError("Unable to read the server response. Check your connection and retry.", {
      detail: String(err?.message || err), cause: err,
    });
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
    externalSignal?.removeEventListener("abort", onExternalAbort);
  }
}

// Auth
export const login = (username, password) =>
  request("/auth/login", {
    method: "POST",
    body: { username, password },
  });

// Devices
export const getDevices = () => request("/devices").then((items) =>
  [...items].sort((a, b) => a.name.localeCompare(b.name))
);
export const getDevice = (deviceId) => request(`/devices/${deviceId}`);
export const discoverDevice = (data) =>
  request("/devices/discover", { method: "POST", body: data, timeoutMs: 45_000 });
export const addDevice = (data) =>
  request("/devices", { method: "POST", body: data, timeoutMs: 120_000 });
export const updateDevice = (deviceId, data) =>
  request(`/devices/${deviceId}`, { method: "PUT", body: data });
export const updateDeviceAnnotations = (deviceId, annotations) =>
  request(`/devices/${deviceId}/annotations`, { method: "PUT", body: { annotations } });
export const deleteDevice = (deviceId) => request(`/devices/${deviceId}`, { method: "DELETE" });
export const scanDevice = (deviceId) => request(`/devices/${deviceId}/scan`, { method: "POST" });

// Operations
export const getOperations = () => request("/operations");
export const runOperation = (operationId, deviceIds, parameters = {}) =>
  request(`/operations/${operationId}/jobs`, {
    method: "POST",
    body: { device_ids: deviceIds, ...parameters },
  });

// Users
export const previewUsersCsv = (file, mode) => {
  const body = new FormData(); body.append("file", file); body.append("mode", mode);
  return request("/users/csv-preview", { method: "POST", body });
};
export const inspectAccounts = (data) => request("/users/inspect", { method: "POST", body: data });
export const bulkUpdateUsers = (data) => request("/users/bulk-update", { method: "PUT", body: data });
export const getUsers = () => request("/users");
export const bulkAddUsers = (data) => request("/users/bulk-add", { method: "POST", body: data });
// Jobs
export const getJobOverview = () => request("/jobs/overview");
export const cancelJob = (jobId) => request(`/jobs/${jobId}/cancel`, { method: "POST" });
export const getJobs = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/jobs${qs ? "?" + qs : ""}`);
};
export const getJob = (jobId) => request(`/jobs/${jobId}`);
// Active jobs need only state. Fetch logs/artifacts once completion is observed.
export async function getJobProgress(jobId) {
  const progress = await request(`/jobs/${jobId}/progress`);
  return ACTIVE.includes(progress.status) ? progress : getJob(jobId);
}

// Chat
export const getChatStatus = () => request("/chat/status");

// Context management
export const getContextStatus = () => request("/context/status");
export const getContextDocuments = () => request("/context/documents");
export const uploadContextDocument = (formData) =>
  request("/context/documents", { method: "POST", body: formData, timeoutMs: 120_000 });
export const deleteContextDocument = (documentId) =>
  request(`/context/documents/${documentId}`, { method: "DELETE" });
export const reindexContext = () => request("/context/reindex", { method: "POST" });

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

    for await (const event of readSse(res)) {
      if (event.type === 'done') {
        onDone?.(event.data);
        return;
      }
      for (const line of event.data.split('\n')) onLine?.(line);
    }
    throw new ApiError("Stream ended before completion. Refresh activity to check the job.");
  } catch (err) {
    if (err.name === "AbortError") return; // caller-initiated cancel; not an error
    onError?.(err);
  }
}

// Stream a chat response from the backend. Callback shape:
//   { onContent(text), onStatus(text), onDone(), onError(err), signal? }
export async function streamChat(messages, handlers = {}) {
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
      body: JSON.stringify({ messages, job_id: handlers.jobId, device_id: handlers.deviceId }),
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

    for await (const event of readSse(res)) {
      if (event.type === 'done') { onDone(); return; }
      let payload;
      try { payload = JSON.parse(event.data); }
      catch { throw new ApiError("The chat stream returned invalid data. Please retry."); }
      if (payload.type === 'content' && payload.content) onContent(payload.content);
      else if (payload.type === 'status' && payload.text) onStatus(payload.text);
      else if (payload.type === 'error') throw new ApiError(payload.message || "Chat error");
    }
    throw new ApiError("Chat disconnected before completion. Please retry.");
  } catch (err) {
    if (err.name === "AbortError") return;
    onError(err);
  }
}
