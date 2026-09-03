function GridFrame(grid) {
  this.width = Number(grid?.width) || 0;
  this.height = Number(grid?.height) || 0;
  this.resolution = Number(grid?.resolution) || 0;
  this.originX = Number(grid?.origin?.x) || 0;
  this.originY = Number(grid?.origin?.y) || 0;
  this.data = grid?.data || [];
}

GridFrame.prototype.worldToCell = function worldToCell(x, y) {
  if (this.resolution <= 0 || this.width <= 0 || this.height <= 0) return null;
  const column = Math.floor((Number(x) - this.originX) / this.resolution);
  const row = Math.floor((Number(y) - this.originY) / this.resolution);
  if (column < 0 || row < 0 || column >= this.width || row >= this.height) return null;
  return { column, row };
};

GridFrame.prototype.sampleWorld = function sampleWorld(x, y) {
  const cell = this.worldToCell(x, y);
  if (!cell) return null;
  const value = Number(this.data[cell.row * this.width + cell.column]);
  return Number.isFinite(value) ? value : null;
};

GridFrame.prototype.canvasToWorld = function canvasToWorld(px, py, canvasWidth, canvasHeight) {
  const cellX = (px / canvasWidth) * this.width;
  const cellY = (1 - py / canvasHeight) * this.height;
  return {
    x: this.originX + cellX * this.resolution,
    y: this.originY + cellY * this.resolution,
  };
};

GridFrame.prototype.worldToCanvas = function worldToCanvas(x, y, canvasWidth, canvasHeight) {
  const cellX = (Number(x) - this.originX) / this.resolution;
  const cellY = (Number(y) - this.originY) / this.resolution;
  return {
    x: (cellX / this.width) * canvasWidth,
    y: (1 - cellY / this.height) * canvasHeight,
  };
};

function occupancyColor(cell) {
  if (cell < 0) return [17, 22, 20, 255];
  if (cell < 20) return [36, 46, 41, 255];
  if (cell < 60) return [90, 78, 48, 255];
  return [196, 219, 118, 255];
}

function paintLayers(occupancy, costmap, layers, width, height) {
  const image = new ImageData(width, height);
  const costFrame = layers.costmap && costmap ? new GridFrame(costmap) : null;
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const world = occupancy.canvasToWorld(x + 0.5, y + 0.5, width, height);
      const cell = layers.occupancy ? occupancy.sampleWorld(world.x, world.y) : -1;
      const color = occupancyColor(cell == null ? -1 : cell);
      const index = (y * width + x) * 4;
      image.data[index] = color[0];
      image.data[index + 1] = color[1];
      image.data[index + 2] = color[2];
      image.data[index + 3] = color[3];
      if (!costFrame) continue;
      const lethal = costFrame.sampleWorld(world.x, world.y);
      if (lethal == null || lethal < 50) continue;
      const mix = Math.min(1, lethal / 254);
      image.data[index] = Math.round(image.data[index] * (1 - mix) + 242 * mix);
      image.data[index + 1] = Math.round(image.data[index + 1] * (1 - mix) + 196 * mix);
      image.data[index + 2] = Math.round(image.data[index + 2] * (1 - mix) + 109 * mix);
    }
  }
  return image;
}

export function createFieldMap(options) {
  const canvas = options.canvas;
  const empty = options.empty;
  const status = options.status;
  const api = options.api;
  const apiMaybe = options.apiMaybe;
  const getPose = options.getPose;
  const getNavigation = options.getNavigation;
  const canGoal = options.canGoal;
  const setAction = options.setAction;
  const layerButtons = [...(options.layerRoot?.querySelectorAll("[data-map-layer]") || [])];
  const clickButtons = [...(options.layerRoot?.querySelectorAll("[data-map-click]") || [])];

  const layers = { occupancy: true, costmap: true, path: true };
  let clickMode = "pose";
  const state = { occupancy: null, path: [], costmap: null, raster: null, lastNav: null };
  const ctx = canvas?.getContext("2d") || null;

  function setStatus(text) {
    if (status) status.textContent = text;
  }

  function syncEmpty() {
    if (!empty) return;
    empty.hidden = Boolean(state.occupancy);
  }

  function fitCanvas() {
    if (!canvas) return false;
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.round((canvas.clientWidth || canvas.width || 1) * ratio));
    const height = Math.max(1, Math.round((canvas.clientHeight || canvas.height || 1) * ratio));
    if (canvas.width === width && canvas.height === height) return false;
    canvas.width = width;
    canvas.height = height;
    return true;
  }

  function syncCursor() {
    if (!canvas) return;
    canvas.style.cursor = canGoal?.() ? "crosshair" : "default";
  }

  function rebuildRaster() {
    if (!ctx || !canvas) return;
    fitCanvas();
    if (!state.occupancy) {
      state.raster = null;
      ctx.fillStyle = "#0d1210";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      return;
    }
    const frame = new GridFrame(state.occupancy);
    state.raster = paintLayers(frame, state.costmap, layers, canvas.width, canvas.height);
  }

  function paint() {
    if (!ctx || !canvas) return;
    if (!state.occupancy || !state.raster) {
      ctx.fillStyle = "#0d1210";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      return;
    }
    ctx.putImageData(state.raster, 0, 0);
    const frame = new GridFrame(state.occupancy);
    if (layers.path && state.path.length >= 2) {
      ctx.beginPath();
      state.path.forEach((pose, index) => {
        const point = frame.worldToCanvas(pose.x, pose.y, canvas.width, canvas.height);
        if (index === 0) ctx.moveTo(point.x, point.y);
        else ctx.lineTo(point.x, point.y);
      });
      ctx.strokeStyle = "#75b8c8";
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    const pose = getPose?.();
    if (!pose || !Number.isFinite(Number(pose.x))) return;
    const point = frame.worldToCanvas(pose.x, pose.y, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(point.x, point.y);
    ctx.rotate(-Number(pose.yaw) || 0);
    ctx.beginPath();
    ctx.moveTo(10, 0);
    ctx.lineTo(-7, 7);
    ctx.lineTo(-7, -7);
    ctx.closePath();
    ctx.fillStyle = "#c4db76";
    ctx.fill();
    ctx.restore();
  }

  function setPose() {
    const nav = getNavigation?.();
    if (nav && nav !== state.lastNav) {
      state.lastNav = nav;
      refreshPath();
    }
    syncCursor();
    paint();
  }

  async function refreshPath() {
    const path = await apiMaybe("/api/v1/navigation/path");
    state.path = path?.poses || [];
    paint();
  }

  async function refresh() {
    const [grid, path, costmap] = await Promise.all([
      apiMaybe("/api/v1/map"),
      apiMaybe("/api/v1/navigation/path"),
      apiMaybe("/api/v1/map/costmap?scope=global"),
    ]);
    state.occupancy = grid;
    state.path = path?.poses || [];
    state.costmap = costmap;
    syncEmpty();
    syncCursor();
    if (!grid) setStatus("맵 수신 대기");
    else setStatus(`${grid.width}×${grid.height}${grid.map_id ? ` · ${grid.map_id}` : ""}`);
    rebuildRaster();
    paint();
  }

  layerButtons.forEach((button) => {
    const layer = button.dataset.mapLayer;
    button.setAttribute("aria-pressed", layers[layer] ? "true" : "false");
    button.addEventListener("click", () => {
      layers[layer] = !layers[layer];
      button.setAttribute("aria-pressed", layers[layer] ? "true" : "false");
      rebuildRaster();
      paint();
    });
  });

  clickButtons.forEach((button) => {
    const mode = button.dataset.mapClick;
    button.setAttribute("aria-pressed", clickMode === mode ? "true" : "false");
    button.addEventListener("click", () => {
      clickMode = mode;
      clickButtons.forEach((item) => {
        item.setAttribute("aria-pressed", item.dataset.mapClick === clickMode ? "true" : "false");
      });
    });
  });

  if (typeof ResizeObserver === "function" && canvas) {
    new ResizeObserver(() => {
      if (fitCanvas()) {
        rebuildRaster();
        paint();
      }
    }).observe(canvas);
  }

  canvas?.addEventListener("click", async (event) => {
    if (!state.occupancy || !canvas) return;
    if (!canGoal?.()) {
      setStatus("이 프로필에서는 목표 전송이 꺼져 있습니다.");
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const px = ((event.clientX - rect.left) / rect.width) * canvas.width;
    const py = ((event.clientY - rect.top) / rect.height) * canvas.height;
    const world = new GridFrame(state.occupancy).canvasToWorld(px, py, canvas.width, canvas.height);
    const yaw = Number(getPose?.()?.yaw) || 0;
    const locating = clickMode === "pose";
    const label = locating ? "초기 자세" : "목표";
    const path = locating
      ? "/api/v1/localization/initialpose"
      : "/api/v1/navigation/goal";
    if (!window.confirm(`${label} ${world.x.toFixed(2)}, ${world.y.toFixed(2)} 로 보낼까요?`)) return;
    try {
      await api(path, {
        method: "POST",
        body: JSON.stringify({ x: world.x, y: world.y, yaw }),
      });
      setAction?.(`${label} ${world.x.toFixed(2)}, ${world.y.toFixed(2)} 전송`);
      setStatus(`${locating ? "pose" : "goal"} ${world.x.toFixed(2)}, ${world.y.toFixed(2)}`);
    } catch (error) {
      setStatus(`${label} 전송 실패: ${error.message}`);
    }
  });

  syncEmpty();
  return { refresh, setPose };
}
