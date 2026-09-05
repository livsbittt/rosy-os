import { createFieldMap } from "./map.js";
import {
  bindFormSave,
  bytes,
  duration,
  elements,
  metricNumber,
  number,
  percent,
  rate,
  setEnabled,
  setFieldMessage,
  setMeter,
  setText,
  svgText,
} from "./dom.js";
import { api, apiMaybe, authHeaders, isAdmin, session, setConnection } from "./client.js";
import {
  fillIdentityForm,
  fillSafetyForm,
  initSettings,
  refreshDocks,
  refreshTokens,
  refreshWaypoints,
  renderDockingStatus,
  renderDocks,
  renderTokens,
  renderWaypoints,
} from "./settings.js";

const fieldMap = createFieldMap({
  canvas: elements["map-canvas"],
  empty: elements["map-empty"],
  status: elements["map-status"],
  layerRoot: document.getElementById("field-map-panel"),
  api,
  apiMaybe,
  getPose: () => session.robotState?.pose,
  getNavigation: () => session.robotState?.navigation,
  canGoal: () => session.capabilities?.navigation?.goal_navigation === true,
  setAction: (text) => setText("action-message", text),
});

function renderRobotInfo(info) {
  const name = info.robot_name || info.name || "Rosy";
  setText("robot-name", name);
  setText("robot-id", `${info.robot_id || "—"} / ${info.hardware_model || "unknown model"} / ${info.runtime_mode || "core"}`);
  fillIdentityForm(info.robot_id, name);
}

function renderRobotState(state) {
  session.robotState = state;
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
  if (session.teleopActive && !teleopEligible()) stopTeleop("운전 조건이 변경되어 정지했습니다.");
  updateTeleopControls();
  fieldMap.setPose();
}

function renderSafety(safety) {
  session.robotState = {
    ...(session.robotState || {}),
    safety: { ...(session.robotState?.safety || {}), estop: Boolean(safety.estop) },
  };
  const stopped = Boolean(safety.estop);
  elements["safety-indicator"].className = `hero-safety ${stopped ? "danger" : "safe"}`;
  setText("safety-label", stopped ? "STOPPED" : "READY");
  setText("safety-source", safety.source || (stopped ? "source unknown" : "주행 회로 정상"));
  fillSafetyForm(safety);
  updateTeleopControls();
  updateTeleopControls();
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
  renderRosNetwork(runtime);
}


function pushNetworkSample(series, value) {
  const amount = metricNumber(value);
  if (amount === null) return;
  series.push(amount);
  if (series.length > 30) series.splice(0, series.length - 30);
}

function renderSparkline(id, values) {
  const svg = elements[id];
  if (!svg) return;
  svg.replaceChildren();
  if (!values.length) return;
  const width = 120;
  const height = 36;
  const peak = Math.max(...values, 1);
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const points = values.map((value, index) => (
    `${(index * step).toFixed(2)},${(height - (value / peak) * (height - 4) - 2).toFixed(2)}`
  )).join(" ");
  const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  line.setAttribute("points", points);
  line.setAttribute("vector-effect", "non-scaling-stroke");
  svg.append(line);
}


function renderRosGraph(graph) {
  const svg = elements["ros-graph-map"];
  if (!svg) return;
  svg.replaceChildren();
  const nodes = (graph.nodes || []).slice(0, 12);
  const topics = (graph.topics || []).slice(0, 12);
  if (!nodes.length && !topics.length) {
    svg.append(svgText("ROS 그래프 데이터 없음", 400, 164, "graph-empty"));
    return;
  }

  const nodePositions = new Map();
  const topicPositions = new Map();
  const positionRows = (items, x) => items.map((item, index) => ({
    item,
    x,
    y: ((index + 1) * 300) / (items.length + 1) + 10,
  }));
  const nodeRows = positionRows(nodes, 150);
  const topicRows = positionRows(topics, 650);
  nodeRows.forEach(({ item, x, y }) => nodePositions.set(item.name, { x, y }));
  topicRows.forEach(({ item, x, y }) => topicPositions.set(item.name, { x, y }));

  (graph.edges || []).slice(0, 48).forEach((edge) => {
    const start = nodePositions.get(edge.source) || topicPositions.get(edge.source);
    const end = nodePositions.get(edge.target) || topicPositions.get(edge.target);
    if (!start || !end) return;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", start.x);
    line.setAttribute("y1", start.y);
    line.setAttribute("x2", end.x);
    line.setAttribute("y2", end.y);
    line.setAttribute("class", `graph-edge ${edge.kind}`);
    svg.append(line);
  });

  nodeRows.forEach(({ item, x, y }) => {
    const marker = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    marker.setAttribute("x", x - 108);
    marker.setAttribute("y", y - 13);
    marker.setAttribute("width", 216);
    marker.setAttribute("height", 26);
    marker.setAttribute("rx", 3);
    marker.setAttribute("class", `graph-node${item.foreign ? " foreign" : ""}`);
    svg.append(marker, svgText(item.name, x, y + 4, "graph-node-label"));
  });
  topicRows.forEach(({ item, x, y }) => {
    const marker = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    marker.setAttribute("cx", x);
    marker.setAttribute("cy", y);
    marker.setAttribute("r", 8);
    marker.setAttribute("class", "graph-topic");
    svg.append(marker, svgText(item.name, x - 14, y - 14, "graph-topic-label"));
  });
}

function renderRosNetwork(runtime) {
  const graph = runtime.ros || {};
  const throughput = runtime.network?.throughput || {};
  const status = graph.status || "UNAVAILABLE";
  setText("ros-graph-status", status);
  elements["ros-graph-status"]?.setAttribute("data-status", status);
  setText("ros-domain-id", graph.domain_id);
  setText("ros-namespace", graph.namespace);
  const isolationLabels = {
    localhost_only: "LOOPBACK ONLY",
    network_visible: "NETWORK VISIBLE",
    unknown: "UNKNOWN",
  };
  setText("dds-isolation", isolationLabels[graph.isolation?.mode] || "—");
  setText("dds-interface", graph.isolation?.interface ? `interface ${graph.isolation.interface}` : "인터페이스 확인 불가");
  setText("ros-node-count", graph.node_count);
  setText("ros-topic-count", graph.topic_count);
  setText("network-rx-rate", rate(throughput.rx_bytes_per_second));
  setText("network-tx-rate", rate(throughput.tx_bytes_per_second));

  pushNetworkSample(session.networkHistory.rx, throughput.rx_bytes_per_second);
  pushNetworkSample(session.networkHistory.tx, throughput.tx_bytes_per_second);
  renderSparkline("network-sparkline-rx", session.networkHistory.rx);
  renderSparkline("network-sparkline-tx", session.networkHistory.tx);
  renderRosGraph(graph);

  const riskList = elements["ros-risk-list"];
  if (!riskList) return;
  riskList.replaceChildren();
  const risks = graph.risks || [];
  if (status === "UNAVAILABLE") {
    const item = document.createElement("li");
    item.className = "risk-unavailable";
    item.textContent = "ROS 그래프 수집 불가 — 충돌 상태를 확인할 수 없습니다.";
    riskList.append(item);
    return;
  }
  if (!risks.length) {
    const item = document.createElement("li");
    item.className = "risk-clear";
    item.textContent = "감지된 충돌 지표 없음";
    riskList.append(item);
    return;
  }
  risks.forEach((risk) => {
    const item = document.createElement("li");
    const code = document.createElement("strong");
    const message = document.createElement("span");
    code.textContent = risk.code || "UNKNOWN";
    message.textContent = risk.message || "상세 정보 없음";
    item.append(code, message);
    riskList.append(item);
  });
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
  const slamOn = capabilities?.slam === true;
  const slamChip = elements["slam-capability"];
  if (slamChip) {
    slamChip.dataset.mode = slamOn ? "AVAILABLE" : "HOLD";
    slamChip.textContent = slamOn ? "AVAILABLE" : "HOLD";
  }
  setEnabled("slam-start", slamOn);
  setEnabled("slam-stop", slamOn);
  setEnabled("slam-save", slamOn);
  updateModeButtons();
  updateTeleopControls();
}

function teleopEligible() {
  return Boolean(
    session.token
    && session.capabilities?.teleop === true
    && session.robotState?.mode === "MANUAL"
    && session.robotState?.safety?.estop !== true
    && elements["bench-safety-confirmed"]?.checked,
  );
}

function updateTeleopControls() {
  const enabled = teleopEligible();
  document.querySelectorAll("[data-teleop]").forEach((button) => {
    button.disabled = !enabled;
  });
  if (!session.token) {
    setText("teleop-message", "operator 접속 키가 필요합니다.");
  } else if (session.capabilities && session.capabilities.teleop !== true) {
    setText("teleop-message", "현재 하드웨어 프로필에서 teleop을 사용할 수 없습니다.");
  } else if (session.robotState?.safety?.estop) {
    setText("teleop-message", "비상정지가 활성화되어 있습니다.");
  } else if (session.robotState?.mode !== "MANUAL") {
    setText("teleop-message", "MANUAL 모드로 전환해야 합니다.");
  } else if (!elements["bench-safety-confirmed"]?.checked) {
    setText("teleop-message", "벤치 안전 확인이 필요합니다.");
  } else if (!session.teleopActive) {
    setText("teleop-message", "버튼을 누르고 있는 동안만 저속 명령을 보냅니다.");
  }
}

function sendTeleop(linear, angular, keepalive = false) {
  return api("/api/v1/teleop", {
    method: "POST",
    body: JSON.stringify({ linear, angular }),
    keepalive,
  });
}

function queueTerminalZero(immediate = false) {
  const prior = session.teleopPending || Promise.resolve();
  if (immediate) {
    const immediateZero = sendTeleop(0, 0, true);
    immediateZero.catch(() => null);
  }
  const terminal = prior
    .catch(() => null)
    .then(() => sendTeleop(0, 0, true));
  session.teleopPending = terminal;
  terminal
    .catch((error) => {
      setText("teleop-message", `정지 전송 실패 · watchdog 대기: ${error.message}`);
    })
    .finally(() => {
      if (session.teleopPending === terminal) session.teleopPending = null;
    });
}

function stopTeleop(message = "정지 명령을 전송했습니다.", immediate = false) {
  const wasActive = session.teleopActive;
  session.teleopActive = false;
  clearInterval(session.teleopTimer);
  session.teleopTimer = null;
  document.querySelectorAll("[data-teleop]").forEach((button) => button.classList.remove("active"));
  if (wasActive && session.token) {
    queueTerminalZero(immediate);
  }
  setText("teleop-message", message);
  updateTeleopControls();
}

async function transmitTeleop(linear, angular) {
  if (!session.teleopActive || session.teleopPending) return;
  const request = sendTeleop(linear, angular);
  session.teleopPending = request;
  try {
    await request;
  } catch (error) {
    if (session.teleopActive) stopTeleop(`주행 명령 실패: ${error.message}`);
  } finally {
    if (session.teleopPending === request) session.teleopPending = null;
  }
}

function startTeleop(button, event) {
  event.preventDefault();
  if (!teleopEligible() || session.teleopActive) return;
  const linear = Number(button.dataset.linear);
  const angular = Number(button.dataset.angular);
  if (!Number.isFinite(linear) || !Number.isFinite(angular)) return;

  session.teleopActive = true;
  button.classList.add("active");
  setText("teleop-message", `${button.querySelector("small")?.textContent || "주행"} 명령 전송 중…`);
  const transmit = () => transmitTeleop(linear, angular);
  transmit();
  session.teleopTimer = setInterval(transmit, session.teleopIntervalMs);
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


// --- Device Runtime cards (WP-5) -------------------------------------------
//
// The rule these three share: when the Host Agent did not answer, say so.
// Filling the fields with em dashes would render an unreachable agent and a
// healthy device identically, and an operator reads an empty field as "fine".

function setCardUnavailable(cardId, noteId, payload) {
  const card = document.getElementById(cardId);
  if (card) card.dataset.available = "false";
  const note = document.getElementById(noteId);
  if (note) {
    const recovery = payload.recovery ? ` ${payload.recovery}` : "";
    note.textContent = `${payload.detail || "정보를 가져올 수 없습니다."}${recovery}`;
  }
}

function setChip(id, value) {
  const chip = document.getElementById(id);
  if (!chip) return;
  const mode = value || "UNKNOWN";
  chip.dataset.mode = mode;
  chip.textContent = mode === "UNKNOWN" ? "—" : mode;
}

function renderHostNetwork(payload) {
  const status = document.getElementById("host-agent-status");
  if (status) {
    status.dataset.status = payload.available ? "OK" : "UNAVAILABLE";
    status.textContent = payload.available ? "Host Agent 연결됨" : "Host Agent 없음";
  }

  if (!payload.available) {
    setChip("network-mode", "UNKNOWN");
    setCardUnavailable("network-card", "network-note", payload);
    setEnabled("network-apply", false);
    return;
  }

  const card = document.getElementById("network-card");
  if (card) card.dataset.available = "true";

  const data = payload.data || {};
  setChip("network-mode", data.mode);
  // The SSID is displayable; a PSK never is, and the agent does not send one.
  setText("network-ssid", data.ssid || "—");
  setText("network-ipv4", data.ipv4 || "—");
  setText("network-route", data.default_route || "—");
  setText("network-dns", (data.dns || []).join(", ") || "—");
  setText("network-internet", data.internet ? "도달" : "도달 못함");
  setText("network-peer", data.peer_reachable ? "가능" : "확인 필요");

  const note = document.getElementById("network-note");
  if (note) {
    // Internet and peer reachability fail separately: a router with client
    // isolation gives you the internet and no dashboard.
    note.textContent = data.internet && !data.peer_reachable
      ? "인터넷은 되지만 같은 WLAN 단말에서 접근되지 않습니다. 공유기의 client isolation 설정을 확인하십시오."
      : (payload.detail || "");
  }
  const profile = elements["network-profile-id"];
  if (profile && document.activeElement !== profile) {
    profile.value = data.profile_id || data.mode || profile.value || "rosy-site-sta";
  }
  setEnabled("network-apply", isAdmin() && payload.available === true);
}

function renderHostRelease(payload) {
  if (!payload.available) {
    setChip("release-state", "UNKNOWN");
    setCardUnavailable("release-card", "release-note", payload);
    setActionsEnabled(false);
    return;
  }

  const card = document.getElementById("release-card");
  if (card) card.dataset.available = "true";

  const data = payload.data || {};
  setChip("release-state", data.state);
  setText("release-current", data.current || "—");
  setText("release-previous", data.previous || "없음");
  setText("release-staged", data.staged || "없음");
  setText("release-revision", (data.git_revision || "").slice(0, 12) || "—");
  setText(
    "release-schema",
    data.config_schema != null ? `${data.config_schema} / ${data.data_schema}` : "—",
  );
  setText("release-failure", data.last_failure || "없음");

  const note = document.getElementById("release-note");
  if (note) note.textContent = data.detail || payload.detail || "";

  // Rollback needs somewhere to go; clearing a hold needs a hold.
  const held = data.state === "RECOVERY_HOLD";
  setEnabled("release-rollback", session.role === "administrator" && Boolean(data.previous) && !held);
  setEnabled("release-clear-hold", session.role === "administrator" && held);
}

function renderCommissioning(payload) {
  setChip("commissioning-mode", payload.runtime_mode);
  const note = document.getElementById("commissioning-note");
  if (note) {
    const holds = [
      payload.motor_hold ? "MOTOR_HOLD" : null,
      payload.lidar_hold ? "LIDAR_HOLD" : null,
      payload.battery_hold ? "BATTERY_HOLD" : null,
      payload.imu_hold ? "IMU_HOLD" : null,
      payload.slam_hold ? "SLAM_HOLD" : null,
      payload.fleet_hold ? "FLEET_HOLD" : null,
    ].filter(Boolean);
    const holdText = holds.length ? `${holds.join(" · ")}. ` : "";
    note.textContent = `${holdText}${payload.detail || ""}`;
  }
}


function setActionsEnabled(enabled) {
  setEnabled("release-rollback", enabled);
  setEnabled("release-clear-hold", enabled);
}


function updateAdminControls() {
  setEnabled("limits-save", isAdmin());
  setEnabled("dock-register", isAdmin());
  setEnabled("identity-save", isAdmin());
  setEnabled("token-add", isAdmin());
  const networkCard = document.getElementById("network-card");
  setEnabled("network-apply", isAdmin() && networkCard?.dataset.available === "true");
}

async function detectRole() {
  session.role = "";
  try {
    const response = await fetch("/api/v1/logs/audit?limit=1", { headers: authHeaders() });
    if (response.status === 200) session.role = "administrator";
    else if (response.status !== 401) session.role = "operator";
  } catch (_error) {
    session.role = "";
  }
  updateAdminControls();
}

async function refreshSlowData() {
  const required = [
    [api("/api/v1/system/runtime"), renderRuntime],
    [api("/api/v1/system/info"), renderRobotInfo],
    [api("/api/v1/system/capabilities"), renderCapabilities],
    [api("/api/v1/safety/state"), renderSafety],
    [api("/api/v1/events?limit=10"), renderEvents],
    [api("/api/v1/host/network"), renderHostNetwork],
    [api("/api/v1/host/release"), renderHostRelease],
    [api("/api/v1/host/commissioning"), renderCommissioning],
  ];
  const optional = [
    [api("/api/v1/waypoints"), renderWaypoints],
    [api("/api/v1/docking/status"), renderDockingStatus],
    [api("/api/v1/docking/docks"), renderDocks],
    [isAdmin() ? api("/api/v1/system/tokens") : Promise.resolve({tokens: []}), renderTokens],
    [fieldMap.refresh(), () => {}],
  ];
  const [requiredResults, optionalResults] = await Promise.all([
    Promise.allSettled(required.map((item) => item[0])),
    Promise.allSettled(optional.map((item) => item[0])),
  ]);
  requiredResults.forEach((result, index) => {
    if (result.status === "fulfilled") required[index][1](result.value);
  });
  optionalResults.forEach((result, index) => {
    if (result.status === "fulfilled") optional[index][1](result.value);
  });
  const failed = requiredResults.find((result) => result.status === "rejected");
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
  stopTeleop("연결 오류로 정지했습니다.");
  setConnection("error", "연결 확인 필요");
  setText("hero-message", error.message || "Rosy API에 연결할 수 없습니다.");
}

async function connect() {
  setConnection("unknown", "연결 중");
  await detectRole();
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
    stopTeleop("모드 변경 전에 정지했습니다.");
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

document.querySelectorAll("[data-teleop]").forEach((button) => {
  button.addEventListener("pointerdown", (event) => startTeleop(button, event));
  button.addEventListener("pointerup", () => stopTeleop());
  button.addEventListener("pointercancel", () => stopTeleop("포인터 취소로 정지했습니다."));
  button.addEventListener("pointerleave", () => stopTeleop("버튼 이탈로 정지했습니다."));
  button.addEventListener("contextmenu", (event) => event.preventDefault());
});

elements["bench-safety-confirmed"].addEventListener("change", () => {
  if (!elements["bench-safety-confirmed"].checked) stopTeleop("안전 확인이 해제되어 정지했습니다.");
  updateTeleopControls();
});
window.addEventListener("pointerup", () => stopTeleop());
window.addEventListener("blur", () => stopTeleop("화면 포커스가 해제되어 정지했습니다."));
window.addEventListener("pagehide", () => stopTeleop("페이지를 벗어나 정지했습니다.", true));
document.addEventListener("visibilitychange", () => {
  if (document.hidden) stopTeleop("화면이 숨겨져 정지했습니다.");
});

elements["emergency-stop"].addEventListener("click", async () => {
  if (!window.confirm("Rosy를 즉시 정지할까요?")) return;
  stopTeleop("비상정지를 요청했습니다.");
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



elements["network-apply"]?.addEventListener("click", async () => {
  const profileId = elements["network-profile-id"]?.value.trim();
  if (!profileId) {
    setText("network-note", "프로파일 id를 입력하세요.");
    return;
  }
  if (!window.confirm(`${profileId} 네트워크 프로파일을 적용할까요? 연결이 잠깐 끊길 수 있습니다.`)) return;
  try {
    const payload = await api("/api/v1/host/network/apply", {
      method: "POST",
      body: JSON.stringify({
        profile_id: profileId,
        confirmed: true,
        idempotency_key: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
      }),
    });
    if (payload.available === false) {
      setText("network-note", payload.detail || "Host Agent가 없어 적용하지 못했습니다.");
      return;
    }
    setText("network-note", payload.ok ? `${profileId} 를 적용했습니다.` : (payload.detail || "적용이 거부되었습니다."));
    const status = await api("/api/v1/host/network");
    renderHostNetwork(status);
  } catch (error) {
    setText("network-note", `프로파일 적용 실패: ${error.message}`);
  }
});

bindFormSave("network-apply-form", "network-apply");

initSettings({
  onIdentityChanged: renderRobotInfo,
  refreshRobotState: () => refreshRobotState(),
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
