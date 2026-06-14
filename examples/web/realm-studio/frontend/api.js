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

export function buildCreateAgent({
  name,
  pdesc,
  desc,
  personality,
  appearance,
  moveSpeed,
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
  return line;
}

export function buildEditObject({ id, name, pdesc, desc, appearance, x, y }) {
  const parts = [`edit-object ${id}`];
  if (name) parts.push(`name ${cliQuote(name)}`);
  if (pdesc) parts.push(`pdesc ${cliQuote(pdesc)}`);
  if (desc) parts.push(`desc ${cliQuote(desc)}`);
  if (appearance !== undefined) parts.push(`appearance ${cliQuote(appearance)}`);
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
