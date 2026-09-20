<template>
  <div>
    <div class="page-header">
      <div><h2>Access</h2><p style="margin: 4px 0 0; color: var(--text-secondary)">Manage Linux accounts only on devices that support user provisioning.</p></div>
    </div>

    <div class="tabs">
      <button :class="['tab', { active: tab === 'add' }]" type="button" @click="tab = 'add'">Add Users</button>
      <button :class="['tab', { active: tab === 'manage' }]" type="button" @click="tab = 'manage'">Manage Users</button>
      <button :class="['tab', { active: tab === 'sudoers' }]" type="button" @click="tab = 'sudoers'">Sudoers</button>
    </div>

    <!-- Add Users Tab -->
    <div v-if="tab === 'add'">
      <div class="grid" style="gap: var(--space-md)">
        <div class="col-6 col-md-12">
          <div class="card">
            <div class="card-body">
              <h4 style="margin-bottom: var(--space-sm)">Manual Entry</h4>
              <div v-for="(u, i) in newUsers" :key="i" class="flex gap-xs" style="margin-bottom: var(--space-xs)">
                <input v-model="u.full_name" class="form-input" placeholder="Full Name" :aria-label="`Full name for row ${i + 1}`" style="flex: 1" />
                <input v-model="u.email" class="form-input" placeholder="name@example.com" :aria-label="`Email for row ${i + 1}`" style="flex: 1" />
                <button class="btn btn-ghost btn-sm btn-icon" type="button" :aria-label="`Remove row ${i + 1}`" :disabled="newUsers.length === 1" @click="newUsers.splice(i, 1)">
                  <i class="fas fa-times" aria-hidden="true"></i>
                </button>
              </div>
              <button class="btn btn-ghost btn-sm" type="button" style="margin-top: var(--space-xs)" @click="newUsers.push({ full_name: '', email: '' })">
                <i class="fas fa-plus" aria-hidden="true"></i> Add Row
              </button>
            </div>
          </div>
        </div>
        <div class="col-6 col-md-12">
          <div class="card">
            <div class="card-body">
              <h4 style="margin-bottom: var(--space-sm)">CSV Upload</h4>
              <CsvUpload @parsed="onCsvParsed" />
            </div>
          </div>
        </div>
      </div>

      <div class="card" style="margin-top: var(--space-sm)">
        <div class="card-body">
          <h4 style="margin-bottom: var(--space-sm)">Target Devices</h4>
          <div class="checkbox-group" style="margin-bottom: var(--space-sm)">
            <label class="checkbox-label" v-for="device in devices" :key="device.id">
              <input type="checkbox" :value="device.id" v-model="selectedDeviceIds" />
              {{ device.name }}
              <span :class="['badge', deviceKind(device.kind).badge]" style="font-size: 10px">{{ deviceKind(device.kind).short }}</span>
            </label>
          </div>
          <div class="flex gap-xs" style="margin-bottom: var(--space-sm)">
            <button v-for="key in availableKinds" :key="key" type="button" class="btn btn-ghost btn-sm" @click="selectGroup(key)">All {{ deviceKind(key).short }}</button>
            <button type="button" class="btn btn-ghost btn-sm" @click="selectedDeviceIds = devices.map(device => device.id)">Select All</button>
          </div>
          <div class="form-group">
            <label class="form-label" for="add-password">Initial password (optional)</label>
            <input id="add-password" v-model="addPassword" type="password" class="form-input" placeholder="Leave blank to avoid setting a password" />
          </div>
          <button class="btn btn-primary" type="button" :disabled="!canProvision" @click="provisionUsers">
            <i class="fas fa-user-plus" aria-hidden="true"></i> Provision Users
          </button>
        </div>
      </div>
    </div>

    <!-- Manage Users Tab -->
    <div v-if="tab === 'manage'">
      <div class="flex gap-xs" style="margin-bottom: var(--space-sm)">
        <label class="visually-hidden" for="user-search">Search users</label>
        <input id="user-search" v-model="search" class="form-input" placeholder="Search users…" style="max-width: 300px" />
        <button class="btn btn-ghost btn-sm" type="button" aria-label="Refresh user list" @click="loadUsers">
          <i class="fas fa-sync-alt" aria-hidden="true"></i>
        </button>
      </div>

      <div v-if="filteredUsers.length" class="table-wrapper">
        <table class="table-reflow">
          <thead>
            <tr>
              <th>Username</th>
              <th>Full Name</th>
              <th>Email</th>
              <th>Groups</th>
              <th>Sudoer</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in filteredUsers" :key="u.id">
              <td data-label="Username"><strong>{{ u.username }}</strong></td>
              <td data-label="Name">{{ u.full_name }}</td>
              <td data-label="Email">{{ u.email }}</td>
              <td data-label="Groups">{{ u.groups }}</td>
              <td data-label="Sudoer">
                <span v-if="u.is_sudoer" class="badge badge-green">sudo</span>
                <span v-else class="badge badge-outline">no</span>
              </td>
              <td data-label="Actions">
                <div class="flex gap-xs">
                  <button class="btn btn-ghost btn-sm btn-icon" type="button" :aria-label="`Change password for ${u.username}`" title="Change password" @click="openPasswordModal(u)">
                    <i class="fas fa-key" aria-hidden="true"></i>
                  </button>
                  <button class="btn btn-ghost btn-sm btn-icon" type="button" :aria-label="u.is_sudoer ? `Remove ${u.username} from sudoers` : `Add ${u.username} to sudoers`" :title="u.is_sudoer ? 'Remove sudoer' : 'Add sudoer'" @click="toggleSudoers(u)">
                    <i class="fas fa-shield-alt" aria-hidden="true"></i>
                  </button>
                  <button class="btn btn-ghost btn-sm btn-icon" type="button" :aria-label="`Remove ${u.username}`" title="Remove user" style="color: var(--color-danger)" @click="confirmRemoveUser = u">
                    <i class="fas fa-trash" aria-hidden="true"></i>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state">
        <i class="fas fa-users" aria-hidden="true"></i>
        <p>{{ search ? 'No users match your search' : 'No managed users yet' }}</p>
      </div>

      <div class="card" style="margin-top: var(--space-md)">
        <div class="card-body">
          <h4 style="margin-bottom: var(--space-xs)">Bulk Password Reset</h4>
          <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: var(--space-sm)">
            Reset passwords for all non-system users. Users must change password on next login.
          </p>
          <button class="btn btn-danger btn-sm" type="button" @click="confirmBulkReset = true">
            <i class="fas fa-redo" aria-hidden="true"></i> Bulk Reset Passwords
          </button>
        </div>
      </div>
    </div>

    <!-- Sudoers Tab -->
    <div v-if="tab === 'sudoers'">
      <div class="grid" style="gap: var(--space-md)">
        <div class="col-6 col-md-12">
          <div class="card">
            <div class="card-body">
              <h4 style="margin-bottom: var(--space-sm)">Current Sudoers</h4>
              <div v-if="sudoerUsers.length" class="table-wrapper" style="box-shadow: none">
                <table>
                  <thead>
                    <tr>
                      <th>Username</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="u in sudoerUsers" :key="u.id">
                      <td>{{ u.username }}</td>
                      <td>
                        <button class="btn btn-ghost btn-sm" type="button" style="color: var(--color-danger)" @click="handleRemoveSudoers(u.username)">Remove</button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-else style="color: var(--text-secondary); font-size: 14px">No sudoers configured</p>
            </div>
          </div>
        </div>
        <div class="col-6 col-md-12">
          <div class="card">
            <div class="card-body">
              <h4 style="margin-bottom: var(--space-sm)">Add Sudoer</h4>
              <div class="form-group">
                <label class="form-label" for="add-sudoer">Username</label>
                <select id="add-sudoer" v-model="sudoerToAdd" class="form-select">
                  <option value="">Select a user</option>
                  <option v-for="u in nonSudoerUsers" :key="u.id" :value="u.username">{{ u.username }} ({{ u.full_name }})</option>
                </select>
              </div>
              <button class="btn btn-green btn-sm" type="button" :disabled="!sudoerToAdd" @click="handleAddSudoers">
                <i class="fas fa-shield-alt" aria-hidden="true"></i> Add to Sudoers
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Password Change Modal -->
    <BaseModal :visible="!!passwordModal" :title="passwordModal ? `Change password for ${passwordModal.username}` : ''" size="sm" @cancel="passwordModal = null">
      <div class="form-group">
        <label class="form-label" for="new-password">New Password</label>
        <input id="new-password" v-model="newPassword" type="password" class="form-input" placeholder="Enter new password" />
      </div>
      <label class="checkbox-label" style="margin-bottom: var(--space-sm)">
        <input type="checkbox" v-model="forceChange" />
        Force password change on next login
      </label>
      <template #actions>
        <button class="btn btn-ghost" type="button" data-cancel @click="passwordModal = null">Cancel</button>
        <button class="btn btn-green" type="button" :disabled="!newPassword" @click="handleChangePassword">Change Password</button>
      </template>
    </BaseModal>

    <ConfirmDialog
      :visible="!!confirmRemoveUser"
      title="Remove user from all eligible devices"
      :message="confirmRemoveUser ? `This removes ${confirmRemoveUser.username} from every device that supports Linux account management. The user's home directory is preserved.` : ''"
      confirm-text="Remove user"
      :danger-mode="true"
      :require-text="confirmRemoveUser ? confirmRemoveUser.username : ''"
      @confirm="handleRemoveUser"
      @cancel="confirmRemoveUser = null"
    />

    <ConfirmDialog
      :visible="confirmBulkReset"
      title="Bulk reset all user passwords"
      message="This resets passwords for every non-system user on every eligible device. Users will be forced to change their password on next login. The temporary password is not stored in job logs."
      confirm-text="Reset all passwords"
      :danger-mode="true"
      require-text="RESET"
      @confirm="handleBulkReset"
      @cancel="closeBulkReset"
    >
      <div class="form-group">
        <label class="form-label" for="bulk-temp-password">Temporary Password</label>
        <input id="bulk-temp-password" v-model="bulkResetPassword" type="password" class="form-input" placeholder="Enter temporary password" />
      </div>
    </ConfirmDialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import {
  getUsers, getDevices, bulkAddUsers, changePassword, bulkPasswordReset,
  addSudoers, removeSudoers, removeUser,
} from "../api.js";
import CsvUpload from "../components/CsvUpload.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import BaseModal from "../components/BaseModal.vue";
import { deviceKind } from "../utils/devices.js";

const tab = ref("add");
const devices = ref([]);
const users = ref([]);
const search = ref("");
const selectedDeviceIds = ref([]);
const newUsers = ref([{ full_name: "", email: "" }]);
const csvUsers = ref([]);
const addPassword = ref("");
const passwordModal = ref(null);
const newPassword = ref("");
const forceChange = ref(false);
const confirmRemoveUser = ref(null);
const confirmBulkReset = ref(false);
const bulkResetPassword = ref("");
const sudoerToAdd = ref("");

const filteredUsers = computed(() => {
  if (!search.value) return users.value;
  const q = search.value.toLowerCase();
  return users.value.filter(
    (u) =>
      u.username.toLowerCase().includes(q) ||
      (u.full_name || "").toLowerCase().includes(q) ||
      (u.email || "").toLowerCase().includes(q)
  );
});

const sudoerUsers = computed(() => users.value.filter((u) => u.is_sudoer));
const nonSudoerUsers = computed(() => users.value.filter((u) => !u.is_sudoer));
const availableKinds = computed(() => [...new Set(devices.value.map((device) => device.kind))].sort());

const allUsersToAdd = computed(() => {
  const manual = newUsers.value.filter((u) => u.full_name && u.email);
  return csvUsers.value.length ? csvUsers.value : manual;
});

const canProvision = computed(
  () => allUsersToAdd.value.length > 0 && selectedDeviceIds.value.length > 0
);

function selectGroup(type) {
  selectedDeviceIds.value = devices.value
    .filter((device) => device.kind === type)
    .map((device) => device.id);
}

function onCsvParsed(parsed) {
  csvUsers.value = parsed;
}

async function loadUsers() {
  try {
    users.value = await getUsers();
  } catch (e) {
    window.$toast?.error("Couldn't load users", e);
  }
}

async function loadDevices() {
  try {
    devices.value = (await getDevices()).filter((device) => device.capabilities.includes("users.manage"));
  } catch (e) {
    window.$toast?.error("Couldn't load access-capable devices", e);
  }
}

async function provisionUsers() {
  try {
    const payload = {
      users: allUsersToAdd.value,
      device_ids: [...selectedDeviceIds.value].sort((a, b) => a - b),
    };
    if (addPassword.value) payload.password = addPassword.value;
    await bulkAddUsers(payload);
    window.$toast?.success(`User provisioning started; accounts appear here after the job succeeds`);
    newUsers.value = [{ full_name: "", email: "" }];
    csvUsers.value = [];
    addPassword.value = "";
    loadUsers();
  } catch (e) {
    window.$toast?.error("Couldn't start user provisioning", e);
  }
}

function openPasswordModal(user) {
  passwordModal.value = user;
  newPassword.value = "";
  forceChange.value = false;
}

async function handleChangePassword() {
  try {
    await changePassword(passwordModal.value.username, {
      all_devices: true,
      new_password: newPassword.value,
      force_change: forceChange.value,
    });
    window.$toast?.success(`Password change started for ${passwordModal.value.username}`);
    passwordModal.value = null;
  } catch (e) {
    window.$toast?.error("Couldn't change password", e);
  }
}

async function handleBulkReset() {
  confirmBulkReset.value = false;
  if (!bulkResetPassword.value) {
    window.$toast?.error("Temporary password is required");
    return;
  }
  try {
    await bulkPasswordReset({ all_devices: true, temp_password: bulkResetPassword.value });
    window.$toast?.success("Bulk password reset started");
    bulkResetPassword.value = "";
  } catch (e) {
    window.$toast?.error("Couldn't start bulk password reset", e);
  }
}

function closeBulkReset() {
  confirmBulkReset.value = false;
  bulkResetPassword.value = "";
}

async function toggleSudoers(user) {
  try {
    if (user.is_sudoer) {
      await removeSudoers(user.username, { all_devices: true });
      window.$toast?.success(`Sudo removal started for ${user.username}`);
    } else {
      await addSudoers(user.username, { all_devices: true });
      window.$toast?.success(`Sudo grant started for ${user.username}`);
    }
    loadUsers();
  } catch (e) {
    window.$toast?.error(`Couldn't update sudoers for ${user.username}`, e);
  }
}

async function handleAddSudoers() {
  try {
    await addSudoers(sudoerToAdd.value, { all_devices: true });
    window.$toast?.success(`Sudo grant started for ${sudoerToAdd.value}`);
    sudoerToAdd.value = "";
    loadUsers();
  } catch (e) {
    window.$toast?.error("Couldn't add to sudoers", e);
  }
}

async function handleRemoveSudoers(username) {
  try {
    await removeSudoers(username, { all_devices: true });
    window.$toast?.success(`Sudo removal started for ${username}`);
    loadUsers();
  } catch (e) {
    window.$toast?.error(`Couldn't remove ${username} from sudoers`, e);
  }
}

async function handleRemoveUser() {
  if (!confirmRemoveUser.value) return;
  try {
    const u = confirmRemoveUser.value;
    confirmRemoveUser.value = null;
    await removeUser(u.username, { all_devices: true, remove_home: false });
    window.$toast?.success(`Removing ${u.username} from all eligible devices`);
    loadUsers();
  } catch (e) {
    window.$toast?.error("Couldn't remove user", e);
  }
}

onMounted(() => {
  loadUsers();
  loadDevices();
});
</script>
