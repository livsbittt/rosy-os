// 사이트 관제 화면. 서버(Fleet)만 본다 — 로봇 API 를 직접 부르지 않는다.
//
// 좌표계: 로봇 pose 는 CORE 가 TF `map → <ns>base_footprint` 로 읽어 주는 map 프레임
// 값이다(ros_bridge `_map_frame = "map"`). 그래서 N대를 한 격자 위에 그대로 겹쳐
// 그릴 수 있다. 격자는 행 0 이 아래쪽(y 최소)이고 캔버스는 위가 0 이라 y 를 뒤집는다.

const GRID = { UNKNOWN: -1, FREE_MAX: 25, OCCUPIED_MIN: 65 };
const STATE_MS = 1000;
const MAP_MS = 5000;
const LOG_MAX = 40;

const el = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const view = {
  map: null,
  robots: [],
  selected: null, // 목표 지정을 기다리는 robot_id
  colors: [],
};

function log(text, kind) {
  const line = document.createElement("div");
  if (kind) line.className = kind;
  const now = new Date().toTimeString().slice(0, 8);
  line.textContent = `${now}  ${text}`;
  const box = el("log");
  box.prepend(line);
  while (box.childElementCount > LOG_MAX) box.lastElementChild.remove();
}

async function call(path, options) {
  const resp = await fetch(path, options);
  let body = null;
  try {
    body = await resp.json();
  } catch (err) {
    body = null;
  }
  if (!resp.ok) {
    const detail = body && body.detail ? body.detail : {};
    throw new Error(detail.message || detail.code || `HTTP ${resp.status}`);
  }
  return body;
}

// --- 지도 ------------------------------------------------------------------

function paintGrid(grid) {
  const canvas = el("map-canvas");
  const { width, height } = grid;
  // 캔버스의 고유 크기는 이 속성이다. CSS 가 `width:100%; height:auto` 라 비율은 여기서
  // 따라온다 — style 속성을 쓰지 않는 이유는 CSP(`style-src 'self'`)가 그것을 막기 때문이다.
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  const image = ctx.createImageData(width, height);
  const free = hexToRgb(css("--paper"));
  const occupied = hexToRgb(css("--ground-deep"));
  const unknown = hexToRgb(css("--ground-soft"));
  for (let row = 0; row < height; row += 1) {
    for (let col = 0; col < width; col += 1) {
      const value = grid.data[row * width + col];
      const rgb = value === GRID.UNKNOWN || value < 0 ? unknown
        : value >= GRID.OCCUPIED_MIN ? occupied
          : value <= GRID.FREE_MAX ? free : unknown;
      const pixel = ((height - 1 - row) * width + col) * 4;
      image.data[pixel] = rgb[0];
      image.data[pixel + 1] = rgb[1];
      image.data[pixel + 2] = rgb[2];
      image.data[pixel + 3] = 255;
    }
  }
  ctx.putImageData(image, 0, 0);
}

function hexToRgb(value) {
  const hex = value.replace("#", "");
  const n = parseInt(hex.length === 3 ? hex.split("").map((c) => c + c).join("") : hex, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function worldToCell(grid, x, y) {
  return {
    col: (x - grid.origin.x) / grid.resolution,
    row: (y - grid.origin.y) / grid.resolution,
  };
}

function cellToWorld(grid, col, row) {
  return {
    x: grid.origin.x + (col + 0.5) * grid.resolution,
    y: grid.origin.y + (row + 0.5) * grid.resolution,
  };
}

function drawOverlay() {
  const grid = view.map;
  if (!grid) return;
  const canvas = el("map-canvas");
  const ctx = canvas.getContext("2d");
  paintGrid(grid);
  // 격자 픽셀 위에 그리므로 선 굵기도 격자 칸 단위다. 0.6칸이면 3 cm 남짓이다.
  ctx.lineWidth = 0.6;
  view.robots.forEach((robot, index) => {
    const pose = robot.state && robot.state.pose;
    if (!pose) return;
    const color = view.colors[index % view.colors.length];
    const cell = worldToCell(grid, pose.x, pose.y);
    const cx = cell.col;
    const cy = grid.height - cell.row;
    const size = Math.max(3, Math.min(grid.width, grid.height) * 0.045);
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(-pose.yaw); // 캔버스 y 가 아래로 자라므로 회전도 뒤집는다
    ctx.beginPath();
    ctx.moveTo(size, 0);
    ctx.lineTo(-size * 0.6, size * 0.62);
    ctx.lineTo(-size * 0.6, -size * 0.62);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.globalAlpha = robot.online ? 1 : 0.35;
    ctx.fill();
    ctx.restore();

    // 목표는 Fleet 이 기억하는 값이다(로봇 상태에는 없다) — "내가 무엇을 시켰는가".
    const goal = robot.goal;
    if (goal && typeof goal.x === "number") {
      const gcell = worldToCell(grid, goal.x, goal.y);
      ctx.beginPath();
      ctx.arc(gcell.col, grid.height - gcell.row, size * 0.5, 0, Math.PI * 2);
      ctx.strokeStyle = css("--status-warn");
      ctx.globalAlpha = 1;
      ctx.stroke();
    }
  });
}

async function refreshMap() {
  try {
    const grid = await call("/api/fleet/map");
    view.map = grid;
    el("map-tag").textContent = `${grid.width}×${grid.height} · ${grid.map_id || "map"}`;
    drawOverlay();
  } catch (err) {
    el("map-tag").textContent = "맵 없음";
  }
}

// --- 로봇 목록 --------------------------------------------------------------

function navTag(state) {
  const nav = state && state.navigation;
  if (!nav) return { text: "—", cls: "" };
  if (nav === "NAVIGATING") return { text: nav, cls: "nav" };
  if (nav === "ARRIVED") return { text: nav, cls: "ok" };
  if (nav === "FAILED") return { text: nav, cls: "crit" };
  return { text: nav, cls: "" };
}

function card(robot, index) {
  const node = document.createElement("article");
  node.className = `robot s${index % view.colors.length}`;
  if (!robot.online) node.classList.add("offline");
  if (view.selected === robot.robot_id) node.classList.add("selected");

  const state = robot.state || {};
  const pose = state.pose;
  const nav = navTag(state);
  const estop = state.safety && state.safety.estop;

  const head = document.createElement("div");
  head.className = "robot-head";
  head.innerHTML = `<b>${robot.robot_id}</b><span class="spacer"></span>`;
  const mode = document.createElement("span");
  mode.className = "tag";
  mode.textContent = robot.online ? (state.mode || "—") : "OFFLINE";
  if (!robot.online) mode.classList.add("crit");
  head.appendChild(mode);
  const navEl = document.createElement("span");
  navEl.className = `tag ${nav.cls}`;
  navEl.textContent = nav.text;
  head.appendChild(navEl);
  node.appendChild(head);

  const facts = document.createElement("div");
  facts.className = "facts";
  const battery = state.battery && typeof state.battery.percent === "number"
    ? `${Math.round(state.battery.percent)}%` : "—";
  const rows = [
    ["POSE", pose ? `${pose.x.toFixed(2)}, ${pose.y.toFixed(2)}` : "—"],
    ["YAW", pose ? `${(pose.yaw * 180 / Math.PI).toFixed(0)}°` : "—"],
    ["BATTERY", battery],
    ["SAFETY", estop ? "E-STOP" : robot.online ? "OK" : "—"],
  ];
  rows.forEach(([label, value]) => {
    const cellEl = document.createElement("div");
    cellEl.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    facts.appendChild(cellEl);
  });
  node.appendChild(facts);

  if (!robot.online && robot.error) {
    const why = document.createElement("p");
    why.className = "hint";
    why.textContent = robot.error.reachable
      ? `로봇이 거절: ${robot.error.code}` : `닿지 않음: ${robot.error.code}`;
    node.appendChild(why);
  }

  const actions = document.createElement("div");
  actions.className = "robot-actions";
  const aim = document.createElement("button");
  aim.type = "button";
  aim.textContent = view.selected === robot.robot_id ? "지도를 찍으세요" : "목표 지정";
  if (view.selected === robot.robot_id) aim.classList.add("arming");
  aim.disabled = !robot.online || !view.map;
  aim.addEventListener("click", () => {
    view.selected = view.selected === robot.robot_id ? null : robot.robot_id;
    el("map-canvas").classList.toggle("idle", view.selected === null);
    render();
  });
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.textContent = "취소";
  cancel.disabled = !robot.online;
  cancel.addEventListener("click", async () => {
    try {
      await call(`/api/fleet/robots/${encodeURIComponent(robot.robot_id)}/cancel`, { method: "POST" });
      log(`${robot.robot_id} 항법 취소`, "good");
    } catch (err) {
      log(`${robot.robot_id} 취소 실패 — ${err.message}`, "bad");
    }
  });
  actions.append(aim, cancel);
  node.appendChild(actions);
  return node;
}

function render() {
  const roster = el("roster");
  roster.replaceChildren(...view.robots.map(card));
  drawOverlay();
  const hint = el("hint");
  hint.textContent = view.selected
    ? `${view.selected}에게 보낼 목표를 지도에서 찍으세요. 다시 누르면 취소됩니다.`
    : "오른쪽에서 로봇의 목표 지정을 누른 뒤 지도를 찍으면 그 로봇에게만 목표가 갑니다.";
}

async function refreshState() {
  try {
    const snapshot = await call("/api/fleet/state");
    view.robots = snapshot.robots;
    el("fleet-name").textContent = (snapshot.fleet.name || "site").toUpperCase();
    const pill = el("online-pill");
    pill.textContent = `${snapshot.fleet.online}/${snapshot.fleet.total} 연결`;
    pill.className = `pill ${snapshot.fleet.online === snapshot.fleet.total ? "good" : "bad"}`;
    render();
  } catch (err) {
    const pill = el("online-pill");
    pill.textContent = "Fleet 서버 없음";
    pill.className = "pill bad";
  }
}

// --- 조작 ------------------------------------------------------------------

el("map-canvas").addEventListener("click", async (event) => {
  if (!view.selected || !view.map) return;
  const canvas = el("map-canvas");
  const rect = canvas.getBoundingClientRect();
  const col = ((event.clientX - rect.left) / rect.width) * view.map.width;
  const rowFromTop = ((event.clientY - rect.top) / rect.height) * view.map.height;
  const point = cellToWorld(view.map, Math.floor(col), Math.floor(view.map.height - rowFromTop));
  const robotId = view.selected;
  view.selected = null;
  canvas.classList.add("idle");
  render();
  try {
    await call(`/api/fleet/robots/${encodeURIComponent(robotId)}/goal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ x: point.x, y: point.y, yaw: 0 }),
    });
    log(`${robotId} → (${point.x.toFixed(2)}, ${point.y.toFixed(2)}) 미션 하달`, "good");
  } catch (err) {
    log(`${robotId} 미션 거절 — ${err.message}`, "bad");
  }
});

el("estop").addEventListener("click", async () => {
  if (!window.confirm("등록된 모든 로봇을 정지시킵니다. 계속할까요?")) return;
  try {
    const result = await call("/api/fleet/estop", { method: "POST" });
    log(`전체 정지: ${result.stopped}/${result.total}`, result.stopped === result.total ? "good" : "bad");
    result.robots.filter((r) => !r.stopped)
      .forEach((r) => log(`  ${r.robot_id} 정지 실패 — ${r.error.code}`, "bad"));
  } catch (err) {
    log(`전체 정지 실패 — ${err.message}`, "bad");
  }
});

function tickClock() {
  el("clock").textContent = new Date().toTimeString().slice(0, 8);
}

view.colors = [css("--series-primary"), css("--series-2"), css("--series-3"), css("--series-4")];
tickClock();
setInterval(tickClock, 1000);
refreshState();
refreshMap();
setInterval(refreshState, STATE_MS);
setInterval(refreshMap, MAP_MS);
