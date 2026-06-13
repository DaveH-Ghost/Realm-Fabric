/**
 * realm-studio frontend — grid, edit menus, LLM turn, sidebar (V0.3.1b–0.3.2b).
 */

import { getPrompt, getState, postTurn } from "./api.js";
import {
  appendTurnLogEntry,
  bindPromptDebug,
  renderLastPrompt,
  renderPassiveVision,
  renderRecentEvents,
  renderTurnLog,
  setLastPrompt,
} from "./panels.js";
import {
  bindActiveAgentSelect,
  bindEmitEventButton,
  bindGridContextMenu,
  initUi,
  renderActiveAgentSelect,
  showToast,
} from "./ui.js";

const statusEl = document.getElementById("status");
const gridEl = document.getElementById("grid");
const snapshotEl = document.getElementById("snapshot");
const sessionMetaEl = document.getElementById("session-meta");
const passiveVisionEl = document.getElementById("passive-vision");
const passiveVisionEmptyEl = document.getElementById("passive-vision-empty");
const recentEventsEl = document.getElementById("recent-events");
const recentEventsEmptyEl = document.getElementById("recent-events-empty");
const turnLogEl = document.getElementById("turn-log");
const turnLogEmptyEl = document.getElementById("turn-log-empty");
const lastPromptEl = document.getElementById("last-prompt");
const lastPromptEmptyEl = document.getElementById("last-prompt-empty");
const promptDebugEl = document.getElementById("prompt-debug");
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
  for (const agent of agents) {
    add(agent.position[0], agent.position[1], "agents", agent);
  }
  for (const object of objects) {
    add(object.position[0], object.position[1], "objects", object);
  }
  return byPos;
}

function createChip(entity, kind, isActive) {
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

function renderGrid(data) {
  const { grid, agents, objects, active_agent_id } = data;
  const byPos = indexEntities(agents, objects);

  const width = grid.max_x - grid.min_x + 1;

  gridEl.style.setProperty("--grid-cols", String(width));
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
      for (const agent of at.agents) {
        stack.appendChild(createChip(agent, "agent", agent.id === active_agent_id));
      }
      for (const object of at.objects) {
        stack.appendChild(createChip(object, "object", false));
      }

      tile.appendChild(stack);
      gridEl.appendChild(tile);
    }
  }
}

function renderSessionMeta(data) {
  const active = data.agents.find((a) => a.id === data.active_agent_id);
  const activeLabel = active ? `${active.name} (${active.id})` : data.active_agent_id;

  sessionMetaEl.innerHTML = `
    <dt>Session turn</dt><dd>${data.session_turn}</dd>
    <dt>Active agent</dt><dd>${escapeHtml(activeLabel)}</dd>
    <dt>Agents</dt><dd>${data.agents.length}</dd>
    <dt>Objects</dt><dd>${data.objects.length}</dd>
  `;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderSidebarPanels(data) {
  renderPassiveVision(data, passiveVisionEl, passiveVisionEmptyEl);
  renderRecentEvents(data, recentEventsEl, recentEventsEmptyEl);
}

function renderState(data) {
  lastSnapshot = data;
  renderGrid(data);
  renderSessionMeta(data);
  renderSidebarPanels(data);
  renderActiveAgentSelect(activeAgentSelect, data);
  snapshotEl.textContent = JSON.stringify(data, null, 2);
}

async function fetchState() {
  statusEl.textContent = "Fetching…";
  try {
    const data = await getState();
    renderState(data);
    updateStatusLine(data);
  } catch (err) {
    gridEl.innerHTML = "";
    snapshotEl.textContent = String(err);
    statusEl.textContent = "Error";
  }
}

function updateStatusLine(data) {
  const active = data.agents.find((a) => a.id === data.active_agent_id);
  statusEl.textContent = `Turn ${data.session_turn} — ${active ? active.name : data.active_agent_id}`;
}

function recordTurnResult(result) {
  const snap = result.snapshot || lastSnapshot;
  const active = snap?.agents?.find((a) => a.id === snap.active_agent_id);
  appendTurnLogEntry({
    sessionTurn: snap?.session_turn ?? "?",
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
    updateStatusLine(snapshot);
    return;
  }
  await fetchState();
}

initUi({
  getSnapshotFn: () => lastSnapshot,
  onStateChangedFn: refreshAfterMutation,
});
bindGridContextMenu(gridEl);
bindActiveAgentSelect(activeAgentSelect, refreshAfterMutation);
bindEmitEventButton(emitEventBtn);
bindPromptDebug(promptDebugEl, lastPromptEl, lastPromptEmptyEl, () => getPrompt());

document.getElementById("refresh").addEventListener("click", fetchState);
runTurnBtn.addEventListener("click", runTurn);
renderTurnLog(turnLogEl, turnLogEmptyEl);
fetchState();
