/**
 * Context menu, modals, toast (V0.3.1c).
 */

import {
  buildCreateAgent,
  buildCreateObject,
  buildEditAgent,
  buildEditObject,
  getMemoryModules,
  memoryOptionFieldName,
  postActiveAgent,
  postActiveArea,
  postCommand,
  postCreateArea,
  postDeleteArea,
  postEditArea,
  postEvent,
} from "./api.js";
import { activeAreaView, asArray, DEFAULT_AREA_ID, normalizeSnapshot } from "./snapshot.js";
import { initObjectActions, openManageObjectActionsModal } from "./objectActions.js";

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

  initObjectActions({
    getSnapshotFn: getSnapshot,
    onStateChangedFn: onStateChanged,
    showToastFn: showToast,
    modalTitleEl: modalTitle,
    modalFormEl: modalForm,
    modalErrorEl: modalError,
    modalBackdropEl: modalBackdrop,
    closeModal,
  });

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
  const snap = activeAreaView(getSnapshot());
  if (!snap?.grid) return { agents: [], objects: [] };
  const agents = asArray(snap.agents).filter(
    (a) => a.position[0] === x && a.position[1] === y,
  );
  const objects = asArray(snap.objects).filter(
    (o) => o.position[0] === x && o.position[1] === y,
  );
  return { agents, objects };
}

function findEntity(kind, id) {
  const snap = activeAreaView(getSnapshot());
  if (!snap) return null;
  const list = kind === "agent" ? asArray(snap.agents) : asArray(snap.objects);
  return list.find((e) => e.id === id) || null;
}

function findAgentWithArea(agentId) {
  const snap = normalizeSnapshot(getSnapshot());
  const entity = asArray(snap?.agents).find((a) => a.id === agentId);
  if (!entity) return null;
  const areaId =
    entity.area_id ?? activeAreaView(getSnapshot())?.active_area_id ?? DEFAULT_AREA_ID;
  return { entity, areaId };
}

function findObjectWithArea(objectId) {
  const snap = normalizeSnapshot(getSnapshot());
  if (!snap?.areas) return null;
  for (const [areaId, block] of Object.entries(snap.areas)) {
    const entity = asArray(block.objects).find((o) => o.id === objectId);
    if (entity) {
      return { entity, areaId };
    }
  }
  return null;
}

function listAreaOptions() {
  const snap = normalizeSnapshot(getSnapshot());
  return Object.keys(snap?.areas ?? {})
    .sort()
    .map((areaId) => ({ value: areaId, label: areaId }));
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
  for (const agent of asArray(at.agents)) {
    items.push({
      label: `Agent: ${agent.name}`,
      action: () => showEntityMenu(x, y, "agent", agent.id),
    });
  }
  for (const object of asArray(at.objects)) {
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
    const agentCtx =
      findAgentWithArea(id) ?? { entity, areaId: activeAreaView(getSnapshot())?.active_area_id };
    showMenu(x, y, [
      {
        label: "Play as this agent",
        action: () => runActiveAgent(entity.id),
      },
      {
        label: "Edit…",
        action: () => openEditAgentModal(agentCtx.entity, agentCtx.areaId),
      },
      {
        label: "Delete",
        action: () => runDelete(`delete-agent ${entity.id}`, entity.name),
      },
    ]);
  } else {
    const objectCtx = findObjectWithArea(id) ?? { entity, areaId: activeAreaView(getSnapshot())?.active_area_id };
    showMenu(x, y, [
      {
        label: "Edit…",
        action: () => openEditObjectModal(objectCtx.entity, objectCtx.areaId),
      },
      { label: "Manage actions…", action: () => openManageObjectActionsModal(entity) },
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
  await onStateChanged(result.snapshot);
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

function syncConditionalModalFields(form) {
  const conditional = form.querySelectorAll(".modal-field-conditional");
  for (const wrap of conditional) {
    const triggerName = wrap.dataset.showWhenField;
    const allowed = (wrap.dataset.showWhenValues || "")
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean);
    const trigger = form.elements[triggerName];
    const current = trigger?.type === "checkbox" ? trigger.checked : trigger?.value;
    wrap.hidden = !allowed.includes(String(current));
  }
}

function ensureAdvancedSection(form) {
  let details = form.querySelector(".modal-advanced");
  if (!details) {
    details = document.createElement("details");
    details.className = "modal-advanced";
    const summary = document.createElement("summary");
    summary.textContent = "Advanced";
    details.appendChild(summary);
    const body = document.createElement("div");
    body.className = "modal-advanced-body";
    details.appendChild(body);
    form.appendChild(details);
  }
  return details.querySelector(".modal-advanced-body");
}

function ensureLocationSection(form) {
  let details = form.querySelector(".modal-location");
  if (!details) {
    details = document.createElement("details");
    details.className = "modal-location";
    const summary = document.createElement("summary");
    summary.textContent = "Location";
    details.appendChild(summary);
    const body = document.createElement("div");
    body.className = "modal-location-body";
    details.appendChild(body);
    form.appendChild(details);
  }
  return details.querySelector(".modal-location-body");
}

function appendModalField(form, field) {
  if (field.type === "context") {
    const context = document.createElement("p");
    context.className = "modal-context";
    context.textContent = field.text ?? "";
    form.appendChild(context);
    return;
  }

  const wrap = document.createElement("label");
  wrap.className = "modal-field";
  if (field.showWhen) {
    wrap.classList.add("modal-field-conditional");
    wrap.dataset.showWhenField = field.showWhen.field;
    wrap.dataset.showWhenValues = field.showWhen.values.join(",");
  }
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
  } else if (field.type === "select") {
    input = document.createElement("select");
    for (const opt of field.options || []) {
      const option = document.createElement("option");
      option.value = opt.value;
      option.textContent = opt.label;
      if (String(opt.value) === String(field.value ?? "")) {
        option.selected = true;
      }
      input.appendChild(option);
    }
  } else if (field.type === "readonly") {
    input = document.createElement("input");
    input.type = "text";
    input.value = field.value ?? "";
    input.readOnly = true;
    input.className = "modal-readonly";
  } else {
    input = document.createElement("input");
    input.type = field.type || "text";
    input.value = field.value ?? "";
  }
  input.name = field.name;
  if (field.required) input.required = true;
  if (field.placeholder) input.placeholder = field.placeholder;
  wrap.appendChild(input);

  const parent = field.location
    ? ensureLocationSection(form)
    : field.advanced
      ? ensureAdvancedSection(form)
      : form;
  parent.appendChild(wrap);
}

function openModal(title, fields, onSubmit, { submitLabel = "Save" } = {}) {
  modalTitle.textContent = title;
  modalForm.innerHTML = "";
  modalError.textContent = "";

  for (const field of fields) {
    appendModalField(modalForm, field);
  }

  syncConditionalModalFields(modalForm);
  for (const el of modalForm.querySelectorAll("select, input[type=checkbox]")) {
    el.addEventListener("change", () => syncConditionalModalFields(modalForm));
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
      if (field.type === "context" || field.type === "readonly" || !field.name) continue;
      const el = modalForm.elements[field.name];
      if (!el) continue;
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
  void (async () => {
    let catalog;
    try {
      catalog = await getMemoryModules();
    } catch (err) {
      showToast(String(err.message || err), true);
      return;
    }

    const fields = [
      { name: "name", label: "Name", value: "New Agent", required: true },
      {
        name: "personality",
        label: "Personality (LLM)",
        value: "You are a calm agent in a small room.",
        type: "textarea",
        rows: 2,
      },
      {
        name: "memoryModule",
        label: "Memory module",
        type: "select",
        value: catalog.default_id,
        options: catalog.modules.map((mod) => ({
          value: mod.id,
          label: mod.label || mod.id,
        })),
      },
      { type: "context", text: `Creating at (${x}, ${y})` },
      {
        name: "pdesc",
        label: "Passive description",
        value: "A figure.",
        type: "textarea",
        advanced: true,
      },
      {
        name: "desc",
        label: "Detailed description",
        value: "A new agent.",
        type: "textarea",
        advanced: true,
      },
      {
        name: "appearance",
        label: "Token image path",
        value: "",
        placeholder: "tokens/my-agent.svg",
        advanced: true,
      },
      {
        name: "moveSpeed",
        label: "Move speed (steps per turn)",
        value: "",
        type: "number",
        placeholder: "blank = unlimited (teleport)",
        advanced: true,
      },
    ];

    const memoryOptionFields = [];
    for (const mod of catalog.modules) {
      for (const opt of mod.options || []) {
        const placeholder =
          opt.max != null ? `${opt.min}–${opt.max}` : `${opt.min}+`;
        memoryOptionFields.push({
          name: memoryOptionFieldName(opt.flag),
          label: opt.label,
          type: "number",
          value: String(opt.default),
          placeholder,
          showWhen: { field: "memoryModule", values: [mod.id] },
        });
      }
    }
    const memoryIndex = fields.findIndex((field) => field.name === "memoryModule") + 1;
    fields.splice(memoryIndex, 0, ...memoryOptionFields);

    openModal("Create agent", fields, async (data) => {
      const selectedModule = catalog.modules.find((mod) => mod.id === data.memoryModule);
      const memoryOptions = {};
      for (const opt of selectedModule?.options || []) {
        const key = memoryOptionFieldName(opt.flag);
        if (data[key]) memoryOptions[key] = data[key];
      }
      const line = buildCreateAgent({
        name: data.name,
        pdesc: data.pdesc,
        desc: data.desc,
        personality: data.personality,
        appearance: data.appearance,
        moveSpeed: data.moveSpeed,
        memoryModule: data.memoryModule,
        memoryOptions,
        x,
        y,
      });
      const result = await postCommand(line);
      if (!result.ok) throw new Error(result.message);
      showToast(result.message, false);
      await onStateChanged();
    });
  })();
}

function openEditObjectModal(entity, areaId) {
  const resolvedAreaId =
    areaId ?? activeAreaView(getSnapshot())?.active_area_id ?? DEFAULT_AREA_ID;
  const areaOptions = listAreaOptions();

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
      name: "areaId",
      label: "Area",
      type: "select",
      value: resolvedAreaId,
      options: areaOptions,
      location: true,
    },
    {
      name: "x",
      label: "X",
      value: String(entity.position[0]),
      type: "number",
      required: true,
      location: true,
    },
    {
      name: "y",
      label: "Y",
      value: String(entity.position[1]),
      type: "number",
      required: true,
      location: true,
    },
  ], async (data) => {
    const line = buildEditObject({
      id: entity.id,
      name: data.name,
      pdesc: data.pdesc || undefined,
      desc: data.desc || undefined,
      appearance: data.appearance,
      areaId: data.areaId,
      sourceAreaId: resolvedAreaId,
      x: data.x,
      y: data.y,
    });
    const result = await postCommand(line);
    if (!result.ok) throw new Error(result.message);
    showToast(result.message, false);
    await onStateChanged();
  });
}

function openEditAgentModal(entity, areaId) {
  const resolvedAreaId =
    areaId ?? activeAreaView(getSnapshot())?.active_area_id ?? DEFAULT_AREA_ID;
  const areaOptions = listAreaOptions();

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
      name: "memoryModule",
      label: "Memory module (set at creation)",
      type: "readonly",
      value: entity.memory_module ?? "recent_turns",
    },
    {
      name: "areaId",
      label: "Area",
      type: "select",
      value: resolvedAreaId,
      options: areaOptions,
      location: true,
    },
    {
      name: "x",
      label: "X",
      value: String(entity.position[0]),
      type: "number",
      required: true,
      location: true,
    },
    {
      name: "y",
      label: "Y",
      value: String(entity.position[1]),
      type: "number",
      required: true,
      location: true,
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
      areaId: data.areaId,
      sourceAreaId: resolvedAreaId,
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

export function bindActiveAreaSelect(selectEl, onChange) {
  if (!selectEl) return;
  selectEl.addEventListener("change", async () => {
    const value = selectEl.value;
    if (!value) return;
    try {
      const result = await postActiveArea(value);
      if (!result.ok) {
        showToast(result.message, true);
        return;
      }
      showToast(result.message, false);
      await onChange(result.snapshot);
    } catch (err) {
      showToast(String(err.message || err), true);
    }
  });
}

export function renderActiveAreaSelect(selectEl, snapshot) {
  if (!selectEl || !snapshot) return;
  const normalized = normalizeSnapshot(snapshot);
  const areaIds = normalized?.areas ? Object.keys(normalized.areas).sort() : [];
  const current = selectEl.value;
  selectEl.innerHTML = "";
  for (const areaId of areaIds) {
    const opt = document.createElement("option");
    opt.value = areaId;
    opt.textContent = areaId;
    if (areaId === normalized.active_area_id) opt.selected = true;
    selectEl.appendChild(opt);
  }
  if (current && [...selectEl.options].some((o) => o.value === current)) {
    selectEl.value = current;
  }
}

export function renderActiveAgentSelect(selectEl, snapshot) {
  if (!selectEl || !snapshot) return;
  const snap = normalizeSnapshot(snapshot);
  const agents = asArray(snap.agents);
  const current = selectEl.value;
  selectEl.innerHTML = "";
  for (const agent of agents) {
    const opt = document.createElement("option");
    opt.value = agent.id;
    const areaTag = agent.area_id ? ` [${agent.area_id}]` : "";
    opt.textContent = `${agent.name} (${agent.id})${areaTag}`;
    if (agent.id === snap.active_agent_id) opt.selected = true;
    selectEl.appendChild(opt);
  }
  if (current && [...selectEl.options].some((o) => o.value === current)) {
    selectEl.value = current;
  }
}

export function openCreateAreaModal() {
  openModal(
    "Create area",
    [
      {
        name: "id",
        label: "Area id (lowercase, e.g. attic)",
        value: "attic",
        required: true,
      },
      {
        name: "desc",
        label: "Area description",
        value: "A new area.",
        type: "textarea",
      },
      { name: "width", label: "Grid width", value: "5", type: "number", required: true },
      { name: "height", label: "Grid height", value: "5", type: "number", required: true },
    ],
    async (data) => {
      const result = await postCreateArea({
        areaId: data.id.trim().toLowerCase(),
        description: data.desc,
        width: data.width,
        height: data.height,
      });
      if (!result.ok) throw new Error(result.message);
      showToast(result.message, false);
      await onStateChanged(result.snapshot);
    },
    { submitLabel: "Create" },
  );
}

export function openEditAreaModal() {
  const snap = normalizeSnapshot(getSnapshot());
  const areaId = snap?.active_area_id;
  if (!areaId || !snap?.areas?.[areaId]) {
    showToast("No active area to edit.", true);
    return;
  }
  const block = snap.areas[areaId];
  const grid = block.grid || {};
  const width = grid.max_x != null && grid.min_x != null
    ? grid.max_x - grid.min_x + 1
    : 5;
  const height = grid.max_y != null && grid.min_y != null
    ? grid.max_y - grid.min_y + 1
    : 5;

  openModal(
    `Edit area — ${areaId}`,
    [
      {
        name: "desc",
        label: "Area description",
        value: block.area_description ?? "",
        type: "textarea",
      },
      { name: "width", label: "Grid width", value: String(width), type: "number", required: true },
      { name: "height", label: "Grid height", value: String(height), type: "number", required: true },
    ],
    async (data) => {
      const result = await postEditArea({
        areaId,
        description: data.desc,
        width: data.width,
        height: data.height,
      });
      if (!result.ok) throw new Error(result.message);
      showToast(result.message, false);
      await onStateChanged(result.snapshot);
    },
  );
}

export async function openDeleteAreaModal() {
  const snap = normalizeSnapshot(getSnapshot());
  const areaId = snap?.active_area_id;
  if (!areaId) {
    showToast("No active area selected.", true);
    return;
  }
  if (!window.confirm(`Delete area "${areaId}"? It must be empty (no agents or objects).`)) {
    return;
  }
  try {
    const result = await postDeleteArea(areaId);
    if (!result.ok) {
      showToast(result.message, true);
      return;
    }
    showToast(result.message, false);
    await onStateChanged(result.snapshot);
  } catch (err) {
    showToast(String(err.message || err), true);
  }
}

export function bindAreaManageButtons({ createBtn, editBtn, deleteBtn }) {
  if (createBtn) createBtn.addEventListener("click", () => openCreateAreaModal());
  if (editBtn) editBtn.addEventListener("click", () => openEditAreaModal());
  if (deleteBtn) deleteBtn.addEventListener("click", () => openDeleteAreaModal());
}

export { showToast };
