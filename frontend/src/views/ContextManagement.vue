<template>
  <div>
    <div class="page-header">
      <div><h2>Knowledge sources</h2><p class="page-subtitle">Manage the documentation and device metadata Fleet Help uses for retrieval.</p></div>
      <button class="btn btn-primary btn-sm" :disabled="status.running" @click="startReindex"><i :class="['fas', status.running ? 'fa-spinner fa-spin' : 'fa-arrows-rotate']" aria-hidden="true"></i>{{ status.running ? 'Re-indexing…' : 'Re-index context' }}</button>
    </div>

    <div class="stat-row context-stats">
      <article class="stat-card"><div class="stat-value">{{ status.record_count ?? '—' }}</div><div class="stat-label">Indexed records</div></article>
      <article class="stat-card"><div class="stat-value">{{ status.document_count }}</div><div class="stat-label">Uploaded documents</div></article>
      <article class="stat-card"><div class="stat-value">{{ status.annotated_device_count }}</div><div class="stat-label">Annotated devices</div></article>
      <article class="stat-card"><div class="stat-value stat-time">{{ status.last_indexed_at ? formatLongTime(status.last_indexed_at) : 'Never' }}</div><div class="stat-label">Last indexed</div></article>
    </div>

    <section v-if="status.running || status.error" :class="['card', 'index-state', { error: status.error }]">
      <div class="card-body">
        <div class="index-state-row"><strong>{{ status.error ? 'Re-index failed' : phaseLabel }}</strong><span v-if="status.total">{{ status.progress }} / {{ status.total }}</span></div>
        <div v-if="status.running" class="progress-bar"><div class="progress-fill" :style="{ width: `${progressPercent}%` }"></div></div>
        <p>{{ status.error || status.message }}</p>
      </div>
    </section>

    <div class="context-layout">
      <section class="card upload-card">
        <div class="card-body">
          <h3>Upload documentation</h3>
          <p class="muted">Add a UTF-8 text or Markdown file<span v-if="status.parser_enabled">, PDF, or PNG/JPEG page image</span> up to {{ formatBytes(status.upload_max_bytes) }}.<span v-if="status.parser_enabled"> PDFs support up to {{ status.parser_max_pages }} pages and are parsed during upload.</span> Associate hardware manuals with a device so retrieval includes that relationship.</p>
          <form @submit.prevent="upload">
            <div class="form-group"><label class="form-label" for="context-file">Document</label><input :key="fileInputKey" id="context-file" class="file-input" type="file" :accept="acceptedFiles" required :disabled="uploading" @change="selectFile" /></div>
            <div class="form-group"><label class="form-label" for="context-title">Title <span>(optional)</span></label><input id="context-title" v-model="uploadForm.title" :disabled="uploading" class="form-input" maxlength="200" placeholder="Uses the document heading or filename" /></div>
            <div class="form-group"><label class="form-label" for="context-device">Associated device <span>(optional)</span></label><select id="context-device" v-model="uploadForm.device_id" :disabled="uploading" class="form-select"><option value="">General fleet documentation</option><option v-for="device in devices" :key="device.id" :value="String(device.id)">{{ device.name }} ({{ device.inventory_name }})</option></select></div>
            <button class="btn btn-primary" type="submit" :disabled="!uploadForm.file || uploading"><i :class="['fas', uploading ? 'fa-spinner fa-spin' : 'fa-upload']" aria-hidden="true"></i>{{ uploading ? 'Processing document…' : 'Upload document' }}</button>
          </form>
          <section v-if="uploadState" class="upload-progress" :class="{ 'upload-error': ['failed', 'interrupted'].includes(uploadState.phase) }" aria-label="Document upload status">
            <div role="status" aria-live="polite" aria-atomic="true">
              <strong>{{ uploadLabel }}</strong>
              <p v-if="uploadDetail">{{ uploadDetail }}</p>
            </div>
            <progress v-if="uploading && !['complete', 'failed'].includes(uploadState.phase)" :value="uploadPercent ?? undefined" max="100" :aria-label="uploadLabel"></progress>
            <p class="upload-timing">Elapsed {{ formatDuration(uploadElapsed) }}<span v-if="lastPageAge != null && uploadState.phase === 'parsing'"> · Last page completed {{ formatDuration(lastPageAge) }} ago</span></p>
            <p v-if="uploadState.connectionWarning" class="upload-warning">{{ uploadState.connectionWarning }}</p>
          </section>
          <p class="reindex-note"><i class="fas fa-circle-info" aria-hidden="true"></i>Uploads and annotation changes become searchable after the next re-index.</p>
        </div>
      </section>

      <section class="card documents-card">
        <div class="card-body section-heading"><div><h3>Uploaded documents</h3><p class="muted">{{ documents.length }} source{{ documents.length === 1 ? '' : 's' }} managed by Fleet Manager.</p></div><button class="btn btn-ghost btn-sm" :disabled="loading" @click="load"><i :class="['fas', loading ? 'fa-spinner fa-spin' : 'fa-sync-alt']" aria-hidden="true"></i>Refresh</button></div>
        <div v-if="documents.length" class="table-wrapper document-table"><table class="table-reflow"><thead><tr><th>Document</th><th>Device</th><th>Size</th><th>Uploaded</th><th></th></tr></thead><tbody><tr v-for="document in documents" :key="document.id"><td data-label="Document"><div class="document-name"><strong>{{ document.title }}</strong><small>{{ document.original_filename }}</small></div></td><td data-label="Device">{{ document.device_name || 'General' }}</td><td data-label="Size">{{ formatBytes(document.size_bytes) }}</td><td data-label="Uploaded">{{ formatLongTime(document.created_at) }}</td><td data-label="Action"><button class="btn btn-ghost btn-icon remove-button" type="button" :aria-label="`Remove ${document.title}`" @click="askDelete(document)"><i class="fas fa-trash" aria-hidden="true"></i></button></td></tr></tbody></table></div>
        <div v-else-if="!loading" class="empty-docs"><i class="fas fa-file-lines" aria-hidden="true"></i><p>No uploaded context yet.</p></div>
      </section>
    </div>

    <ConfirmDialog :visible="deleteTarget != null" title="Remove context document" :message="deleteTarget ? `Remove ${deleteTarget.title}? Its existing index records remain searchable until the next re-index.` : ''" confirm-text="Remove document" danger-mode @confirm="removeDocument" @cancel="deleteTarget = null" />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import { deleteContextDocument, getContextDocuments, getContextStatus, getDevices, reindexContext, startContextUpload, getContextUpload, uploadContextDocument } from "../api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import { formatLongTime } from "../utils/time.js";

const route = useRoute();
const status = reactive({ parser_enabled: false, upload_max_bytes: 10 * 1024 * 1024, parser_max_pages: 20, parser_timeout_seconds: 100, record_count: null, document_count: 0, annotated_device_count: 0, running: false, phase: "idle", message: "", progress: 0, total: 0, last_indexed_at: null, error: null });
const acceptedFiles = computed(() => ".txt,.md,.markdown,text/plain,text/markdown" + (status.parser_enabled ? ",.pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" : ""));
const documents = ref([]); const devices = ref([]); const loading = ref(true); const uploading = ref(false); const deleteTarget = ref(null); const fileInputKey = ref(0); let pollTimer, disposed = false;
const uploadForm = reactive({ file: null, title: "", device_id: route.query.device ? String(route.query.device) : "" });
const phaseLabel = computed(() => ({ loading: "Loading sources", embedding: "Creating embeddings", inserting: "Updating search index" }[status.phase] || "Re-indexing context"));
const progressPercent = computed(() => status.total ? Math.min(100, Math.round((status.progress / status.total) * 100)) : 5);

async function loadStatus() { try { const result = await getContextStatus(); if (disposed) return; Object.assign(status, result); } catch (error) { if (!disposed) window.$toast?.error("Couldn't load context index status", error); } finally { if (!disposed && status.running) schedulePoll(); } }
async function load() { if (disposed) return; loading.value = true; try { [documents.value, devices.value] = await Promise.all([getContextDocuments(), getDevices()]); if (!disposed) await loadStatus(); } catch (error) { window.$toast?.error("Couldn't load context", error); } finally { loading.value = false; } }
function schedulePoll() { clearTimeout(pollTimer); if (disposed) return; pollTimer = setTimeout(async () => { await loadStatus(); if (!status.running) await load(); }, 1500); }
async function startReindex() { try { const result = await reindexContext(); window.$toast?.success(result.detail); status.running = true; status.error = null; schedulePoll(); } catch (error) { window.$toast?.error("Couldn't start context re-index", error); } }
const uploadState = ref(null);
const uploadNow = ref(Date.now());
let uploadPollTimer, uploadClock, activeUploadId = null;
const uploadElapsed = computed(() => {
  const state = uploadState.value;
  if (!state) return 0;
  return (state.elapsed_seconds ?? 0) + (uploading.value ? Math.max(0, uploadNow.value - state.observedAt) / 1000 : 0);
});
const lastPageAge = computed(() => uploadState.value?.seconds_since_last_page == null ? null : uploadState.value.seconds_since_last_page + Math.max(0, uploadNow.value - uploadState.value.observedAt) / 1000);
const uploadLabel = computed(() => {
  const state = uploadState.value;
  if (!state) return "";
  return ({ uploading: state.transferred ? "Waiting for server…" : "Uploading file…", validating: "Checking document…", rendering: "Preparing pages…", parsing: "Parsing document…", saving: "Saving document…", complete: "Document saved", failed: "Upload failed", interrupted: "Upload status unconfirmed" })[state.phase] || "Processing document…";
});
const uploadDetail = computed(() => {
  const state = uploadState.value;
  if (!state) return "";
  if (state.error) return state.error;
  if (state.phase === "complete") return "Re-index to make this document searchable.";
  if (state.phase === "uploading") return state.bytesTotal ? `${formatBytes(state.bytesSent)} / ${formatBytes(state.bytesTotal)} transferred` : `${formatBytes(state.bytesSent)} transferred`;
  if (state.phase === "rendering" && state.total) return `${state.completed} of ${state.total} pages prepared`;
  if (state.phase === "parsing") return `${state.completed} of ${state.total} pages complete${state.completed < state.total ? `; processing page ${state.completed + 1}` : ""}`;
  return "";
});
const uploadPercent = computed(() => {
  const state = uploadState.value;
  if (!state) return null;
  if (state.phase === "uploading" && !state.transferred && state.bytesTotal) return Math.min(100, state.bytesSent / state.bytesTotal * 100);
  if (["rendering", "parsing"].includes(state.phase) && state.total) return state.completed / state.total * 100;
  return null;
});
function formatDuration(seconds) { const value = Math.max(0, Math.floor(seconds)); return value < 60 ? `${value}s` : `${Math.floor(value / 60)}m ${value % 60}s`; }
function applyUploadStatus(result) {
  Object.assign(uploadState.value, result, { observedAt: Date.now(), connectionWarning: "" });
  uploadNow.value = Date.now();
}
function scheduleUploadPoll(uploadId) {
  clearTimeout(uploadPollTimer);
  if (disposed || !uploading.value || uploadId !== activeUploadId) return;
  uploadPollTimer = setTimeout(async () => {
    try {
      const result = await getContextUpload(uploadId);
      if (disposed || !uploading.value || uploadId !== activeUploadId) return;
      applyUploadStatus(result);
    } catch (error) {
      if (disposed || !uploading.value || uploadId !== activeUploadId) return;
      uploadState.value.connectionWarning = "Progress updates unavailable. Waiting for the upload result…";
    }
    if (!['complete', 'failed'].includes(uploadState.value.phase)) scheduleUploadPoll(uploadId);
  }, 1000);
}
function stopUploadTimers() { clearTimeout(uploadPollTimer); clearInterval(uploadClock); }
function selectFile(event) { uploadForm.file = event.target.files?.[0] || null; if (!uploading.value) uploadState.value = null; }
async function upload() {
  if (!uploadForm.file || uploading.value) return;
  uploading.value = true;
  activeUploadId = null;
  uploadNow.value = Date.now();
  uploadState.value = { phase: "uploading", bytesSent: 0, bytesTotal: null, transferred: false, completed: 0, total: 0, elapsed_seconds: 0, seconds_since_last_page: null, observedAt: Date.now(), error: null, connectionWarning: "" };
  uploadClock = setInterval(() => { uploadNow.value = Date.now(); }, 1000);
  let uploadId;
  const body = new FormData();
  body.append("file", uploadForm.file);
  if (uploadForm.title.trim()) body.append("title", uploadForm.title.trim());
  if (uploadForm.device_id) body.append("device_id", uploadForm.device_id);
  try {
    const reservation = await startContextUpload();
    uploadId = reservation.upload_id;
    activeUploadId = uploadId;
    if (disposed) return;
    body.append("upload_id", uploadId);
    scheduleUploadPoll(uploadId);
    await uploadContextDocument(body, {
      parserTimeoutSeconds: reservation.parser_timeout_seconds ?? status.parser_timeout_seconds,
      onProgress: (loaded, total) => { if (!disposed) Object.assign(uploadState.value, { bytesSent: loaded, bytesTotal: total }); },
      onTransferred: () => { if (!disposed) uploadState.value.transferred = true; },
    });
    if (disposed) return;
    uploadState.value.phase = "complete";
    uploadState.value.connectionWarning = "";
  } catch (error) {
    if (disposed) return;
    // A lost response is not proof that the database commit failed.
    let result;
    if (uploadId) { try { result = await getContextUpload(uploadId); } catch { /* The connection may still be down. */ } }
    if (disposed) return;
    if (result?.phase === "complete") applyUploadStatus(result);
    else {
      uploadState.value.phase = result?.phase === "failed" || (error.status >= 400 && error.status < 500) ? "failed" : "interrupted";
      uploadState.value.error = result?.error || error.message;
      uploadState.value.connectionWarning = "";
    }
  } finally {
    stopUploadTimers();
    if (!disposed) {
      uploadState.value.elapsed_seconds = uploadElapsed.value;
      uploading.value = false;
    }
  }
  if (!disposed && uploadState.value.phase === "complete") {
    uploadForm.file = null;
    uploadForm.title = "";
    fileInputKey.value += 1;
    await load();
  }
}
function askDelete(document) { deleteTarget.value = document; }
async function removeDocument() { const document = deleteTarget.value; deleteTarget.value = null; try { const result = await deleteContextDocument(document.id); window.$toast?.success(result.detail); await load(); } catch (error) { window.$toast?.error("Couldn't remove document", error); } }
function formatBytes(bytes) { if (bytes < 1024) return `${bytes} B`; if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`; return `${(bytes / (1024 * 1024)).toFixed(1)} MB`; }
onMounted(load); onUnmounted(() => { disposed = true; clearTimeout(pollTimer); stopUploadTimers(); });
</script>

<style scoped>
.upload-progress { margin-top: 16px; padding: 12px; border: 1px solid var(--border-color); border-radius: var(--radius-sm); background: var(--surface-light); }
.upload-progress strong { font-size: 13px; }
.upload-progress p { margin: 6px 0 0; font-size: 12px; color: var(--text-secondary); overflow-wrap: anywhere; }
.upload-progress progress { display: block; width: 100%; height: 8px; margin-top: 10px; accent-color: var(--color-accent); }
.upload-progress .upload-timing { font-variant-numeric: tabular-nums; }
.upload-error { border-color: var(--color-danger); }
.upload-progress .upload-warning { color: var(--color-warning, var(--text-primary)); }

.page-subtitle { margin: 4px 0 0; color: var(--text-secondary); }.context-stats { grid-template-columns: repeat(4, 1fr); }.stat-time { font-size: 1rem !important; min-height: 38px; display: flex; align-items: center; }.index-state { margin-bottom: 16px; border-left: 4px solid var(--color-info); }.index-state.error { border-left-color: var(--color-danger); }.index-state-row { display: flex; justify-content: space-between; margin-bottom: 9px; }.index-state p { margin: 9px 0 0; color: var(--text-secondary); font-size: 12px; }.progress-fill { background: var(--color-accent); min-width: 5%; }.context-layout { display: grid; grid-template-columns: minmax(280px, 360px) 1fr; gap: 16px; align-items: start; }.upload-card h3, .section-heading h3 { margin: 0 0 5px; }.muted { color: var(--text-secondary); font-size: 12px; }.form-label span { text-transform: none; letter-spacing: 0; }.file-input { width: 100%; font: inherit; font-size: 12px; color: var(--text-secondary); }.file-input::file-selector-button { margin-right: 10px; padding: 7px 10px; border: 1px solid var(--border-color); border-radius: var(--radius-sm); background: var(--surface-light); color: var(--text-primary); cursor: pointer; }.upload-card form .btn { width: 100%; }.reindex-note { display: flex; gap: 8px; margin: 14px 0 0; color: var(--text-secondary); font-size: 11px; line-height: 1.4; }.section-heading { display: flex; justify-content: space-between; align-items: center; }.section-heading p { margin: 0; }.documents-card > .card-body { border-bottom: 1px solid var(--border-subtle); }.document-table { border: 0; border-radius: 0; box-shadow: none; }.document-name { display: flex; flex-direction: column; max-width: 300px; }.document-name small { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.remove-button { color: var(--color-danger); }.empty-docs { padding: 50px 20px; text-align: center; color: var(--text-secondary); }.empty-docs i { font-size: 24px; }.empty-docs p { margin-bottom: 0; }
@media (max-width: 900px) { .context-stats { grid-template-columns: repeat(2, 1fr); }.context-layout { grid-template-columns: 1fr; } }
@media (max-width: 520px) { .context-stats { grid-template-columns: 1fr; } }
</style>
