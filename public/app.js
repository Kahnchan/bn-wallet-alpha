const state = {
  events: [],
  cursor: asiaShanghaiToday(),
  selectedDateKey: null,
};

const monthGrid = document.querySelector("#monthGrid");
const miniGrid = document.querySelector("#miniGrid");
const miniTitle = document.querySelector("#miniTitle");
const monthTitle = document.querySelector("#monthTitle");
const monthSummary = document.querySelector("#monthSummary");
const selectedDate = document.querySelector("#selectedDate");
const selectedCount = document.querySelector("#selectedCount");
const detailList = document.querySelector("#detailList");
const copyResult = document.querySelector("#copyResult");

document.querySelector("#prevMonth").addEventListener("click", () => moveMonth(-1));
document.querySelector("#nextMonth").addEventListener("click", () => moveMonth(1));
document.querySelector("#todayButton").addEventListener("click", () => {
  state.cursor = asiaShanghaiToday();
  state.selectedDateKey = toDateKey(state.cursor);
  render();
});

document.querySelector(".copy-button").addEventListener("click", async (event) => {
  const value = event.currentTarget.dataset.copy;
  try {
    await navigator.clipboard.writeText(value);
    copyResult.textContent = "已复制";
  } catch {
    copyResult.textContent = value;
  }
});

loadEvents();

async function loadEvents() {
  try {
    const response = await fetch(`./history.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const items = Array.isArray(payload.items) ? payload.items : [];
    state.events = items.map(normalizeEvent).filter(Boolean).sort((a, b) => a.startsAt - b.startsAt);
    const latest = latestEventDate(state.events);
    if (latest) state.cursor = new Date(latest.getFullYear(), latest.getMonth(), 1);
    state.selectedDateKey = toDateKey(asiaShanghaiToday());
  } catch (error) {
    monthSummary.textContent = `读取 history.json 失败：${error.message}`;
  }
  render();
}

function normalizeEvent(item) {
  if (!item || !item.listingTime) return null;
  const startsAt = new Date(item.listingTime);
  if (Number.isNaN(startsAt.valueOf())) return null;
  const local = toShanghaiParts(startsAt);
  const symbol = item.symbol || "UNKNOWN";
  const isUnknown = symbol === "待公布";
  return {
    ...item,
    startsAt,
    dateKey: local.dateKey,
    timeText: item.dateOnly ? "全天" : local.time,
    title: `${symbol} - BN Alpha ${isUnknown ? "空投" : item.signalType === "social_alpha_notice" ? "预告" : "空投"}`,
    tone: isUnknown ? "unknown" : item.signalType === "social_alpha_notice" ? "notice" : "alpha",
  };
}

function latestEventDate(events) {
  if (!events.length) return null;
  return events[events.length - 1].startsAt;
}

function moveMonth(delta) {
  state.cursor = new Date(state.cursor.getFullYear(), state.cursor.getMonth() + delta, 1);
  state.selectedDateKey = null;
  render();
}

function render() {
  renderMonth();
  renderMiniMonth();
  const selected = state.selectedDateKey || firstEventInMonthKey();
  state.selectedDateKey = selected;
  renderDetails(selected);
}

function renderMonth() {
  const year = state.cursor.getFullYear();
  const month = state.cursor.getMonth();
  monthTitle.textContent = `${year} 年 ${month + 1} 月`;

  const eventsInMonth = state.events.filter((event) => {
    const [eventYear, eventMonth] = event.dateKey.split("-").map(Number);
    return eventYear === year && eventMonth === month + 1;
  });
  monthSummary.textContent = eventsInMonth.length ? `${eventsInMonth.length} 个 Alpha 事件` : "本月暂无 Alpha 事件";

  const cells = getMonthCells(year, month);
  monthGrid.innerHTML = "";
  cells.forEach((date) => {
    const dateKey = toDateKey(date);
    const dayEvents = eventsForDate(dateKey);
    const cell = document.createElement("div");
    cell.setAttribute("role", "button");
    cell.tabIndex = 0;
    cell.className = "day-cell";
    if (date.getMonth() !== month) cell.classList.add("is-outside");
    if (dateKey === state.selectedDateKey) cell.classList.add("is-selected");
    cell.addEventListener("click", () => {
      state.selectedDateKey = dateKey;
      render();
    });
    cell.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        state.selectedDateKey = dateKey;
        render();
      }
    });

    const number = document.createElement("div");
    number.className = `day-number${dateKey === toDateKey(asiaShanghaiToday()) ? " today" : ""}`;
    number.innerHTML = `<span>${date.getDate()}</span>`;
    cell.appendChild(number);

    const stack = document.createElement("div");
    stack.className = "event-stack";
    dayEvents.slice(0, 3).forEach((event) => stack.appendChild(renderEventPill(event)));
    if (dayEvents.length > 3) {
      const more = document.createElement("div");
      more.className = "more-count";
      more.textContent = `还有 ${dayEvents.length - 3} 个`;
      stack.appendChild(more);
    }
    cell.appendChild(stack);
    monthGrid.appendChild(cell);
  });
}

function renderMiniMonth() {
  const year = state.cursor.getFullYear();
  const month = state.cursor.getMonth();
  miniTitle.textContent = `${month + 1}月`;
  miniGrid.innerHTML = "";
  getMonthCells(year, month).forEach((date) => {
    const dateKey = toDateKey(date);
    const node = document.createElement("span");
    node.textContent = date.getDate();
    if (eventsForDate(dateKey).length) node.classList.add("has-event");
    if (dateKey === toDateKey(asiaShanghaiToday())) node.classList.add("today");
    miniGrid.appendChild(node);
  });
}

function renderEventPill(event) {
  const pill = document.createElement("button");
  pill.type = "button";
  pill.className = `event-pill ${event.tone}`;
  pill.innerHTML = `<span class="event-time">${event.timeText}</span> ${escapeHtml(event.title)}`;
  pill.addEventListener("click", (clickEvent) => {
    clickEvent.stopPropagation();
    state.selectedDateKey = event.dateKey;
    render();
  });
  return pill;
}

function renderDetails(dateKey) {
  const events = eventsForDate(dateKey);
  selectedDate.textContent = formatDateLabel(dateKey);
  selectedCount.textContent = `${events.length} 个事件`;
  detailList.innerHTML = "";
  if (!events.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "这一天没有 Alpha 空投记录。";
    detailList.appendChild(empty);
    return;
  }
  events.forEach((event) => {
    const card = document.createElement("article");
    card.className = "detail-card";
    const rule = Array.isArray(event.ruleSummary) && event.ruleSummary.length ? event.ruleSummary[0] : "请以 Binance Wallet > Alpha > Events 为准。";
    const href = event.sourceUrl || "./binance-alpha-airdrops.ics";
    card.innerHTML = `
      <h3>${escapeHtml(event.title)}</h3>
      <p>${escapeHtml(event.timeText)} · ${escapeHtml(event.name || "")}</p>
      <p>${escapeHtml(rule)}</p>
      <a href="${escapeAttribute(href)}">打开来源</a>
    `;
    detailList.appendChild(card);
  });
}

function eventsForDate(dateKey) {
  return state.events.filter((event) => event.dateKey === dateKey);
}

function firstEventInMonthKey() {
  const year = state.cursor.getFullYear();
  const month = state.cursor.getMonth() + 1;
  const event = state.events.find((item) => {
    const [eventYear, eventMonth] = item.dateKey.split("-").map(Number);
    return eventYear === year && eventMonth === month;
  });
  return event ? event.dateKey : toDateKey(new Date(year, month - 1, 1));
}

function getMonthCells(year, month) {
  const first = new Date(year, month, 1);
  const start = new Date(year, month, 1 - first.getDay());
  return Array.from({ length: 42 }, (_, index) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + index));
}

function asiaShanghaiToday() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return new Date(Number(value.year), Number(value.month) - 1, Number(value.day));
}

function toShanghaiParts(date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return {
    dateKey: `${value.year}-${value.month}-${value.day}`,
    time: `${value.hour}:${value.minute}`,
  };
}

function toDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDateLabel(dateKey) {
  if (!dateKey) return "选择日期";
  const [year, month, day] = dateKey.split("-").map(Number);
  return `${year} 年 ${month} 月 ${day} 日`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}
