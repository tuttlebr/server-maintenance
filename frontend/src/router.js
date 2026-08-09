import { createRouter, createWebHashHistory } from "vue-router";
import { isAuthenticated } from "./api.js";

import Login from "./views/Login.vue";
import Dashboard from "./views/Dashboard.vue";

const Devices = () => import("./views/Devices.vue");
const DeviceDetail = () => import("./views/DeviceDetail.vue");
const Operations = () => import("./views/Operations.vue");
const UserManagement = () => import("./views/UserManagement.vue");
const JobHistory = () => import("./views/JobHistory.vue");
const ContextManagement = () => import("./views/ContextManagement.vue");

const routes = [
  { path: "/login", component: Login, meta: { public: true } },
  { path: "/", component: Dashboard },
  { path: "/devices", component: Devices },
  { path: "/devices/:id", component: DeviceDetail, props: true },
  { path: "/operations", component: Operations },
  { path: "/access", component: UserManagement },
  { path: "/activity", component: JobHistory },
  { path: "/context", component: ContextManagement },
];

const router = createRouter({ history: createWebHashHistory(), routes });

router.beforeEach((to) => {
  if (!to.meta.public && !isAuthenticated()) return "/login";
});

export default router;
