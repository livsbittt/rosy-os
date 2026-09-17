// 대시보드가 공유하는 DOM 접근과 표시 형식.
// 여기 있는 함수는 네트워크도 세션도 모르며, 그래서 어느 모듈에서든 안전하게 부를 수 있다.

export const elements = Object.fromEntries(
  [...document.querySelectorAll("[id]")].map((element) => [element.id, element]),
);

export function setText(id, value, fallback = "—", evidence) {
  const node = elements[id];
  if (!node) return;
  node.textContent = value ?? fallback;
  if (evidence == null) {
    delete node.dataset.evidence;
    node.removeAttribute("title");
    return;
  }
  const state = typeof evidence === "string" ? evidence : evidence.evidence;
  const received = typeof evidence === "object" ? evidence.received_at : undefined;
  if (state) node.dataset.evidence = state;
  else delete node.dataset.evidence;
  if (received) node.title = received;
  else node.removeAttribute("title");
}

export function number(value, digits = 1) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "—";
}

export function percent(value) {
  return Number.isFinite(Number(value)) ? `${Math.round(Number(value))}%` : "—";
}

export function bytes(value) {
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

export function duration(value) {
  if (!Number.isFinite(Number(value))) return "—";
  const total = Math.floor(Number(value));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  return `${days}일 ${hours}시간 ${minutes}분`;
}

export function setMeter(id, value) {
  const safe = Number.isFinite(Number(value)) ? Math.max(0, Math.min(100, Number(value))) : 0;
  elements[id]?.style.setProperty("--meter", `${safe}%`);
}

export function rate(value) {
  const amount = metricNumber(value);
  return amount === null ? "—" : `${bytes(amount)}/s`;
}

export function metricNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const amount = Number(value);
  return Number.isFinite(amount) ? amount : null;
}

export function svgText(label, x, y, className) {
  const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
  text.setAttribute("x", x);
  text.setAttribute("y", y);
  text.setAttribute("class", className);
  text.textContent = label;
  return text;
}

export function fillNumberInput(id, value) {
  const input = elements[id];
  if (!input || document.activeElement === input) return;
  input.value = Number.isFinite(Number(value)) ? Number(value).toFixed(2) : "";
}

export function fillSelect(id, value) {
  const input = elements[id];
  if (!input || document.activeElement === input || value == null || value === "") return;
  input.value = value;
}

export function fillTextInput(id, value) {
  const input = elements[id];
  if (!input || document.activeElement === input) return;
  input.value = value == null ? "" : String(value);
}

export function setFieldMessage(id, text) {
  setText(id, text, "");
}

export function setEnabled(id, enabled) {
  const element = document.getElementById(id);
  if (element) element.disabled = !enabled;
}

/** 저장 버튼은 type="button" 이다. Enter 로 submit 되면 셸이 통째로 다시 뜬다. */
export function bindFormSave(formId, buttonId) {
  elements[formId]?.addEventListener("submit", (event) => {
    event.preventDefault();
    elements[buttonId]?.click();
  });
}
