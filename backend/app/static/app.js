const state = {
  lists: [],
  tasks: [],
  sprints: [],
  timeBlocks: [],
};

const TASK_STATUSES = ["inbox", "todo", "in_progress", "done"];

const voiceSession = {
  parsed: null,
  finalTranscript: "",
};

let recognition = null;
let recognitionActive = false;

function toast(message) {
  const node = document.getElementById("toast");
  node.textContent = message;
  node.classList.add("show");
  window.setTimeout(() => node.classList.remove("show"), 1700);
}

function addVoiceMessage(role, text) {
  const log = document.getElementById("voiceChatMessages");
  const item = document.createElement("div");
  item.className = `chat-item ${role}`;
  item.textContent = text;
  log.appendChild(item);
  log.scrollTop = log.scrollHeight;
}

function normalizeApiError(error) {
  if (typeof error.message !== "string") {
    return "Request failed";
  }
  return error.message;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      } else if (payload.detail?.message) {
        detail = payload.detail.message;
      }
    } catch (_error) {
      detail = response.statusText;
    }
    throw new Error(detail || "Request failed");
  }

  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

function toISO(datetimeLocalValue) {
  if (!datetimeLocalValue) {
    return null;
  }
  return new Date(datetimeLocalValue).toISOString();
}

function fromISO(iso) {
  if (!iso) {
    return "-";
  }
  return new Date(iso).toLocaleString();
}

async function ensureDefaultList() {
  const lists = await api("/api/lists");
  if (lists.length > 0) {
    return lists;
  }
  await api("/api/lists", {
    method: "POST",
    body: JSON.stringify({ name: "General", color: "#0369a1" }),
  });
  return api("/api/lists");
}

function fillSelect(selectId, items, placeholder, mapper) {
  const select = document.getElementById(selectId);
  if (!select) {
    return;
  }

  select.innerHTML = "";
  if (placeholder) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = placeholder;
    select.appendChild(opt);
  }

  items.forEach((item) => {
    const opt = document.createElement("option");
    const mapped = mapper(item);
    opt.value = mapped.value;
    opt.textContent = mapped.label;
    select.appendChild(opt);
  });
}

function renderDashboard() {
  const stats = {
    total: state.tasks.length,
    todo: state.tasks.filter((task) => task.status === "todo").length,
    inProgress: state.tasks.filter((task) => task.status === "in_progress").length,
    done: state.tasks.filter((task) => task.status === "done").length,
  };

  const container = document.getElementById("dashboardStats");
  container.innerHTML = [
    ["Total", stats.total],
    ["Todo", stats.todo],
    ["In progress", stats.inProgress],
    ["Done", stats.done],
  ]
    .map(
      ([label, value]) =>
        `<div class="stat"><div class="label">${label}</div><div class="value">${value}</div></div>`
    )
    .join("");
}

function renderTasks() {
  const container = document.getElementById("tasksContainer");
  container.innerHTML = "";

  if (state.tasks.length === 0) {
    container.innerHTML = '<div class="task-item">No tasks yet.</div>';
    return;
  }

  state.tasks.forEach((task) => {
    const node = document.createElement("article");
    node.className = "task-item";
    node.innerHTML = `
      <div><strong>${task.title}</strong></div>
      <div class="task-meta">
        <span class="pill ${task.priority}">${task.priority}</span>
        <span class="pill">${task.status}</span>
        ${task.duration_min} min | deadline: ${fromISO(task.deadline)}
      </div>
      <div class="task-meta">${task.note || ""}</div>
      <div class="stack" style="margin-top:0.4rem;">
        <div class="grid two">
          <select data-edit-status="${task.id}">
            ${TASK_STATUSES.map(
              (status) =>
                `<option value="${status}" ${task.status === status ? "selected" : ""}>${status}</option>`
            ).join("")}
          </select>
          <button class="button ghost" data-delete-task="${task.id}">Delete</button>
        </div>
      </div>
    `;
    container.appendChild(node);
  });

  container.querySelectorAll("[data-delete-task]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      try {
        const taskId = event.currentTarget.dataset.deleteTask;
        await api(`/api/tasks/${taskId}`, { method: "DELETE" });
        toast("Task removed");
        await refreshAll();
      } catch (error) {
        toast(normalizeApiError(error));
      }
    });
  });

  container.querySelectorAll("[data-edit-status]").forEach((select) => {
    select.addEventListener("change", async (event) => {
      try {
        const taskId = event.currentTarget.dataset.editStatus;
        await api(`/api/tasks/${taskId}/move`, {
          method: "POST",
          body: JSON.stringify({ status: event.currentTarget.value }),
        });
        await refreshAll();
      } catch (error) {
        toast(normalizeApiError(error));
      }
    });
  });
}

function renderKanban() {
  const board = document.getElementById("kanbanBoard");
  board.innerHTML = "";

  TASK_STATUSES.forEach((status) => {
    const col = document.createElement("div");
    col.className = "column";
    col.innerHTML = `<div class="column-header">${status}</div><div class="column-body" data-status="${status}"></div>`;
    board.appendChild(col);

    const body = col.querySelector(".column-body");
    body.addEventListener("dragover", (event) => event.preventDefault());
    body.addEventListener("drop", async (event) => {
      event.preventDefault();
      const taskId = event.dataTransfer.getData("text/plain");
      try {
        await api(`/api/tasks/${taskId}/move`, {
          method: "POST",
          body: JSON.stringify({ status }),
        });
        await refreshAll();
      } catch (error) {
        toast(normalizeApiError(error));
      }
    });

    state.tasks
      .filter((task) => task.status === status)
      .forEach((task) => {
        const card = document.createElement("article");
        card.className = "kanban-card";
        card.draggable = true;
        card.dataset.taskId = task.id;
        card.innerHTML = `<strong>${task.title}</strong><div class="task-meta">${task.duration_min} min</div>`;

        card.addEventListener("dragstart", (event) => {
          card.classList.add("dragging");
          event.dataTransfer.setData("text/plain", task.id);
        });

        card.addEventListener("dragend", () => card.classList.remove("dragging"));
        body.appendChild(card);
      });
  });
}

function renderSprints() {
  const container = document.getElementById("sprintsContainer");
  container.innerHTML = "";
  if (state.sprints.length === 0) {
    container.innerHTML = '<div class="sprint-card">No sprints yet.</div>';
    return;
  }

  state.sprints.forEach((sprint) => {
    const node = document.createElement("article");
    node.className = "sprint-card";

    const directionsHtml = sprint.directions
      .map((direction) => {
        const directionTasks = state.tasks.filter(
          (task) => task.sprint_direction_id === direction.id
        );

        return `
          <div class="task-item" style="margin-top:0.4rem;">
            <strong>${direction.name}</strong>
            <div class="task-meta">${directionTasks.length} tasks</div>
          </div>
        `;
      })
      .join("");

    node.innerHTML = `
      <h3>${sprint.name}</h3>
      <div class="task-meta">${fromISO(sprint.start_date)} — ${fromISO(sprint.end_date)}</div>
      ${directionsHtml}
    `;
    container.appendChild(node);
  });
}

function renderCalendar() {
  const container = document.getElementById("calendarContainer");
  container.innerHTML = "";

  if (state.timeBlocks.length === 0) {
    container.innerHTML = '<div class="calendar-item">No time blocks yet.</div>';
    return;
  }

  state.timeBlocks.forEach((event) => {
    const node = document.createElement("article");
    node.className = "calendar-item";
    node.innerHTML = `
      <strong>${event.task.title}</strong>
      <div class="task-meta">${fromISO(event.block.start_at)} -> ${fromISO(event.block.end_at)}</div>
    `;
    container.appendChild(node);
  });
}

async function renderStubsAndSettings() {
  const integration = await api("/api/integrations/google-calendar");
  document.getElementById("integrationState").textContent = JSON.stringify(
    integration,
    null,
    2
  );
  document.querySelector("#integrationForm input[name='enabled']").checked =
    integration.enabled;
  document.querySelector("#integrationForm textarea[name='settings_json']").value =
    integration.settings_json;

  const ai = await api("/api/ai/capabilities");
  const voice = await api("/api/voice/capabilities");
  document.getElementById("aiState").textContent = JSON.stringify(ai, null, 2);
  document.getElementById("voiceState").textContent = JSON.stringify(voice, null, 2);
}

function syncSelects() {
  fillSelect("taskListSelect", state.lists, null, (list) => ({
    value: list.id,
    label: list.name,
  }));

  fillSelect("voiceListSelect", state.lists, null, (list) => ({
    value: list.id,
    label: `Voice target: ${list.name}`,
  }));

  fillSelect("timeBlockTaskSelect", state.tasks, null, (task) => ({
    value: task.id,
    label: task.title,
  }));
}

async function refreshAll() {
  state.lists = await ensureDefaultList();
  state.tasks = await api("/api/tasks");
  state.sprints = await api("/api/sprints");
  state.timeBlocks = await api("/api/calendar");

  syncSelects();
  renderDashboard();
  renderTasks();
  renderKanban();
  renderSprints();
  renderCalendar();
  await renderStubsAndSettings();
}

function formValue(form, name) {
  return form.elements[name]?.value?.trim();
}

function getRecognitionClass() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

async function parseVoiceTranscript({ announce = true } = {}) {
  const transcriptNode = document.getElementById("voiceTranscript");
  const previewNode = document.getElementById("voicePreview");
  const transcript = transcriptNode.value.trim();

  if (!transcript) {
    toast("Transcript is empty");
    return null;
  }

  const listId = document.getElementById("voiceListSelect").value || null;
  const parsed = await api("/api/voice/parse-task", {
    method: "POST",
    body: JSON.stringify({ transcript, list_id: listId }),
  });

  voiceSession.parsed = parsed;
  previewNode.textContent = JSON.stringify(parsed, null, 2);

  if (announce) {
    addVoiceMessage("assistant", `Понял задачу: ${parsed.title}`);
  }

  if (parsed.requires_clarification) {
    addVoiceMessage(
      "assistant",
      parsed.next_question || "Нужны уточнения перед сохранением задачи."
    );
  } else {
    addVoiceMessage(
      "assistant",
      "Все поля на месте. Можно нажать Create Task и сохранить задачу."
    );
  }

  return parsed;
}

function bindVoice() {
  const transcriptNode = document.getElementById("voiceTranscript");

  addVoiceMessage(
    "assistant",
    "Диктуй задачу голосом. Если чего-то не хватит, я задам уточняющий вопрос в этом чате."
  );

  const RecognitionClass = getRecognitionClass();
  if (RecognitionClass) {
    recognition = new RecognitionClass();
    recognition.lang = "ru-RU";
    recognition.interimResults = true;
    recognition.continuous = true;

    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const piece = event.results[i][0].transcript.trim();
        if (!piece) {
          continue;
        }
        if (event.results[i].isFinal) {
          voiceSession.finalTranscript = `${voiceSession.finalTranscript} ${piece}`.trim();
        } else {
          interim = `${interim} ${piece}`.trim();
        }
      }
      transcriptNode.value = `${voiceSession.finalTranscript} ${interim}`.trim();
    };

    recognition.onend = () => {
      recognitionActive = false;
      transcriptNode.value = voiceSession.finalTranscript.trim();
    };
  }

  document.getElementById("voiceStartBtn").addEventListener("click", () => {
    if (!recognition) {
      toast("SpeechRecognition is not supported in this browser");
      addVoiceMessage("assistant", "Открой приложение в Chrome/Edge для голосового ввода.");
      return;
    }
    if (recognitionActive) {
      return;
    }
    voiceSession.finalTranscript = transcriptNode.value.trim();
    recognition.start();
    recognitionActive = true;
    toast("Dictation started");
  });

  document.getElementById("voiceStopBtn").addEventListener("click", () => {
    if (recognition && recognitionActive) {
      recognition.stop();
      recognitionActive = false;
      toast("Dictation stopped");
    }
  });

  document.getElementById("voiceParseBtn").addEventListener("click", async () => {
    try {
      await parseVoiceTranscript({ announce: true });
    } catch (error) {
      toast(normalizeApiError(error));
      addVoiceMessage("assistant", normalizeApiError(error));
    }
  });

  document.getElementById("voiceCreateBtn").addEventListener("click", async () => {
    try {
      const parsed = voiceSession.parsed || (await parseVoiceTranscript({ announce: false }));
      if (!parsed) {
        return;
      }

      if (parsed.requires_clarification) {
        addVoiceMessage(
          "assistant",
          parsed.next_question || "Нужно уточнить параметры перед сохранением."
        );
        toast("Need clarification first");
        return;
      }

      const task = await api("/api/voice/create-task", {
        method: "POST",
        body: JSON.stringify({
          transcript: document.getElementById("voiceTranscript").value.trim(),
          list_id: document.getElementById("voiceListSelect").value,
          title: parsed.title,
          note: parsed.note,
          status: parsed.status,
          priority: parsed.priority,
          duration_min: parsed.duration_min,
          deadline: parsed.deadline,
        }),
      });

      document.getElementById("voicePreview").textContent = JSON.stringify(task, null, 2);
      addVoiceMessage("assistant", "Готово. Задача сохранена.");
      document.getElementById("voiceTranscript").value = "";
      voiceSession.finalTranscript = "";
      voiceSession.parsed = null;
      toast("Task created from voice");
      await refreshAll();
    } catch (error) {
      const text = normalizeApiError(error);
      toast(text);
      addVoiceMessage("assistant", text);
    }
  });

  document.getElementById("voiceChatForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.getElementById("voiceChatInput");
    const value = input.value.trim();
    if (!value) {
      return;
    }

    addVoiceMessage("user", value);
    const transcriptNode = document.getElementById("voiceTranscript");
    transcriptNode.value = `${transcriptNode.value} ${value}`.trim();
    voiceSession.finalTranscript = transcriptNode.value;
    input.value = "";

    try {
      await parseVoiceTranscript({ announce: false });
    } catch (error) {
      const text = normalizeApiError(error);
      toast(text);
      addVoiceMessage("assistant", text);
    }
  });
}

function bindForms() {
  document.getElementById("quickTaskForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api("/api/tasks", {
        method: "POST",
        body: JSON.stringify({
          title: formValue(form, "title"),
          duration_min: Number(formValue(form, "duration_min")) || 30,
          priority: formValue(form, "priority") || "medium",
          status: "inbox",
          list_id: state.lists[0].id,
        }),
      });
      form.reset();
      toast("Task created");
      await refreshAll();
    } catch (error) {
      toast(normalizeApiError(error));
    }
  });

  document.getElementById("taskForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api("/api/tasks", {
        method: "POST",
        body: JSON.stringify({
          title: formValue(form, "title"),
          note: formValue(form, "note") || null,
          status: formValue(form, "status"),
          priority: formValue(form, "priority"),
          duration_min: Number(formValue(form, "duration_min")) || 30,
          deadline: toISO(formValue(form, "deadline")),
          list_id: formValue(form, "list_id"),
        }),
      });
      form.reset();
      toast("Task created");
      await refreshAll();
    } catch (error) {
      toast(normalizeApiError(error));
    }
  });

  document.getElementById("sprintForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api("/api/sprints", {
        method: "POST",
        body: JSON.stringify({
          name: formValue(form, "name"),
          start_date: toISO(formValue(form, "start_date")),
          end_date: toISO(formValue(form, "end_date")),
          directions: ["Health", "Career", "Relationships", "Finance"],
        }),
      });
      form.reset();
      toast("Sprint created");
      await refreshAll();
    } catch (error) {
      toast(normalizeApiError(error));
    }
  });

  document.getElementById("timeBlockForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api("/api/time-blocks", {
        method: "POST",
        body: JSON.stringify({
          task_id: formValue(form, "task_id"),
          start_at: toISO(formValue(form, "start_at")),
          end_at: toISO(formValue(form, "end_at")),
        }),
      });
      form.reset();
      toast("Time block saved");
      await refreshAll();
    } catch (error) {
      toast(normalizeApiError(error));
    }
  });

  document.getElementById("integrationForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      const payload = {
        enabled: form.elements.enabled.checked,
        settings_json: formValue(form, "settings_json") || "{}",
      };
      const response = await api("/api/integrations/google-calendar", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      document.getElementById("integrationState").textContent = JSON.stringify(response, null, 2);
      toast("Settings saved");
    } catch (error) {
      toast(normalizeApiError(error));
    }
  });
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
      button.classList.add("active");

      const view = button.dataset.view;
      document.querySelectorAll(".view").forEach((node) => node.classList.remove("active"));
      document.getElementById(`view-${view}`).classList.add("active");
    });
  });
}

function bindGlobalActions() {
  document.getElementById("refreshBtn").addEventListener("click", async () => {
    try {
      await refreshAll();
      toast("Refreshed");
    } catch (error) {
      toast(normalizeApiError(error));
    }
  });
}

async function boot() {
  bindTabs();
  bindVoice();
  bindForms();
  bindGlobalActions();
  await refreshAll();
}

boot().catch((error) => {
  toast(normalizeApiError(error) || "Failed to initialize app");
});
