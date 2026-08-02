<template>
  <div
    class="upload-zone"
    :class="{ dragover }"
    @dragover.prevent="dragover = true"
    @dragleave="dragover = false"
    @drop.prevent="onDrop"
    @click="$refs.fileInput.click()"
  >
    <i class="fas fa-cloud-upload-alt"></i>
    <p>Drag and drop a CSV file here, or click to browse</p>
    <p style="font-size: 12px; margin-top: 4px">Columns: full_name, email</p>
    <input
      ref="fileInput"
      type="file"
      accept=".csv"
      style="display: none"
      @change="onFileSelect"
    />
  </div>

  <div v-if="parsedUsers.length" class="csv-preview">
    <h4 style="margin: var(--space-sm) 0 var(--space-xs)">
      Preview ({{ parsedUsers.length }} users)
    </h4>
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Full Name</th>
            <th>Email</th>
            <th>Username</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(u, i) in parsedUsers" :key="i">
            <td>{{ u.full_name }}</td>
            <td>{{ u.email }}</td>
            <td>{{ u.email.split('@')[0] }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

const emit = defineEmits(["parsed"]);

const dragover = ref(false);
const parsedUsers = ref([]);

function parseCSV(text) {
  const lines = text.trim().split("\n");
  if (lines.length === 0) return [];

  const firstLine = lines[0].toLowerCase();
  const hasHeader =
    firstLine.includes("name") || firstLine.includes("email");
  const dataLines = hasHeader ? lines.slice(1) : lines;

  const users = [];
  for (const line of dataLines) {
    const parts = line.split(",").map((s) => s.trim().replace(/^"|"$/g, ""));
    if (parts.length >= 2 && parts[0] && parts[1]) {
      users.push({ full_name: parts[0], email: parts[1] });
    }
  }
  return users;
}

function handleFile(file) {
  if (!file || !file.name.endsWith(".csv")) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const users = parseCSV(e.target.result);
    parsedUsers.value = users;
    emit("parsed", users);
  };
  reader.readAsText(file);
}

function onDrop(e) {
  dragover.value = false;
  const file = e.dataTransfer.files[0];
  handleFile(file);
}

function onFileSelect(e) {
  const file = e.target.files[0];
  handleFile(file);
}
</script>

<style scoped>
.csv-preview {
  margin-top: var(--space-sm);
}
</style>
