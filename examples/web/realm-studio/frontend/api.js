/** HTTP helpers for realm-studio API. */

export async function getState() {
  const res = await fetch("/api/state");
  if (!res.ok) {
    throw new Error(`GET /api/state failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function postCommand(line) {
  const res = await fetch("/api/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ line }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function postActiveAgent(nameOrId) {
  const res = await fetch("/api/active-agent", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name_or_id: nameOrId }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function postActiveArea(areaId) {
  const res = await fetch("/api/active-area", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ area_id: areaId }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function postCreateArea({ areaId, description, width, height }) {
  const res = await fetch("/api/create-area", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      area_id: areaId,
      description: description ?? "",
      width: Number(width),
      height: Number(height),
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function postEditArea({ areaId, description, width, height }) {
  const res = await fetch("/api/edit-area", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      area_id: areaId,
      description,
      width: width !== "" && width !== undefined ? Number(width) : undefined,
      height: height !== "" && height !== undefined ? Number(height) : undefined,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function postDeleteArea(areaId) {
  const res = await fetch("/api/delete-area", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ area_id: areaId }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function postTurn({ agentId, includeExamples } = {}) {
  const body = {};
  if (agentId) body.agent_id = agentId;
  if (includeExamples !== undefined) body.include_examples = includeExamples;

  const res = await fetch("/api/turn", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function postEvent(text) {
  const res = await fetch("/api/event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function getPrompt(agentId) {
  const params = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : "";
  const res = await fetch(`/api/prompt${params}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function getPromptBlocks(agentId) {
  const params = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : "";
  const res = await fetch(`/api/prompt-blocks${params}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function putPromptBlocks(blocks) {
  const res = await fetch("/api/prompt-blocks", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ blocks }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function resetPromptBlocks() {
  const res = await fetch("/api/prompt-blocks/reset", { method: "POST" });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function getPromptSlots(agentId) {
  const params = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : "";
  const res = await fetch(`/api/prompt-slots${params}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function getPromptBlockCatalog() {
  const res = await fetch("/api/prompt-block-catalog");
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function putVisionUnits({ units, units_per_tile }) {
  const res = await fetch("/api/vision-units", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ units, units_per_tile }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

export async function previewPromptBlocks(blocks, agentId) {
  const body = { blocks };
  if (agentId) body.agent_id = agentId;
  const res = await fetch("/api/prompt-blocks/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }
  return data;
}

/** CLI-safe double-quoted string (v1: strip embedded quotes). */
export function cliQuote(value) {
  const text = String(value ?? "").replace(/"/g, "'");
  return `"${text}"`;
}

export function buildCreateObject({ name, pdesc, desc, appearance, x, y, withEat }) {
  let line =
    `create-object name ${cliQuote(name)} pdesc ${cliQuote(pdesc)} ` +
    `desc ${cliQuote(desc)} at ${x},${y}`;
  if (appearance) {
    line += ` appearance ${cliQuote(appearance)}`;
  }
  if (withEat) {
    line +=
      " action eat range 0 effect delete_self " +
      `result ${cliQuote("You ate it.")} passive ${cliQuote("{actor} ate it.")}`;
  }
  return line;
}

export async function getMemoryModules() {
  const res = await fetch("/api/memory-modules");
  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error(data.message || `GET /api/memory-modules failed: HTTP ${res.status}`);
  }
  return data;
}

const MEMORY_OPTION_FLAGS = {
  memoryWindow: "memory-window",
  memoryBudget: "memory-budget",
  memorySummaryInterval: "memory-summary-interval",
  memorySummaryMax: "memory-summary-max",
  memorySummaryTail: "memory-summary-tail",
};

function hasMemoryCliOptions(memoryOptions) {
  return Object.values(memoryOptions).some(
    (value) => value !== undefined && value !== null && String(value).trim() !== "",
  );
}

export function memoryOptionFieldName(flag) {
  const entry = Object.entries(MEMORY_OPTION_FLAGS).find(([, cliFlag]) => cliFlag === flag);
  return entry ? entry[0] : flag.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
}

export function buildCreateAgent({
  name,
  pdesc,
  desc,
  personality,
  appearance,
  moveSpeed,
  memoryModule,
  memoryOptions = {},
  x,
  y,
}) {
  let line =
    `create-agent name ${cliQuote(name)} pdesc ${cliQuote(pdesc)} ` +
    `desc ${cliQuote(desc)} personality ${cliQuote(personality)} at ${x},${y}`;
  if (appearance) {
    line += ` appearance ${cliQuote(appearance)}`;
  }
  if (moveSpeed) {
    line += ` move-speed ${moveSpeed}`;
  }
  const moduleId = String(memoryModule ?? "").trim() || "recent_turns";
  if (moduleId !== "recent_turns") {
    line += ` memory ${moduleId}`;
  } else if (hasMemoryCliOptions(memoryOptions)) {
    line += " memory recent_turns";
  }
  for (const [field, flag] of Object.entries(MEMORY_OPTION_FLAGS)) {
    const value = memoryOptions[field];
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      line += ` ${flag} ${String(value).trim()}`;
    }
  }
  return line;
}

export function buildEditObject({
  id,
  name,
  pdesc,
  desc,
  appearance,
  areaId,
  sourceAreaId,
  x,
  y,
}) {
  const parts = [`edit-object ${id}`];
  if (name) parts.push(`name ${cliQuote(name)}`);
  if (pdesc) parts.push(`pdesc ${cliQuote(pdesc)}`);
  if (desc) parts.push(`desc ${cliQuote(desc)}`);
  if (appearance !== undefined) parts.push(`appearance ${cliQuote(appearance)}`);
  const targetArea = String(areaId ?? "").trim();
  const originArea = String(sourceAreaId ?? "").trim();
  if (targetArea && originArea && targetArea !== originArea) {
    parts.push(`area ${targetArea}`);
  }
  parts.push(`pos ${x},${y}`);
  return parts.join(" ");
}

export function buildEditAgent({
  id,
  name,
  pdesc,
  desc,
  personality,
  appearance,
  moveSpeed,
  areaId,
  sourceAreaId,
  x,
  y,
}) {
  const parts = [`edit-agent ${id}`];
  if (name) parts.push(`name ${cliQuote(name)}`);
  if (pdesc) parts.push(`pdesc ${cliQuote(pdesc)}`);
  if (desc) parts.push(`desc ${cliQuote(desc)}`);
  if (personality) parts.push(`personality ${cliQuote(personality)}`);
  if (appearance !== undefined) parts.push(`appearance ${cliQuote(appearance)}`);
  if (moveSpeed !== undefined) {
    if (moveSpeed === "") {
      parts.push('move-speed ""');
    } else {
      parts.push(`move-speed ${moveSpeed}`);
    }
  }
  const targetArea = String(areaId ?? "").trim();
  const originArea = String(sourceAreaId ?? "").trim();
  if (targetArea && originArea && targetArea !== originArea) {
    parts.push(`area ${targetArea}`);
  }
  parts.push(`pos ${x},${y}`);
  return parts.join(" ");
}

export function buildCreateArea({ id, desc, width, height }) {
  let line = `create-area id ${id}`;
  if (desc) line += ` desc ${cliQuote(desc)}`;
  line += ` width ${width} height ${height}`;
  return line;
}

export function buildEditArea({ id, desc, width, height }) {
  const parts = [`edit-area ${id}`];
  if (desc !== undefined && desc !== "") parts.push(`desc ${cliQuote(desc)}`);
  if (width) parts.push(`width ${width}`);
  if (height) parts.push(`height ${height}`);
  return parts.join(" ");
}

export function buildDeleteArea(id) {
  return `delete-area ${id}`;
}

export function buildAddObjectAction(objectId, {
  name,
  range,
  result,
  passive,
  effect,
  destArea,
  destX,
  destY,
}) {
  const parts = [`edit-object ${objectId} add-action ${name} range ${range}`];
  if (effect && effect !== "none") {
    parts.push(`effect ${effect}`);
    if (effect === "move_area") {
      parts.push(`dest-area ${destArea}`, `dest-at ${destX},${destY}`);
    }
  }
  parts.push(`result ${cliQuote(result)}`, `passive ${cliQuote(passive)}`);
  return parts.join(" ");
}

export function buildRemoveObjectAction(objectId, actionName) {
  return `edit-object ${objectId} remove-action ${actionName}`;
}
