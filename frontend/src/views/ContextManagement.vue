<template>
  <div>
    <div class="page-header">
      <div><h2>Context</h2><p class="page-subtitle">Manage the documentation and device metadata Fleet Help uses for retrieval.</p></div>
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
          <p class="muted">Add a UTF-8 text or Markdown file up to 10 MB. Associate hardware manuals with a device so retrieval includes that relationship.</p>
          <form @submit.prevent="upload">
            <div class="form-group"><label class="form-label" for="context-file">Document</label><input :key="fileInputKey" id="context-file" class="file-input" type="file" accept=".txt,.md,.markdown,text/plain,text/markdown" required @change="selectFile" /></div>
            <div class="form-group"><label class="form-label" for="context-title">Title <span>(optional)</span></label><input id="context-title" v-model="uploadForm.title" class="form-input" maxlength="200" placeholder="Uses the document heading or filename" /></div>
            <div class="form-group"><label class="form-label" for="context-device">Associated device <span>(optional)</span></label><select id="context-device" v-model="uploadForm.device_id" class="form-select"><option value="">General fleet documentation</option><option v-for="device in devices" :key="device.id" :value="String(device.id)">{{ device.name }} ({{ device.inventory_name }})</option></select></div>
            <button class="btn btn-primary" type="submit" :disabled="!uploadForm.file || uploading"><i :class="['fas', uploading ? 'fa-spinner fa-spin' : 'fa-upload']" aria-hidden="true"></i>{{ uploading ? 'Uploading…' : 'Upload document' }}</button>
          </form>
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
import { deleteContextDocument, getContextDocuments, getContextStatus, getDevices, reindexContext, uploadContextDocument } from "../api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import { formatLongTime } from "../utils/time.js";

const route = useRoute();
const status = reactive({ record_count: null, document_count: 0, annotated_device_count: 0, running: false, phase: "idle", message: "", progress: 0, total: 0, last_indexed_at: null, error: null });
const documents = ref([]); const devices = ref([]); const loading = ref(true); const uploading = ref(false); const deleteTarget = ref(null); const fileInputKey = ref(0); let pollTimer;
const uploadForm = reactive({ file: null, title: "", device_id: route.query.device ? String(route.query.device) : "" });
const phaseLabel = computed(() => ({ loading: "Loading sources", embedding: "Creating embeddings", inserting: "Updating search index" }[status.phase] || "Re-indexing context"));
const progressPercent = computed(() => status.total ? Math.min(100, Math.round((status.progress / status.total) * 100)) : 5);

async function loadStatus() { try { Object.assign(status, await getContextStatus()); if (status.running) schedulePoll(); } catch (error) { window.$toast?.error("Couldn't load context index status", error); } }
async function load() { loading.value = true; try { [documents.value, devices.value] = await Promise.all([getContextDocuments(), getDevices()]); await loadStatus(); } catch (error) { window.$toast?.error("Couldn't load context", error); } finally { loading.value = false; } }
function schedulePoll() { clearTimeout(pollTimer); pollTimer = setTimeout(async () => { await loadStatus(); if (!status.running) await load(); }, 1500); }
async function startReindex() { try { const result = await reindexContext(); window.$toast?.success(result.detail); status.running = true; status.error = null; schedulePoll(); } catch (error) { window.$toast?.error("Couldn't start context re-index", error); } }
function selectFile(event) { uploadForm.file = event.target.files?.[0] || null; }
async function upload() { if (!uploadForm.file) return; uploading.value = true; const body = new FormData(); body.append("file", uploadForm.file); if (uploadForm.title.trim()) body.append("title", uploadForm.title.trim()); if (uploadForm.device_id) body.append("device_id", uploadForm.device_id); try { await uploadContextDocument(body); window.$toast?.success("Document uploaded. Re-index when you're ready to publish it to search."); uploadForm.file = null; uploadForm.title = ""; fileInputKey.value += 1; await load(); } catch (error) { window.$toast?.error("Couldn't upload document", error); } finally { uploading.value = false; } }
function askDelete(document) { deleteTarget.value = document; }
async function removeDocument() { const document = deleteTarget.value; deleteTarget.value = null; try { const result = await deleteContextDocument(document.id); window.$toast?.success(result.detail); await load(); } catch (error) { window.$toast?.error("Couldn't remove document", error); } }
function formatBytes(bytes) { if (bytes < 1024) return `${bytes} B`; if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`; return `${(bytes / (1024 * 1024)).toFixed(1)} MB`; }
onMounted(load); onUnmounted(() => clearTimeout(pollTimer));
</script>

<style scoped>
.page-subtitle { margin: 4px 0 0; color: var(--text-secondary); }.context-stats { grid-template-columns: repeat(4, 1fr); }.stat-time { font-size: 1rem !important; min-height: 38px; display: flex; align-items: center; }.index-state { margin-bottom: 16px; border-left: 4px solid var(--color-info); }.index-state.error { border-left-color: var(--color-danger); }.index-state-row { display: flex; justify-content: space-between; margin-bottom: 9px; }.index-state p { margin: 9px 0 0; color: var(--text-secondary); font-size: 12px; }.progress-fill { background: var(--color-accent); min-width: 5%; }.context-layout { display: grid; grid-template-columns: minmax(280px, 360px) 1fr; gap: 16px; align-items: start; }.upload-card h3, .section-heading h3 { margin: 0 0 5px; }.muted { color: var(--text-secondary); font-size: 12px; }.form-label span { text-transform: none; letter-spacing: 0; }.file-input { width: 100%; font: inherit; font-size: 12px; color: var(--text-secondary); }.file-input::file-selector-button { margin-right: 10px; padding: 7px 10px; border: 1px solid var(--border-color); border-radius: var(--radius-sm); background: var(--surface-light); color: var(--text-primary); cursor: pointer; }.upload-card form .btn { width: 100%; }.reindex-note { display: flex; gap: 8px; margin: 14px 0 0; color: var(--text-secondary); font-size: 11px; line-height: 1.4; }.section-heading { display: flex; justify-content: space-between; align-items: center; }.section-heading p { margin: 0; }.documents-card > .card-body { border-bottom: 1px solid var(--border-subtle); }.document-table { border: 0; border-radius: 0; box-shadow: none; }.document-name { display: flex; flex-direction: column; max-width: 300px; }.document-name small { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.remove-button { color: var(--color-danger); }.empty-docs { padding: 50px 20px; text-align: center; color: var(--text-secondary); }.empty-docs i { font-size: 24px; }.empty-docs p { margin-bottom: 0; }
@media (max-width: 900px) { .context-stats { grid-template-columns: repeat(2, 1fr); }.context-layout { grid-template-columns: 1fr; } }
@media (max-width: 520px) { .context-stats { grid-template-columns: 1fr; } }
</style>
