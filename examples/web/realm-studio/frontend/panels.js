/**
 * Sidebar panels: passive vision, turn log, recent events (V0.3.1e–0.3.2b).
 */

const MAX_LOG_ENTRIES = 50;

let turnLogEntries = [];
let lastPromptText = null;

export function renderPassiveVision(snapshot, visionEl, emptyEl) {
  const text = snapshot?.passive_vision?.trim();
  if (!text) {
    visionEl.textContent = "";
    visionEl.classList.add("hidden");
    emptyEl.classList.remove("hidden");
    return;
  }
  visionEl.textContent = text;
  visionEl.classList.remove("hidden");
  emptyEl.classList.add("hidden");
}

export function renderRecentEvents(snapshot, listEl, emptyEl) {
  const events = snapshot?.recent_events;
  listEl.innerHTML = "";
  if (!Array.isArray(events) || events.length === 0) {
    emptyEl.classList.remove("hidden");
    return;
  }
  emptyEl.classList.add("hidden");
  for (const event of [...events].reverse()) {
    const item = document.createElement("li");
    item.className = "recent-event-entry";
    const turn = document.createElement("span");
    turn.className = "recent-event-turn";
    turn.textContent = `Turn ${event.session_turn}`;
    const text = document.createElement("span");
    text.className = "recent-event-text";
    text.textContent = event.text;
    item.appendChild(turn);
    item.appendChild(text);
    listEl.appendChild(item);
  }
}

export function appendTurnLogEntry({ sessionTurn, agentName, message, steps }) {
  turnLogEntries.unshift({
    sessionTurn,
    agentName,
    message,
    steps: Array.isArray(steps) ? steps : [],
  });
  if (turnLogEntries.length > MAX_LOG_ENTRIES) {
    turnLogEntries.length = MAX_LOG_ENTRIES;
  }
}

export function renderTurnLog(listEl, emptyEl) {
  listEl.innerHTML = "";
  if (turnLogEntries.length === 0) {
    emptyEl.classList.remove("hidden");
    return;
  }
  emptyEl.classList.add("hidden");

  for (const entry of turnLogEntries) {
    const item = document.createElement("li");
    item.className = "turn-log-entry";

    const head = document.createElement("div");
    head.className = "turn-log-head";
    head.textContent = `Session ${entry.sessionTurn} — ${entry.agentName}`;
    item.appendChild(head);

    const composite = document.createElement("p");
    composite.className = "turn-log-composite";
    composite.textContent = entry.message;
    item.appendChild(composite);

    if (entry.steps.length > 0) {
      const steps = document.createElement("ul");
      steps.className = "turn-log-steps";
      for (const step of entry.steps) {
        const li = document.createElement("li");
        li.textContent = `[${step.kind}] ${step.result}`;
        steps.appendChild(li);
      }
      item.appendChild(steps);
    }

    listEl.appendChild(item);
  }
}

export function setLastPrompt(text) {
  lastPromptText = text ?? null;
}

export function renderLastPrompt(promptEl, emptyEl) {
  if (!lastPromptText) {
    promptEl.textContent = "";
    promptEl.classList.add("hidden");
    emptyEl.classList.remove("hidden");
    return;
  }
  promptEl.textContent = lastPromptText;
  promptEl.classList.remove("hidden");
  emptyEl.classList.add("hidden");
}

export function bindPromptDebug(detailsEl, promptEl, emptyEl, fetchPromptFn) {
  detailsEl.addEventListener("toggle", async () => {
    if (!detailsEl.open) return;
    if (lastPromptText) {
      renderLastPrompt(promptEl, emptyEl);
      return;
    }
    try {
      const data = await fetchPromptFn();
      if (data.ok && data.prompt) {
        setLastPrompt(data.prompt);
      }
      renderLastPrompt(promptEl, emptyEl);
    } catch {
      renderLastPrompt(promptEl, emptyEl);
    }
  });
}
