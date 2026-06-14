/**
 * realm-studio frontend — grid, edit menus, LLM turn, sidebar (V0.3.1b–0.4.0c2).
 */

import { hasAppearance, resolveAppearanceUrl } from "./appearance.js";
import { getPrompt, getState, postTurn } from "./api.js";
import { initGridViewport, maybeCenterGrid } from "./gridViewport.js";
import {
  appendTurnLogEntry,
  bindPromptDebug,
  renderAgentsElsewhere,
  renderLastPrompt,
  renderPassiveVision,
  renderRecentEvents,
  renderTurnLog,
  setLastPrompt,
} from "./panels.js";
import { activeAreaView, asArray, normalizeSnapshot } from "./snapshot.js";
import {
  bindActiveAgentSelect,
  bindActiveAreaSelect,
  bindAreaManageButtons,
  bindEmitEventButton,
  bindGridContextMenu,
  initUi,
  renderActiveAgentSelect,
  renderActiveAreaSelect,
  showToast,
} from "./ui.js";

const statusEl = document.getElementById("status");
const gridViewportEl = document.getElementById("grid-viewport");
const gridWorldEl = document.getElementById("grid-world");
const gridEl = document.getElementById("grid");
const snapshotEl = document.getElementById("snapshot");
const sessionMetaEl = document.getElementById("session-meta");
const passiveVisionEl = document.getElementById("passive-vision");
const passiveVisionEmptyEl = document.getElementById("passive-vision-empty");
const agentsElsewhereEl = document.getElementById("agents-elsewhere");
const agentsElsewhereEmptyEl = document.getElementById("agents-elsewhere-empty");
const recentEventsEl = document.getElementById("recent-events");
const recentEventsEmptyEl = document.getElementById("recent-events-empty");
const turnLogEl = document.getElementById("turn-log");
const turnLogEmptyEl = document.getElementById("turn-log-empty");
const lastPromptEl = document.getElementById("last-prompt");
const lastPromptEmptyEl = document.getElementById("last-prompt-empty");
const promptDebugEl = document.getElementById("prompt-debug");
const activeAreaSelect = document.getElementById("active-area-select");
const createAreaBtn = document.getElementById("create-area");
const editAreaBtn = document.getElementById("edit-area");
const deleteAreaBtn = document.getElementById("delete-area");
const activeAgentSelect = document.getElementById("active-agent-select");
const runTurnBtn = document.getElementById("run-turn");
const emitEventBtn = document.getElementById("emit-event");

let lastSnapshot = null;
let turnInFlight = false;

function posKey(x, y) {
  return `${x},${y}`;
}

function indexEntities(agents, objects) {
  const byPos = new Map();
  const add = (x, y, kind, entity) => {
    const key = posKey(x, y);
    if (!byPos.has(key)) {
      byPos.set(key, { agents: [], objects: [] });
    }
    byPos.get(key)[kind].push(entity);
  };
  for (const agent of asArray(agents)) {
    add(agent.position[0], agent.position[1], "agents", agent);
  }
  for (const object of asArray(objects)) {
    add(object.position[0], object.position[1], "objects", object);
  }
  return byPos;
}

function createNameChip(entity, kind, isActive) {
  const chip = document.createElement("div");
  chip.className = `chip chip-${kind}${isActive ? " chip-active" : ""}`;
  chip.dataset.kind = kind;
  chip.dataset.id = entity.id;
  chip.title = `${entity.name} (${entity.id})`;
  chip.textContent = entity.name;
  if (isActive) {
    const star = document.createElement("span");
    star.className = "chip-active-mark";
    star.textContent = " ★";
    star.setAttribute("aria-label", "active agent");
    chip.appendChild(star);
  }
  return chip;
}

function createTokenMarker(entity, kind, isActive) {
  const token = document.createElement("div");
  token.className = `token token-${kind}${isActive ? " token-active" : ""}`;
  token.dataset.kind = kind;
  token.dataset.id = entity.id;
  token.title = `${entity.name} (${entity.id})`;

  const img = document.createElement("img");
  img.className = "token-img";
  img.src = resolveAppearanceUrl(entity.appearance);
  img.alt = entity.name;
  img.draggable = false;
  img.addEventListener("error", () => {
    token.replaceWith(createNameChip(entity, kind, isActive));
  });
  token.appendChild(img);

  if (isActive) {
    const star = document.createElement("span");
    star.className = "token-active-mark";
    star.textContent = "★";
    star.setAttribute("aria-label", "active agent");
    token.appendChild(star);
  }
  return token;
}

function createEntityMarker(entity, kind, isActive) {
  if (hasAppearance(entity)) {
    return createTokenMarker(entity, kind, isActive);
  }
  return createNameChip(entity, kind, isActive);
}

function renderGrid(data) {
  const view = activeAreaView(data);
  const { grid, active_agent_id } = view;
  if (!grid) {
    gridEl.innerHTML = "";
    gridEl.classList.add("grid-empty");
    return;
  }
  gridEl.classList.remove("grid-empty");
  const byPos = indexEntities(view.agents, view.objects);

  const width = grid.max_x - grid.min_x + 1;
  const height = grid.max_y - grid.min_y + 1;

  gridEl.style.setProperty("--grid-cols", String(width));
  gridEl.style.setProperty("--grid-rows", String(height));
  gridEl.innerHTML = "";

  for (let y = grid.min_y; y <= grid.max_y; y++) {
    for (let x = grid.min_x; x <= grid.max_x; x++) {
      const tile = document.createElement("div");
      tile.className = "tile";
      tile.dataset.x = String(x);
      tile.dataset.y = String(y);

      const coord = document.createElement("span");
      coord.className = "tile-coord";
      coord.textContent = `${x}, ${y}`;
      tile.appendChild(coord);

      const stack = document.createElement("div");
      stack.className = "tile-stack";

      const at = byPos.get(posKey(x, y)) || { agents: [], objects: [] };
      for (const agent of asArray(at.agents)) {
        stack.appendChild(createEntityMarker(agent, "agent", agent.id === active_agent_id));
      }
      for (const object of asArray(at.objects)) {
        stack.appendChild(createEntityMarker(object, "object", false));
      }

      tile.appendChild(stack);
      gridEl.appendChild(tile);
    }
  }

  maybeCenterGrid(gridEl);
}

function renderSessionMeta(data) {
  const snap = normalizeSnapshot(data);
  const view = activeAreaView(snap);
  const agents = asArray(view.agents);
  const objects = asArray(view.objects);
  const allAgents = asArray(snap.agents);
  const active = allAgents.find((a) => a.id === snap.active_agent_id);
  const activeLabel = active ? `${active.name} (${active.id})` : snap.active_agent_id;
  const areaDesc = snap.areas?.[snap.active_area_id]?.area_description ?? "";

  sessionMetaEl.innerHTML = `
    <dt>Session turn</dt><dd>${snap.session_turn ?? "?"}</dd>
    <dt>Active area</dt><dd>${escapeHtml(snap.active_area_id ?? "—")}</dd>
    <dt>Area description</dt><dd>${escapeHtml(areaDesc)}</dd>
    <dt>Active agent</dt><dd>${escapeHtml(activeLabel ?? "—")}</dd>
    <dt>Agents (this area)</dt><dd>${agents.length}</dd>
    <dt>Objects (this area)</dt><dd>${objects.length}</dd>
  `;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderSidebarPanels(data) {
  renderPassiveVision(data, passiveVisionEl, passiveVisionEmptyEl);
  renderAgentsElsewhere(data, agentsElsewhereEl, agentsElsewhereEmptyEl);
  renderRecentEvents(activeAreaView(data), recentEventsEl, recentEventsEmptyEl);
}

function renderState(data) {
  lastSnapshot = normalizeSnapshot(data);
  renderGrid(lastSnapshot);
  renderSessionMeta(lastSnapshot);
  renderSidebarPanels(lastSnapshot);
  if (activeAreaSelect) renderActiveAreaSelect(activeAreaSelect, lastSnapshot);
  if (activeAgentSelect) renderActiveAgentSelect(activeAgentSelect, lastSnapshot);
  snapshotEl.textContent = JSON.stringify(lastSnapshot, null, 2);
}

async function fetchState() {
  statusEl.textContent = "Fetching…";
  try {
    const data = await getState();
    renderState(data);
    updateStatusLine(lastSnapshot);
  } catch (err) {
    gridEl.innerHTML = "";
    gridEl.classList.add("grid-empty");
    snapshotEl.textContent = String(err.message || err);
    statusEl.textContent = `Error — ${err.message || err}`;
    showToast(String(err.message || err), true);
  }
}

function updateStatusLine(data) {
  const snap = normalizeSnapshot(data);
  const active = asArray(snap.agents).find((a) => a.id === snap.active_agent_id);
  const area = snap.active_area_id ?? "area";
  const agentName = active ? active.name : snap.active_agent_id ?? "—";
  statusEl.textContent = `Turn ${snap.session_turn ?? "?"} — ${area} — ${agentName}`;
}

function recordTurnResult(result) {
  const snap = normalizeSnapshot(result.snapshot || lastSnapshot);
  const active = asArray(snap.agents).find((a) => a.id === snap.active_agent_id);
  appendTurnLogEntry({
    sessionTurn: snap.session_turn ?? "?",
    agentName: active?.name ?? "Agent",
    message: result.message,
    steps: result.steps,
  });
  renderTurnLog(turnLogEl, turnLogEmptyEl);
  if (result.prompt) {
    setLastPrompt(result.prompt);
    if (promptDebugEl.open) {
      renderLastPrompt(lastPromptEl, lastPromptEmptyEl);
    }
  }
}

async function runTurn() {
  if (turnInFlight) return;
  turnInFlight = true;
  runTurnBtn.disabled = true;
  statusEl.textContent = "Running LLM turn…";
  try {
    const result = await postTurn({});
    if (!result.ok) {
      showToast(result.message, true);
      statusEl.textContent = "Turn failed";
      return;
    }
    if (result.snapshot) {
      renderState(result.snapshot);
      updateStatusLine(result.snapshot);
    } else {
      await fetchState();
    }
    recordTurnResult(result);
    const stepCount = Array.isArray(result.steps) ? result.steps.length : 0;
    const suffix = stepCount ? ` (${stepCount} step${stepCount === 1 ? "" : "s"})` : "";
    showToast(`${result.message}${suffix}`, false);
  } catch (err) {
    showToast(String(err.message || err), true);
    statusEl.textContent = "Error";
  } finally {
    turnInFlight = false;
    runTurnBtn.disabled = false;
  }
}

async function refreshAfterMutation(snapshot) {
  if (snapshot) {
    renderState(snapshot);
    updateStatusLine(lastSnapshot);
    return;
  }
  await fetchState();
}

initUi({
  getSnapshotFn: () => activeAreaView(lastSnapshot),
  onStateChangedFn: refreshAfterMutation,
});
initGridViewport(gridViewportEl, gridWorldEl);
bindGridContextMenu(gridEl);
if (activeAreaSelect) bindActiveAreaSelect(activeAreaSelect, refreshAfterMutation);
if (activeAgentSelect) bindActiveAgentSelect(activeAgentSelect, refreshAfterMutation);
bindAreaManageButtons({
  createBtn: createAreaBtn,
  editBtn: editAreaBtn,
  deleteBtn: deleteAreaBtn,
});
bindEmitEventButton(emitEventBtn);
bindPromptDebug(promptDebugEl, lastPromptEl, lastPromptEmptyEl, () => getPrompt());

document.getElementById("refresh").addEventListener("click", fetchState);
runTurnBtn.addEventListener("click", runTurn);
renderTurnLog(turnLogEl, turnLogEmptyEl);
fetchState();
