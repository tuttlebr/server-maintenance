import { createRouter, createWebHashHistory } from "vue-router";
import { isAuthenticated } from "./api.js";

import Login from "./views/Login.vue";
import Dashboard from "./views/Dashboard.vue";

// Heavier routes are lazy-loaded so the initial bundle stays small.
const HostDetail = () => import("./views/HostDetail.vue");
const UserManagement = () => import("./views/UserManagement.vue");
const DriverManagement = () => import("./views/DriverManagement.vue");
const Networking = () => import("./views/Networking.vue");
const Maintenance = () => import("./views/Maintenance.vue");
const JobHistory = () => import("./views/JobHistory.vue");

const routes = [
  { path: "/login", component: Login, meta: { public: true } },
  { path: "/", component: Dashboard },
  { path: "/hosts/:hostname", component: HostDetail, props: true },
  { path: "/users", component: UserManagement },
  { path: "/drivers", component: DriverManagement },
  { path: "/networking", component: Networking },
  { path: "/maintenance", component: Maintenance },
  { path: "/jobs", component: JobHistory },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

router.beforeEach((to) => {
  if (!to.meta.public && !isAuthenticated()) {
    return "/login";
  }
});

export default router;
