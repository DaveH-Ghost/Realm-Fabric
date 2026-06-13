/** HTTP helpers for realm-studio API (V0.3.1c). */

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

/** CLI-safe double-quoted string (v1: strip embedded quotes). */
export function cliQuote(value) {
  const text = String(value ?? "").replace(/"/g, "'");
  return `"${text}"`;
}

export function buildCreateObject({ name, pdesc, desc, x, y, withEat }) {
  let line =
    `create-object name ${cliQuote(name)} pdesc ${cliQuote(pdesc)} ` +
    `desc ${cliQuote(desc)} at ${x},${y}`;
  if (withEat) {
    line +=
      " action eat range 0 effect delete_self " +
      `result ${cliQuote("You ate it.")} passive ${cliQuote("{actor} ate it.")}`;
  }
  return line;
}

export function buildCreateAgent({ name, pdesc, desc, personality, x, y }) {
  return (
    `create-agent name ${cliQuote(name)} pdesc ${cliQuote(pdesc)} ` +
    `desc ${cliQuote(desc)} personality ${cliQuote(personality)} at ${x},${y}`
  );
}

export function buildEditObject({ id, name, pdesc, desc, x, y }) {
  const parts = [`edit-object ${id}`];
  if (name) parts.push(`name ${cliQuote(name)}`);
  if (pdesc) parts.push(`pdesc ${cliQuote(pdesc)}`);
  if (desc) parts.push(`desc ${cliQuote(desc)}`);
  parts.push(`pos ${x},${y}`);
  return parts.join(" ");
}

export function buildEditAgent({ id, name, pdesc, desc, personality, x, y }) {
  const parts = [`edit-agent ${id}`];
  if (name) parts.push(`name ${cliQuote(name)}`);
  if (pdesc) parts.push(`pdesc ${cliQuote(pdesc)}`);
  if (desc) parts.push(`desc ${cliQuote(desc)}`);
  if (personality) parts.push(`personality ${cliQuote(personality)}`);
  parts.push(`pos ${x},${y}`);
  return parts.join(" ");
}
