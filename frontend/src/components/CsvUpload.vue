<template>
  <div class="csv-import">
    <label :for="`csv-${mode}`" class="form-label">Upload CSV</label>
    <div class="file-controls"><input :id="`csv-${mode}`" type="file" accept=".csv,text/csv" :disabled="disabled || importing" @change="selectFile" /><a :href="templateUrl" :download="`users-${mode}-template.csv`">Download template</a></div>
    <p class="muted">{{ mode === 'add' ? 'Columns: username, full_name, email, groups, shell, grant_sudo. Username can be derived from email.' : 'Use username and any fields to change: full_name, email, groups, shell, grant_sudo. Blank fields stay unchanged.' }} Set grant_sudo to true to grant passwordless sudo. False or blank keeps existing access. Upload replaces the current rows. Quote groups containing commas. Up to 500 users / 1 MB.</p>
    <p v-if="importing" role="status">Validating CSV…</p>
    <p v-else-if="imported" role="status">{{ imported }} users imported into the editable rows below. Review them before applying.</p>
    <p v-if="error" role="alert" class="callout callout-danger csv-error">{{ error }}</p>
  </div>
</template>
<script setup>
import {computed, ref, onUnmounted} from 'vue';
import {previewUsersCsv} from '../api.js';
import {csvTemplate} from '../utils/users.js';
const props = defineProps({mode:{type:String,default:'add'},disabled:Boolean});
const emit = defineEmits(['parsed','busy']);
const error = ref(''), importing = ref(false), imported = ref(0);
const templateUrl = computed(() => `data:text/csv;charset=utf-8,${encodeURIComponent(csvTemplate(props.mode))}`);
let disposed = false;
onUnmounted(() => { disposed = true; });
async function selectFile(event) {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (!file || props.disabled || importing.value) return;
  error.value = ''; imported.value = 0;
  if (!/\.csv$/i.test(file.name)) { error.value = 'Choose a .csv file.'; return; }
  if (file.size > 1024 * 1024) { error.value = 'CSV must be 1 MB or smaller.'; return; }
  importing.value = true; emit('busy', true);
  try {
    const result = await previewUsersCsv(file, props.mode);
    if (!disposed) { imported.value = result.users.length; emit('parsed', result.users); }
  } catch(e) { if (!disposed) error.value = e.message; }
  finally { if (!disposed) { importing.value = false; emit('busy', false); } }
}
</script>
<style scoped>
.csv-import { padding:16px; border:1px dashed var(--border-subtle); border-radius:6px; margin:16px 0; }.file-controls {display:flex;align-items:center;gap:12px;flex-wrap:wrap}.file-controls input{max-width:100%;font:inherit;font-size:13px}.file-controls a{font-size:13px}.muted{color:var(--text-secondary);font-size:12px;line-height:1.6;margin-top:8px}.csv-error{white-space:pre-wrap;margin-top:12px}
</style>
