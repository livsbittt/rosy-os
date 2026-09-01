const elements = Object.fromEntries(
  [...document.querySelectorAll("[id]")].map((element) => [element.id, element]),
);

const session = {
  token: sessionStorage.getItem("rosy.dashboard.token") || "",
  socket: null,
  fallbackTimer: null,
  refreshTimer: null,
  capabilities: null,
  modeChangePending: false,
};

const authHeaders = () => ({
  "Content-Type": "application/json",
  Authorization: `Bearer ${session.token}`,
});

function setText(id, value, fallback = "—") {
  if (elements[id]) elements[id].textContent = value ?? fallback;
}

function number(value, digits = 1) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "—";
}

function percent(value) {
  return Number.isFinite(Number(value)) ? `${Math.round(Number(value))}%` : "—";
}

function bytes(value) {
  if (!Number.isFinite(Number(value))) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = Number(value);
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(unit > 2 ? 1 : 0)} ${units[unit]}`;
}

function duration(value) {
  if (!Number.isFinite(Number(value))) return "—";
  const total = Math.floor(Number(value));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  return `${days}일 ${hours}시간 ${minutes}분`;
}

function setMeter(id, value) {
  const safe = Number.isFinite(Number(value)) ? Math.max(0, Math.min(100, Number(value))) : 0;
  elements[id]?.style.setProperty("--meter", `${safe}%`);
}

function setConnection(kind, label) {
  const badge = elements["connection-badge"];
  badge.className = `status-badge status-${kind}`;
  badge.querySelector("span").textContent = label;
}

async function api(path, options = {}) {
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

function renderRobotInfo(info) {
  setText("robot-name", info.name || "Rosy");
  setText("robot-id", `${info.robot_id || "—"} / ${info.hardware_model || "unknown model"}`);
}

function renderRobotState(state) {
  setText("robot-id", state.robot_id || "—");
  setText("robot-mode", state.mode);
  setText("state-sequence", `SEQ ${state.seq ?? "—"}`);
  setText("pose-x", number(state.pose?.x, 3));
  setText("pose-y", number(state.pose?.y, 3));
  setText("pose-yaw", number(state.pose?.yaw, 3));
  setText("velocity-linear", number(state.velocity?.linear, 3));
  setText("velocity-angular", number(state.velocity?.angular, 3));
  setText("battery-value", percent(state.battery?.percent));
  setText("battery-voltage", Number.isFinite(Number(state.battery?.voltage)) ? `${number(state.battery.voltage, 2)} V` : "voltage —");
  setText("navigation-state", state.navigation);
  setText("map-id", `map ${state.map_id || "—"}`);
  setText("state-age", state.timestamp ? new Date(state.timestamp).toLocaleTimeString("ko-KR") : "—");
  setText("hero-message", state.online === false ? "로봇이 오프라인 상태를 보고했습니다." : "로봇 런타임과 상태 스트림이 연결되었습니다.");

  document.querySelectorAll("[data-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === state.mode);
  });

  const stopped = Boolean(state.safety?.estop);
  elements["safety-indicator"].className = `hero-safety ${stopped ? "danger" : "safe"}`;
  setText("safety-label", stopped ? "STOPPED" : "READY");
  setText("safety-source", stopped ? "비상정지 활성" : "주행 회로 정상");
  setConnection("online", "상태 스트림 연결");
  setText("last-sync", `마지막 동기화 ${new Date().toLocaleTimeString("ko-KR")}`);
}

function renderSafety(safety) {
  const stopped = Boolean(safety.estop);
  elements["safety-indicator"].className = `hero-safety ${stopped ? "danger" : "safe"}`;
  setText("safety-label", stopped ? "STOPPED" : "READY");
  setText("safety-source", safety.source || (stopped ? "source unknown" : "주행 회로 정상"));
}

function renderRuntime(runtime) {
  setText("host-name", runtime.hostname);
  setText("os-name", runtime.os?.pretty_name || runtime.os?.name);
  setText("kernel-name", [runtime.kernel, runtime.architecture].filter(Boolean).join(" / "));
  setText("network-address", runtime.network?.addresses?.join(", "));
  setText("uptime", duration(runtime.uptime_seconds));

  setText("cpu-value", percent(runtime.cpu?.usage_percent));
  setText("cpu-detail", `load ${number(runtime.cpu?.load_1, 2)} / ${runtime.cpu?.logical_count ?? "—"} cores`);
  setMeter("cpu-bar", runtime.cpu?.usage_percent);

  setText("memory-value", percent(runtime.memory?.used_percent));
  setText("memory-detail", `${bytes(runtime.memory?.available_bytes)} available`);
  setMeter("memory-bar", runtime.memory?.used_percent);

  setText("storage-value", percent(runtime.storage?.used_percent));
  setText("storage-detail", `${bytes(runtime.storage?.free_bytes)} free · ${runtime.storage?.path || "—"}`);
  setMeter("storage-bar", runtime.storage?.used_percent);

  const temperature = runtime.temperature_c;
  setText("temperature", Number.isFinite(Number(temperature)) ? `${number(temperature, 1)}°` : null);
  setText("temperature-state", temperature == null ? "센서 없음" : temperature >= 80 ? "고온 경고" : temperature >= 70 ? "주의" : "정상 범위");
  setText("runtime-warning", runtime.unavailable?.length ? `읽을 수 없는 항목: ${runtime.unavailable.join(", ")}` : "");
}

function flattenCapabilities(value, prefix = "") {
  const rows = [];
  Object.entries(value || {}).forEach(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (item && typeof item === "object" && !Array.isArray(item)) {
      rows.push(...flattenCapabilities(item, path));
    } else {
      rows.push([path, Boolean(item)]);
    }
  });
  return rows;
}

function renderCapabilities(capabilities) {
  session.capabilities = capabilities;
  const rows = flattenCapabilities(capabilities);
  elements["capability-list"].replaceChildren();
  rows.forEach(([name, enabled]) => {
    const row = document.createElement("div");
    row.className = "capability-item";
    const label = document.createElement("span");
    label.textContent = name;
    const state = document.createElement("b");
    state.className = enabled ? "enabled" : "disabled";
    state.textContent = enabled ? "AVAILABLE" : "DISABLED";
    row.append(label, state);
    elements["capability-list"].append(row);
  });
  setText("capability-count", `${rows.filter((row) => row[1]).length} / ${rows.length} ON`);
  updateModeButtons();
}

function updateModeButtons() {
  const navigationAvailable = session.capabilities?.navigation?.goal_navigation === true;
  document.querySelectorAll("[data-mode]").forEach((button) => {
    const unsupported = button.dataset.mode === "NAVIGATION" && !navigationAvailable;
    button.disabled = session.modeChangePending || unsupported;
    button.title = unsupported ? "이 프로필에서는 내비게이션이 비활성화되어 있습니다." : "";
  });
}

function renderEvents(payload) {
  const events = [...(payload.events || [])].reverse().slice(0, 10);
  elements["event-list"].replaceChildren();
  if (!events.length) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "수신된 이벤트가 없습니다.";
    elements["event-list"].append(empty);
    return;
  }
  events.forEach((event) => {
    const row = document.createElement("li");
    const time = document.createElement("time");
    time.className = "event-time";
    time.textContent = event.ts ? new Date(event.ts).toLocaleTimeString("ko-KR") : "—";
    const type = document.createElement("span");
    type.className = "event-type";
    type.textContent = event.type || "unknown.event";
    const severity = document.createElement("span");
    severity.className = `event-severity ${event.severity || "info"}`;
    severity.textContent = (event.severity || "info").toUpperCase();
    row.append(time, type, severity);
    elements["event-list"].append(row);
  });
}

async function refreshSlowData() {
  const requests = await Promise.allSettled([
    api("/api/v1/system/runtime"),
    api("/api/v1/system/info"),
    api("/api/v1/system/capabilities"),
    api("/api/v1/safety/state"),
    api("/api/v1/events?limit=10"),
  ]);
  const renderers = [renderRuntime, renderRobotInfo, renderCapabilities, renderSafety, renderEvents];
  requests.forEach((result, index) => {
    if (result.status === "fulfilled") renderers[index](result.value);
  });
  const failed = requests.find((result) => result.status === "rejected");
  if (failed) throw failed.reason;
}

async function refreshRobotState() {
  renderRobotState(await api("/api/v1/robot/state"));
}

function connectStateSocket() {
  session.socket?.close();
  clearInterval(session.fallbackTimer);
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const url = `${scheme}://${window.location.host}/ws/state?token=${encodeURIComponent(session.token)}`;
  const socket = new WebSocket(url);
  session.socket = socket;
  socket.addEventListener("open", () => setConnection("online", "상태 스트림 연결"));
  socket.addEventListener("message", (event) => {
    try { renderRobotState(JSON.parse(event.data)); } catch (_error) { setConnection("error", "상태 해석 실패"); }
  });
  socket.addEventListener("close", () => {
    if (socket !== session.socket || !session.token) return;
    setConnection("error", "REST 폴링 전환");
    session.fallbackTimer = setInterval(() => refreshRobotState().catch(showConnectionError), 2000);
  });
}

function showConnectionError(error) {
  setConnection("error", "연결 확인 필요");
  setText("hero-message", error.message || "Rosy API에 연결할 수 없습니다.");
}

async function connect() {
  setConnection("unknown", "연결 중");
  await Promise.all([refreshRobotState(), refreshSlowData()]);
  connectStateSocket();
  clearInterval(session.refreshTimer);
  session.refreshTimer = setInterval(() => refreshSlowData().catch(showConnectionError), 5000);
  elements["auth-drawer"].classList.remove("open");
}

elements["auth-form"].addEventListener("submit", async (event) => {
  event.preventDefault();
  session.token = elements["token-input"].value.trim();
  sessionStorage.setItem("rosy.dashboard.token", session.token);
  setText("auth-message", "연결 확인 중…");
  try {
    await connect();
    setText("auth-message", "연결되었습니다.");
  } catch (error) {
    sessionStorage.removeItem("rosy.dashboard.token");
    session.token = "";
    setText("auth-message", error.message);
    showConnectionError(error);
  }
});

elements["open-auth"].addEventListener("click", () => elements["auth-drawer"].classList.add("open"));
elements["close-auth"].addEventListener("click", () => elements["auth-drawer"].classList.remove("open"));
elements["refresh-events"].addEventListener("click", () => api("/api/v1/events?limit=10").then(renderEvents).catch(showConnectionError));

document.querySelectorAll("[data-mode]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (button.disabled || session.modeChangePending) return;
    const requestedMode = button.dataset.mode;
    if (!window.confirm(`${requestedMode} 모드로 변경할까요? 주변 안전을 확인하세요.`)) return;
    session.modeChangePending = true;
    updateModeButtons();
    try {
      await api("/api/v1/mode", { method: "POST", body: JSON.stringify({ mode: requestedMode }) });
      setText("action-message", `${requestedMode} 모드 요청을 전송했습니다.`);
      await refreshRobotState();
    } catch (error) {
      setText("action-message", `모드 변경 실패: ${error.message}`);
    } finally {
      session.modeChangePending = false;
      updateModeButtons();
    }
  });
});

elements["emergency-stop"].addEventListener("click", async () => {
  if (!window.confirm("Rosy를 즉시 정지할까요?")) return;
  try {
    await api("/api/v1/safety/stop", { method: "POST" });
    setText("action-message", "비상정지가 활성화되었습니다.");
    await refreshRobotState();
  } catch (error) {
    setText("action-message", `정지 명령 실패: ${error.message}`);
  }
});

elements["release-stop"].addEventListener("click", async () => {
  if (!window.confirm("주변 안전을 확인했고 정지를 해제할까요?")) return;
  try {
    await api("/api/v1/safety/release", { method: "POST" });
    setText("action-message", "비상정지가 해제되었습니다.");
    await refreshRobotState();
  } catch (error) {
    setText("action-message", `정지 해제 실패: ${error.message}`);
  }
});

setInterval(() => setText("clock", new Date().toLocaleTimeString("ko-KR", { hour12: false })), 1000);
setText("clock", new Date().toLocaleTimeString("ko-KR", { hour12: false }));

if (session.token) {
  elements["token-input"].value = session.token;
  connect().catch((error) => {
    showConnectionError(error);
    elements["auth-drawer"].classList.add("open");
  });
} else {
  elements["auth-drawer"].classList.add("open");
}
