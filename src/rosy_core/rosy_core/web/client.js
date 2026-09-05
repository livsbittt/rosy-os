// 세션과 인증된 fetch. 토큰이 사는 유일한 곳이다.

import { elements } from "./dom.js";

export const session = {
  token: sessionStorage.getItem("rosy.dashboard.token") || "",
  socket: null,
  fallbackTimer: null,
  refreshTimer: null,
  capabilities: null,
  robotState: null,
  waypoints: [],
  docks: [],
  dockingSupported: false,
  role: "",
  modeChangePending: false,
  teleopTimer: null,
  teleopActive: false,
  teleopPending: null,
  teleopIntervalMs: 100,
  networkHistory: { rx: [], tx: [] },
};

export const authHeaders = () => ({
  "Content-Type": "application/json",
  Authorization: `Bearer ${session.token}`,
});

export function setConnection(kind, label) {
  const badge = elements["connection-badge"];
  badge.className = `status-badge status-${kind}`;
  badge.querySelector("span").textContent = label;
}

export async function api(path, options = {}) {
  if (!session.token) throw new Error("접속 키가 필요합니다.");
  const response = await fetch(path, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body.error?.message || body.detail || message;
    } catch (_error) {
      // The HTTP status remains the safest fallback.
    }
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

export async function apiMaybe(path) {
  if (!session.token) return null;
  const response = await fetch(path, { headers: authHeaders() });
  if (response.status === 404) return null;
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body.error?.message || message;
    } catch (_error) {
      // Keep the status text.
    }
    throw new Error(message);
  }
  return response.json();
}

export function isAdmin() {
  return session.role === "administrator";
}
