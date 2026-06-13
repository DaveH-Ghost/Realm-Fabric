/**
 * realm-studio frontend — grid render from Session.snapshot() (V0.3.1b).
 */

const statusEl = document.getElementById("status");
const gridEl = document.getElementById("grid");
const snapshotEl = document.getElementById("snapshot");
const sessionMetaEl = document.getElementById("session-meta");

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
    <dt>Turn</dt><dd>${data.session_turn}</dd>
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

function renderState(data) {
  renderGrid(data);
  renderSessionMeta(data);
  snapshotEl.textContent = JSON.stringify(data, null, 2);
}

async function fetchState() {
  statusEl.textContent = "Fetching…";
  try {
    const res = await fetch("/api/state");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    renderState(data);
    const active = data.agents.find((a) => a.id === data.active_agent_id);
    statusEl.textContent = `Turn ${data.session_turn} — ${active ? active.name : data.active_agent_id}`;
  } catch (err) {
    gridEl.innerHTML = "";
    snapshotEl.textContent = String(err);
    statusEl.textContent = "Error";
  }
}

document.getElementById("refresh").addEventListener("click", fetchState);
fetchState();
