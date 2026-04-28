const state = {
  lists: [],
  tasks: [],
  sprints: [],
  timeBlocks: [],
  activeSprint: null,
};

const TASK_STATUSES = ["inbox", "todo", "in_progress", "done"];

const voiceSession = {
  parsed: null,
  finalTranscript: "",
  pendingDeleteTaskIds: [],
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

function renderVoiceSprintState() {
  const node = document.getElementById("voiceSprintState");
  if (!node) {
    return;
  }

  if (state.activeSprint?.sprint) {
    node.textContent = `Active sprint: ${state.activeSprint.sprint.name}`;
    return;
  }

  node.textContent = "Active sprint: not selected (tasks go to inbox).";
}

function renderVoiceRuntimeState(runtime) {
  const node = document.getElementById("voiceRuntimeStatus");
  if (!node) {
    return;
  }
  node.textContent = `AI mode: ${runtime.status_label}`;
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

    const isActive = state.activeSprint?.sprint_id === sprint.id;

    node.innerHTML = `
      <h3>${sprint.name}${isActive ? " (active)" : ""}</h3>
      <div class="task-meta">${fromISO(sprint.start_date)} - ${fromISO(sprint.end_date)}</div>
      <button class="button ghost" data-set-active-sprint="${sprint.id}" type="button">
        ${isActive ? "Active now" : "Make Active"}
      </button>
      ${directionsHtml}
    `;
    container.appendChild(node);
  });

  container.querySelectorAll("[data-set-active-sprint]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      try {
        const sprintId = event.currentTarget.dataset.setActiveSprint;
        await api("/api/sprints/active", {
          method: "PUT",
          body: JSON.stringify({ sprint_id: sprintId }),
        });
        toast("Active sprint updated");
        await refreshAll();
      } catch (error) {
        toast(normalizeApiError(error));
      }
    });
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
  const voiceRuntime = await api("/api/voice/runtime");
  document.getElementById("aiState").textContent = JSON.stringify(ai, null, 2);
  document.getElementById("voiceState").textContent = JSON.stringify(voice, null, 2);
  renderVoiceRuntimeState(voiceRuntime);

  const chatHistoryConfig = await api("/api/voice/history-config");
  document.querySelector("#chatHistoryForm input[name='enabled']").checked =
    chatHistoryConfig.enabled;
  document.querySelector("#chatHistoryForm input[name='retention_days']").value =
    chatHistoryConfig.retention_days;
  document.querySelector("#chatHistoryForm input[name='context_limit']").value =
    chatHistoryConfig.context_limit;

  const history = await api("/api/voice/history?limit=20");
  const memory = await api("/api/voice/memory?limit=20");
  document.getElementById("chatHistoryState").textContent = JSON.stringify(
    { config: chatHistoryConfig, recent_messages: history, long_memory: memory },
    null,
    2
  );
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
  state.activeSprint = await api("/api/sprints/active");
  state.timeBlocks = await api("/api/calendar");

  syncSelects();
  renderDashboard();
  renderTasks();
  renderKanban();
  renderSprints();
  renderVoiceSprintState();
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
  const inputNode = document.getElementById("voiceChatInput");
  const previewNode = document.getElementById("voicePreview");
  const message = inputNode.value.trim();

  if (!message) {
    toast("Message is empty");
    return null;
  }

  addVoiceMessage("user", message);
  inputNode.value = "";

  const plan = await api("/api/voice/chat-turn", {
    method: "POST",
    body: JSON.stringify({
      message,
      list_id: document.getElementById("voiceListSelect").value || null,
    }),
  });

  voiceSession.parsed = plan;
  voiceSession.pendingDeleteTaskIds = [];
  previewNode.textContent = JSON.stringify(plan, null, 2);

  addVoiceMessage(
    "assistant",
    `${plan.assistant_reply}`
  );

  renderVoiceActions(plan.actions || []);

  if (plan.error) {
    addVoiceMessage(
      "assistant",
      "Был технический сбой у AI-провайдера, но базовую логику я сохранил и продолжаю работать."
    );
  }

  if (announce && plan.tasks?.length) {
    addVoiceMessage("assistant", `Я выделил задач: ${plan.tasks.length}.`);
  }

  return plan;
}

function renderVoiceActions(actions) {
  const wrap = document.getElementById("voiceActionChips");
  wrap.innerHTML = "";

  actions.forEach((item) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.textContent = item.label;
    btn.dataset.action = item.action;
    wrap.appendChild(btn);
  });
}

async function handleVoiceAction(action) {
  if (!voiceSession.parsed) {
    return;
  }

  if (action === "save_tasks") {
    const created = await api("/api/voice/confirm-tasks", {
      method: "POST",
      body: JSON.stringify({
        list_id: document.getElementById("voiceListSelect").value,
        tasks: voiceSession.parsed.tasks || [],
      }),
    });

    const assignedSprint = created.tasks?.[0]?.sprint_id;
    const sprintNote = assignedSprint
      ? " Привязал к активному спринту."
      : " Сохранил в inbox без спринта.";

    addVoiceMessage(
      "assistant",
      `Готово. Записал задач: ${created.created_count}.${sprintNote}`
    );
    document.getElementById("voicePreview").textContent = JSON.stringify(created, null, 2);
    voiceSession.parsed = null;
    renderVoiceActions([]);
    await refreshAll();
    return;
  }

  if (action === "run_query" || action === "confirm_delete" || action === "confirm_update_status") {
    if (action === "confirm_delete") {
      const preview = await api("/api/voice/apply-action", {
        method: "POST",
        body: JSON.stringify({
          action: "run_query",
          operation: voiceSession.parsed?.operation || null,
          list_id: document.getElementById("voiceListSelect").value || null,
        }),
      });

      document.getElementById("voicePreview").textContent = JSON.stringify(preview, null, 2);
      const ids = (preview.tasks || []).map((task) => task.id);
      voiceSession.pendingDeleteTaskIds = ids;

      if (!ids.length) {
        addVoiceMessage("assistant", "Под удаление ничего не нашел. Уточни запрос.");
        voiceSession.parsed = null;
        renderVoiceActions([]);
        return;
      }

      addVoiceMessage(
        "assistant",
        `Нашел для удаления: ${ids.length}. Подтверди финальное удаление.`
      );
      renderVoiceActions([
        { action: "final_delete", label: "Подтверждаю удаление" },
        { action: "skip_tasks", label: "Отмена" },
      ]);
      return;
    }

    const result = await api("/api/voice/apply-action", {
      method: "POST",
      body: JSON.stringify({
        action,
        operation: voiceSession.parsed?.operation || null,
        list_id: document.getElementById("voiceListSelect").value || null,
      }),
    });

    addVoiceMessage("assistant", result.assistant_reply);

    if (result.tasks?.length) {
      const lines = result.tasks
        .slice(0, 8)
        .map((task) => `• ${task.title} [${task.status}]`)
        .join("\n");
      addVoiceMessage("assistant", `Список:\n${lines}`);
    }

    document.getElementById("voicePreview").textContent = JSON.stringify(result, null, 2);
    voiceSession.parsed = null;
    renderVoiceActions([]);
    await refreshAll();
    return;
  }

  if (action === "final_delete") {
    const result = await api("/api/voice/apply-action", {
      method: "POST",
      body: JSON.stringify({
        action: "confirm_delete",
        operation: voiceSession.parsed?.operation || null,
        list_id: document.getElementById("voiceListSelect").value || null,
        task_ids: voiceSession.pendingDeleteTaskIds || [],
      }),
    });
    addVoiceMessage("assistant", result.assistant_reply);
    document.getElementById("voicePreview").textContent = JSON.stringify(result, null, 2);
    voiceSession.pendingDeleteTaskIds = [];
    voiceSession.parsed = null;
    renderVoiceActions([]);
    await refreshAll();
    return;
  }

  if (action === "skip_tasks") {
    addVoiceMessage("assistant", "Ок, не записываю. Чем еще помочь?");
    voiceSession.pendingDeleteTaskIds = [];
    voiceSession.parsed = null;
    renderVoiceActions([]);
    return;
  }

  if (action === "edit_tasks") {
    addVoiceMessage(
      "assistant",
      "Напиши правку сообщением: например 'у второй задачи приоритет high'."
    );
    return;
  }

  addVoiceMessage("assistant", "Продолжим. Напиши или надиктуй следующее сообщение.");
}

function bindVoice() {
  const inputNode = document.getElementById("voiceChatInput");

  addVoiceMessage(
    "assistant",
    "Привет. Я могу выделять задачи, отвечать на вопросы и помогать с фокусом."
  );

  const RecognitionClass = getRecognitionClass();
  if (RecognitionClass) {
    recognition = new RecognitionClass();
    recognition.lang = "ru-RU";
    recognition.interimResults = true;
    recognition.continuous = true;

    recognition.onresult = (event) => {
      let text = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        text += event.results[i][0].transcript + " ";
      }
      inputNode.value = text.trim();
    };

    recognition.onend = async () => {
      if (recognitionActive) {
        try {
          recognition.start();
          return;
        } catch (_error) {
          // noop, user can start again
        }
      }
      recognitionActive = false;
    };
  }

  document.getElementById("voiceStartBtn").addEventListener("click", () => {
    if (!recognition) {
      toast("SpeechRecognition is not supported in this browser");
      return;
    }
    if (recognitionActive) {
      return;
    }
    recognition.start();
    recognitionActive = true;
    toast("Dictation started");
  });

  document.getElementById("voiceStopBtn").addEventListener("click", () => {
    if (recognition && recognitionActive) {
      recognition.stop();
      recognitionActive = false;
      toast("Dictation stopped");
      if (inputNode.value.trim()) {
        parseVoiceTranscript({ announce: true }).catch((error) => {
          toast(normalizeApiError(error));
          addVoiceMessage("assistant", normalizeApiError(error));
        });
      }
    }
  });

  document.getElementById("voiceChatForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await parseVoiceTranscript({ announce: true });
    } catch (error) {
      toast(normalizeApiError(error));
      addVoiceMessage("assistant", normalizeApiError(error));
    }
  });

  document.getElementById("voiceActionChips").addEventListener("click", async (event) => {
    const action = event.target?.dataset?.action;
    if (!action) {
      return;
    }
    try {
      await handleVoiceAction(action);
    } catch (error) {
      toast(normalizeApiError(error));
      addVoiceMessage("assistant", normalizeApiError(error));
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

  document.getElementById("chatHistoryForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      const payload = {
        enabled: form.elements.enabled.checked,
        retention_days: Number(formValue(form, "retention_days")) || 30,
        context_limit: Number(formValue(form, "context_limit")) || 10,
      };
      await api("/api/voice/history-config", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      toast("Chat history settings saved");
      await renderStubsAndSettings();
    } catch (error) {
      toast(normalizeApiError(error));
    }
  });

  document.getElementById("clearChatHistoryBtn").addEventListener("click", async () => {
    try {
      await api("/api/voice/history/clear", { method: "POST" });
      toast("Chat history cleared");
      await renderStubsAndSettings();
    } catch (error) {
      toast(normalizeApiError(error));
    }
  });

  document.getElementById("clearLongMemoryBtn").addEventListener("click", async () => {
    try {
      await api("/api/voice/memory/clear", { method: "POST" });
      toast("Long memory cleared");
      await renderStubsAndSettings();
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
