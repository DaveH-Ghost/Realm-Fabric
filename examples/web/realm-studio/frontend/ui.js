/**
 * Context menu, modals, toast (V0.3.1c).
 */

import {
  buildCreateAgent,
  buildCreateObject,
  buildEditAgent,
  buildEditObject,
  postActiveAgent,
  postCommand,
  postEvent,
} from "./api.js";

let menuEl;
let modalBackdrop;
let modalTitle;
let modalForm;
let modalError;
let toastEl;
let getSnapshot = () => null;
let onStateChanged = async () => {};

export function initUi({ getSnapshotFn, onStateChangedFn }) {
  getSnapshot = getSnapshotFn;
  onStateChanged = onStateChangedFn;

  menuEl = document.getElementById("context-menu");
  modalBackdrop = document.getElementById("modal-backdrop");
  modalTitle = document.getElementById("modal-title");
  modalForm = document.getElementById("modal-form");
  modalError = document.getElementById("modal-error");
  toastEl = document.getElementById("toast");

  document.getElementById("modal-cancel").addEventListener("click", closeModal);
  document.getElementById("modal-backdrop").addEventListener("click", (e) => {
    if (e.target === modalBackdrop) closeModal();
  });
  document.addEventListener("click", () => hideMenu());
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      hideMenu();
      closeModal();
    }
  });
}

export function bindGridContextMenu(gridEl) {
  gridEl.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    hideMenu();

    const marker = e.target.closest(".chip, .token");
    if (marker) {
      showEntityMenu(e.clientX, e.clientY, marker.dataset.kind, marker.dataset.id);
      return;
    }

    const tile = e.target.closest(".tile");
    if (!tile) return;

    const x = Number(tile.dataset.x);
    const y = Number(tile.dataset.y);
    const at = entitiesAt(x, y);
    const count = at.agents.length + at.objects.length;

    if (count > 1) {
      showManageTileMenu(e.clientX, e.clientY, x, y, at);
    } else if (count === 0) {
      showEmptyTileMenu(e.clientX, e.clientY, x, y);
    } else {
      const entity = at.agents[0] || at.objects[0];
      const kind = at.agents.length ? "agent" : "object";
      showEntityMenu(e.clientX, e.clientY, kind, entity.id);
    }
  });
}

function entitiesAt(x, y) {
  const snap = getSnapshot();
  if (!snap) return { agents: [], objects: [] };
  const agents = snap.agents.filter(
    (a) => a.position[0] === x && a.position[1] === y,
  );
  const objects = snap.objects.filter(
    (o) => o.position[0] === x && o.position[1] === y,
  );
  return { agents, objects };
}

function findEntity(kind, id) {
  const snap = getSnapshot();
  if (!snap) return null;
  const list = kind === "agent" ? snap.agents : snap.objects;
  return list.find((e) => e.id === id) || null;
}

function showMenu(x, y, items) {
  menuEl.innerHTML = "";
  for (const item of items) {
    if (item.separator) {
      const sep = document.createElement("div");
      sep.className = "context-menu-sep";
      menuEl.appendChild(sep);
      continue;
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "context-menu-item";
    btn.textContent = item.label;
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      hideMenu();
      item.action();
    });
    menuEl.appendChild(btn);
  }
  menuEl.classList.remove("hidden");
  menuEl.style.left = `${x}px`;
  menuEl.style.top = `${y}px`;
}

function hideMenu() {
  menuEl.classList.add("hidden");
}

function showEmptyTileMenu(x, y, tileX, tileY) {
  showMenu(x, y, [
    {
      label: "Create object here…",
      action: () => openCreateObjectModal(tileX, tileY),
    },
    {
      label: "Create agent here…",
      action: () => openCreateAgentModal(tileX, tileY),
    },
  ]);
}

function showManageTileMenu(x, y, tileX, tileY, at) {
  const items = [
    {
      label: "Create object here…",
      action: () => openCreateObjectModal(tileX, tileY),
    },
    {
      label: "Create agent here…",
      action: () => openCreateAgentModal(tileX, tileY),
    },
    { separator: true },
  ];
  for (const agent of at.agents) {
    items.push({
      label: `Agent: ${agent.name}`,
      action: () => showEntityMenu(x, y, "agent", agent.id),
    });
  }
  for (const object of at.objects) {
    items.push({
      label: `Object: ${object.name}`,
      action: () => showEntityMenu(x, y, "object", object.id),
    });
  }
  showMenu(x, y, items);
}

function showEntityMenu(x, y, kind, id) {
  const entity = findEntity(kind, id);
  if (!entity) return;

  if (kind === "agent") {
    showMenu(x, y, [
      {
        label: "Play as this agent",
        action: () => runActiveAgent(entity.id),
      },
      { label: "Edit…", action: () => openEditAgentModal(entity) },
      {
        label: "Delete",
        action: () => runDelete(`delete-agent ${entity.id}`, entity.name),
      },
    ]);
  } else {
    showMenu(x, y, [
      { label: "Edit…", action: () => openEditObjectModal(entity) },
      {
        label: "Delete",
        action: () => runDelete(`delete-object ${entity.id}`, entity.name),
      },
    ]);
  }
}

async function runCommand(line) {
  const result = await postCommand(line);
  if (!result.ok) {
    showToast(result.message, true);
    return result;
  }
  showToast(result.message, false);
  await onStateChanged();
  return result;
}

async function runActiveAgent(nameOrId) {
  const result = await postActiveAgent(nameOrId);
  if (!result.ok) {
    showToast(result.message, true);
    return;
  }
  showToast(result.message, false);
  await onStateChanged();
}

async function runDelete(line, name) {
  if (!window.confirm(`Delete ${name}?`)) return;
  await runCommand(line);
}

function showToast(message, isError) {
  toastEl.textContent = message;
  toastEl.classList.toggle("toast-error", isError);
  toastEl.classList.remove("hidden");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => toastEl.classList.add("hidden"), 4000);
}

function closeModal() {
  modalBackdrop.classList.add("hidden");
  modalForm.innerHTML = "";
  modalError.textContent = "";
}

function openModal(title, fields, onSubmit, { submitLabel = "Save" } = {}) {
  modalTitle.textContent = title;
  modalForm.innerHTML = "";
  modalError.textContent = "";

  for (const field of fields) {
    const wrap = document.createElement("label");
    wrap.className = "modal-field";
    const label = document.createElement("span");
    label.textContent = field.label;
    wrap.appendChild(label);

    let input;
    if (field.type === "checkbox") {
      input = document.createElement("input");
      input.type = "checkbox";
      input.checked = !!field.value;
    } else if (field.type === "textarea") {
      input = document.createElement("textarea");
      input.rows = field.rows || 2;
      input.value = field.value ?? "";
    } else {
      input = document.createElement("input");
      input.type = field.type || "text";
      input.value = field.value ?? "";
    }
    input.name = field.name;
    if (field.required) input.required = true;
    if (field.placeholder) input.placeholder = field.placeholder;
    wrap.appendChild(input);
    modalForm.appendChild(wrap);
  }

  const actions = document.createElement("div");
  actions.className = "modal-actions";
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = submitLabel;
  actions.appendChild(submit);
  modalForm.appendChild(actions);

  modalForm.onsubmit = async (e) => {
    e.preventDefault();
    modalError.textContent = "";
    const data = {};
    for (const field of fields) {
      const el = modalForm.elements[field.name];
      data[field.name] =
        field.type === "checkbox" ? el.checked : el.value.trim();
    }
    try {
      await onSubmit(data);
      closeModal();
    } catch (err) {
      modalError.textContent = String(err.message || err);
    }
  };

  modalBackdrop.classList.remove("hidden");
}

function openCreateObjectModal(x, y) {
  openModal("Create object", [
    { name: "name", label: "Name", value: "New Object", required: true },
    { name: "pdesc", label: "Passive description", value: "An object.", type: "textarea" },
    { name: "desc", label: "Detailed description", value: "A new object.", type: "textarea" },
    {
      name: "appearance",
      label: "Token image path",
      value: "",
      placeholder: "tokens/my-object.svg",
    },
    { name: "x", label: "X", value: String(x), type: "number", required: true },
    { name: "y", label: "Y", value: String(y), type: "number", required: true },
    { name: "withEat", label: "Add eat action (same tile)", type: "checkbox", value: false },
  ], async (data) => {
    const line = buildCreateObject({
      name: data.name,
      pdesc: data.pdesc,
      desc: data.desc,
      appearance: data.appearance,
      x: data.x,
      y: data.y,
      withEat: data.withEat,
    });
    const result = await postCommand(line);
    if (!result.ok) throw new Error(result.message);
    showToast(result.message, false);
    await onStateChanged();
  });
}

function openCreateAgentModal(x, y) {
  openModal("Create agent", [
    { name: "name", label: "Name", value: "New Agent", required: true },
    { name: "pdesc", label: "Passive description", value: "A figure.", type: "textarea" },
    { name: "desc", label: "Detailed description", value: "A new agent.", type: "textarea" },
    {
      name: "personality",
      label: "Personality (LLM)",
      value: "You are a calm agent in a small room.",
      type: "textarea",
    },
    {
      name: "appearance",
      label: "Token image path",
      value: "",
      placeholder: "tokens/my-agent.svg",
    },
    {
      name: "moveSpeed",
      label: "Move speed (steps per turn)",
      value: "",
      type: "number",
      placeholder: "blank = unlimited (teleport)",
    },
    { name: "x", label: "X", value: String(x), type: "number", required: true },
    { name: "y", label: "Y", value: String(y), type: "number", required: true },
  ], async (data) => {
    const line = buildCreateAgent({
      name: data.name,
      pdesc: data.pdesc,
      desc: data.desc,
      personality: data.personality,
      appearance: data.appearance,
      moveSpeed: data.moveSpeed,
      x: data.x,
      y: data.y,
    });
    const result = await postCommand(line);
    if (!result.ok) throw new Error(result.message);
    showToast(result.message, false);
    await onStateChanged();
  });
}

function openEditObjectModal(entity) {
  openModal(`Edit object — ${entity.name}`, [
    { name: "name", label: "Name", value: entity.name, required: true },
    {
      name: "pdesc",
      label: "Passive description",
      value: entity.passive_description ?? "",
      type: "textarea",
    },
    {
      name: "desc",
      label: "Detailed description",
      value: entity.description ?? "",
      type: "textarea",
    },
    {
      name: "appearance",
      label: "Token image path",
      value: entity.appearance ?? "",
      placeholder: "tokens/my-object.svg",
    },
    {
      name: "x",
      label: "X",
      value: String(entity.position[0]),
      type: "number",
      required: true,
    },
    {
      name: "y",
      label: "Y",
      value: String(entity.position[1]),
      type: "number",
      required: true,
    },
  ], async (data) => {
    const line = buildEditObject({
      id: entity.id,
      name: data.name,
      pdesc: data.pdesc || undefined,
      desc: data.desc || undefined,
      appearance: data.appearance,
      x: data.x,
      y: data.y,
    });
    const result = await postCommand(line);
    if (!result.ok) throw new Error(result.message);
    showToast(result.message, false);
    await onStateChanged();
  });
}

function openEditAgentModal(entity) {
  openModal(`Edit agent — ${entity.name}`, [
    { name: "name", label: "Name", value: entity.name, required: true },
    {
      name: "pdesc",
      label: "Passive description",
      value: entity.passive_description ?? "",
      type: "textarea",
    },
    {
      name: "desc",
      label: "Detailed description",
      value: entity.description ?? "",
      type: "textarea",
    },
    {
      name: "personality",
      label: "Personality (LLM)",
      value: entity.personality ?? "",
      type: "textarea",
    },
    {
      name: "appearance",
      label: "Token image path",
      value: entity.appearance ?? "",
      placeholder: "tokens/my-agent.svg",
    },
    {
      name: "moveSpeed",
      label: "Move speed (steps per turn)",
      value: entity.move_speed != null ? String(entity.move_speed) : "",
      type: "number",
      placeholder: "blank = unlimited (teleport)",
    },
    {
      name: "x",
      label: "X",
      value: String(entity.position[0]),
      type: "number",
      required: true,
    },
    {
      name: "y",
      label: "Y",
      value: String(entity.position[1]),
      type: "number",
      required: true,
    },
  ], async (data) => {
    const line = buildEditAgent({
      id: entity.id,
      name: data.name,
      pdesc: data.pdesc || undefined,
      desc: data.desc || undefined,
      personality: data.personality || undefined,
      appearance: data.appearance,
      moveSpeed: data.moveSpeed,
      x: data.x,
      y: data.y,
    });
    const result = await postCommand(line);
    if (!result.ok) throw new Error(result.message);
    showToast(result.message, false);
    await onStateChanged();
  });
}

export function bindEmitEventButton(buttonEl) {
  buttonEl.addEventListener("click", () => openEmitEventModal());
}

function openEmitEventModal() {
  openModal(
    "Emit area event",
    [
      {
        name: "text",
        label: "Event text (all agents will remember this)",
        value: "Thunder rumbles overhead.",
        type: "textarea",
        rows: 3,
        required: true,
      },
    ],
    async (data) => {
      const result = await postEvent(data.text);
      if (!result.ok) throw new Error(result.message);
      showToast(result.message, false);
      await onStateChanged(result.snapshot);
    },
    { submitLabel: "Emit" },
  );
}

export function bindActiveAgentSelect(selectEl, onChange) {
  selectEl.addEventListener("change", async () => {
    const value = selectEl.value;
    if (!value) return;
    try {
      const result = await postActiveAgent(value);
      if (!result.ok) {
        showToast(result.message, true);
        return;
      }
      showToast(result.message, false);
      await onChange();
    } catch (err) {
      showToast(String(err.message || err), true);
    }
  });
}

export function renderActiveAgentSelect(selectEl, snapshot) {
  const current = selectEl.value;
  selectEl.innerHTML = "";
  for (const agent of snapshot.agents) {
    const opt = document.createElement("option");
    opt.value = agent.id;
    opt.textContent = `${agent.name} (${agent.id})`;
    if (agent.id === snapshot.active_agent_id) opt.selected = true;
    selectEl.appendChild(opt);
  }
  if (current && [...selectEl.options].some((o) => o.value === current)) {
    selectEl.value = current;
  }
}

export { showToast };
