"use strict";

const PROGRESS_CIRCUMFERENCE = 2 * Math.PI * 60; // r=60

async function api(url, body = null) {
  const opts = {
    method: body !== null ? "POST" : "GET",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": CSRF_TOKEN,
    },
  };
  if (body !== null) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function parseTags(raw) {
  return raw.split(",").map((s) => s.trim()).filter(Boolean);
}

function updateStats(stats, streak) {
  const byId = (id) => document.getElementById(id);
  if (stats) {
    byId("statTotal").textContent      = stats.total;
    byId("statCompleted").textContent  = stats.completed;
    byId("statPending").textContent    = stats.pending;
    byId("statHighPriority").textContent = stats.high_priority_remaining;

    const pct = stats.completion_rate;
    byId("progressPct").textContent = `${pct}%`;
    const offset = PROGRESS_CIRCUMFERENCE - (pct / 100) * PROGRESS_CIRCUMFERENCE;
    const bar = byId("progressRingBar");
    bar.style.strokeDasharray  = String(PROGRESS_CIRCUMFERENCE);
    bar.style.strokeDashoffset = String(offset);
  }
  if (streak !== undefined) {
    const sc = byId("streakCount");
    if (sc) sc.textContent = streak;
  }
}

(function initRing() {
  const bar = document.getElementById("progressRingBar");
  if (!bar) return;
  const pct = parseFloat(bar.dataset.pct || 0);
  const offset = PROGRESS_CIRCUMFERENCE - (pct / 100) * PROGRESS_CIRCUMFERENCE;
  bar.style.strokeDasharray  = String(PROGRESS_CIRCUMFERENCE);
  bar.style.strokeDashoffset = String(offset);
})();

let activeFilter = "all";

function applyFilter() {
  const items = document.querySelectorAll(".task-item");
  let visible = 0;
  items.forEach((li) => {
    const f = li.dataset.filter;
    const show = activeFilter === "all" || f === activeFilter;
    li.style.display = show ? "" : "none";
    if (show) visible++;
  });
  const empty = document.getElementById("emptyState");
  if (empty) empty.classList.toggle("hidden", visible > 0 || items.length === 0);
}

document.getElementById("statusFilters")?.addEventListener("click", (e) => {
  const btn = e.target.closest(".chip");
  if (!btn) return;
  activeFilter = btn.dataset.filter;
  document.querySelectorAll("#statusFilters .chip").forEach(
    (c) => c.classList.toggle("is-active", c === btn)
  );
  applyFilter();
});

function escHtml(str) {
  return str.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function buildTaskItem(task) {
  const li = document.createElement("li");
  li.className = "task-item" + (task.completed ? " is-completed" : "");
  li.dataset.id     = task.id;
  li.dataset.filter = task.completed ? "completed" : "active";

  const tagsHtml = (task.tags || [])
    .map((t) => `<span class="tag tag--color-teal">${escHtml(t)}</span>`)
    .join("");
  const dueHtml = task.dueTime
    ? `<span class="due-badge due-badge--time">${escHtml(task.dueTime)}</span>`
    : "";

  li.innerHTML = `
    <div style="display:flex; align-items:flex-start; gap:12px; width:100%;">
      <input type="checkbox" class="task-check" data-id="${task.id}">
      <div class="task-body">
        <div class="task-text">${escHtml(task.text)}</div>
        <div class="task-meta">
          <span class="tag tag--category">${escHtml(task.category)}</span>
          <span class="tag tag--priority-${task.priority.toLowerCase()}">${escHtml(task.priority)}</span>
          ${tagsHtml}${dueHtml}
        </div>
      </div>
      <div class="task-actions">
        <button class="icon-btn edit-btn" title="Edit task" data-id="${task.id}"
          data-text="${escHtml(task.text)}" data-category="${task.category}" data-priority="${task.priority}"
          data-notes="${escHtml(task.notes || "")}" data-due-time="${task.dueTime || ""}"
          data-tags="${(task.tags || []).join(",")}">✎</button>
        <button class="icon-btn icon-btn--danger delete-btn" title="Delete task" data-id="${task.id}">✕</button>
      </div>
    </div>
    <button class="subtask-toggle-btn" data-parent-id="${task.id}">↳ Add subtask</button>
    <div class="add-subtask-row hidden" data-parent-id="${task.id}">
      <input type="text" placeholder="Subtask…" maxlength="140">
      <button type="button" class="add-subtask-submit" data-parent-id="${task.id}">+</button>
    </div>`;
  return li;
}

document.getElementById("addTaskForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const textInput = document.getElementById("taskInput");
  const text = textInput.value.trim();
  if (!text) return;

  const dueTimeVal = document.getElementById("dueTimeInput")?.value || "";
  const tagsVal = document.getElementById("tagsInput")?.value || "";
  const dateInput = document.getElementById("addTaskDateInput");
  const targetDate = dateInput ? dateInput.value : VIEW_DATE;

  try {
    const res = await api(URLS.create, {
      text,
      category: document.getElementById("categorySelect").value,
      priority: document.getElementById("prioritySelect").value,
      date: targetDate,
      due_time: dueTimeVal || null,
      tags: parseTags(tagsVal),
    });

    if (targetDate === VIEW_DATE) {
      // Same day being viewed — insert into the visible list as usual.
      const taskList = document.getElementById("taskList");
      const empty    = document.getElementById("emptyState");
      if (empty) empty.classList.add("hidden");
      const li = buildTaskItem(res.task);
      taskList.appendChild(li);
      applyFilter();
      updateStats(res.stats);
    } else {
      // Added for a different day (e.g. "Tomorrow") — it won't show in
      // today's list, so just confirm it landed rather than silently
      // doing nothing visible.
      const toggle = document.getElementById("addForDateToggle");
      const label = toggle?.querySelector(".chip.is-active")?.textContent.trim() || targetDate;
      const original = textInput.placeholder;
      textInput.placeholder = `Added to ${label} ✓`;
      setTimeout(() => { textInput.placeholder = original; }, 2200);
      // Reset the toggle back to "Today" so the next add defaults sanely.
      toggle?.querySelectorAll(".chip").forEach((c) => c.classList.toggle("is-active", c.dataset.date === VIEW_DATE));
      if (dateInput) dateInput.value = VIEW_DATE;
    }

    textInput.value = "";
    document.getElementById("dueTimeInput").value = "";
    document.getElementById("tagsInput").value = "";
    textInput.focus();
  } catch (err) {
    alert("Failed to add task: " + err.message);
  }
});

document.getElementById("taskList")?.addEventListener("change", async (e) => {
  if (e.target.matches(".subtask-check")) {
    if (!IS_TODAY) return;
    const id = e.target.dataset.id;
    const url = URLS.subtaskToggle.replace("__ID__", id);
    try {
      const res = await api(url);
      const li = document.querySelector(`.subtask-item[data-id="${id}"]`);
      li?.classList.toggle("is-completed", res.subtask.completed);
    } catch (err) {
      e.target.checked = !e.target.checked;
    }
    return;
  }

  if (!e.target.matches(".task-check") || !IS_TODAY) return;
  const id = e.target.dataset.id;
  const url = URLS.toggle.replace("__ID__", id);
  try {
    const res = await api(url);
    const li = document.querySelector(`.task-item[data-id="${id}"]`);
    if (li) {
      li.classList.toggle("is-completed", res.task.completed);
      li.dataset.filter = res.task.completed ? "completed" : "active";
    }
    updateStats(res.stats, res.streak);
    applyFilter();
  } catch (err) {
    e.target.checked = !e.target.checked;
    alert("Failed to update task.");
  }
});

let editingTaskId = null;
const editDialog  = document.getElementById("editDialog");

document.getElementById("taskList")?.addEventListener("click", (e) => {
  const btn = e.target.closest(".edit-btn");
  if (!btn) return;
  editingTaskId = btn.dataset.id;
  document.getElementById("editTextInput").value       = btn.dataset.text;
  document.getElementById("editCategorySelect").value   = btn.dataset.category;
  document.getElementById("editPrioritySelect").value   = btn.dataset.priority;
  document.getElementById("editNotesInput").value       = btn.dataset.notes || "";
  document.getElementById("editDueTimeInput").value     = btn.dataset.dueTime || "";
  document.getElementById("editTagsInput").value        = btn.dataset.tags || "";
  editDialog?.showModal();
});

document.getElementById("editForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = URLS.edit.replace("__ID__", editingTaskId);
  const text     = document.getElementById("editTextInput").value.trim();
  const category = document.getElementById("editCategorySelect").value;
  const priority = document.getElementById("editPrioritySelect").value;
  const notes    = document.getElementById("editNotesInput").value;
  const dueTime  = document.getElementById("editDueTimeInput").value;
  const tags     = parseTags(document.getElementById("editTagsInput").value);

  try {
    const res = await api(url, { text, category, priority, notes, due_time: dueTime || null, tags });
    location.reload();
  } catch (err) {
    alert("Failed to save: " + err.message);
  }
});

document.getElementById("cancelEditBtn")?.addEventListener("click",
  () => editDialog?.close());

document.getElementById("taskList")?.addEventListener("click", async (e) => {
  const btn = e.target.closest(".delete-btn");
  if (!btn) return;
  const id  = btn.dataset.id;
  const url = URLS.del.replace("__ID__", id);
  try {
    const res = await api(url);
    const li = document.querySelector(`.task-item[data-id="${id}"]`);
    li?.remove();
    updateStats(res.stats, res.streak);
    applyFilter();
    const remaining = document.querySelectorAll(".task-item");
    const empty = document.getElementById("emptyState");
    if (empty && remaining.length === 0) empty.classList.remove("hidden");
  } catch (err) {
    alert("Failed to delete: " + err.message);
  }
});

document.getElementById("taskList")?.addEventListener("click", (e) => {
  const toggleBtn = e.target.closest(".subtask-toggle-btn");
  if (toggleBtn) {
    const row = document.querySelector(`.add-subtask-row[data-parent-id="${toggleBtn.dataset.parentId}"]`);
    row?.classList.toggle("hidden");
    row?.querySelector("input")?.focus();
    return;
  }

  const submitBtn = e.target.closest(".add-subtask-submit");
  if (submitBtn) {
    const parentId = submitBtn.dataset.parentId;
    const row = document.querySelector(`.add-subtask-row[data-parent-id="${parentId}"]`);
    const input = row.querySelector("input");
    const text = input.value.trim();
    if (!text) return;
    const url = URLS.subtaskCreate.replace("__ID__", parentId);
    api(url, { text }).then((res) => {
      let list = document.querySelector(`.task-item[data-id="${parentId}"] .subtask-list`);
      if (!list) {
        list = document.createElement("ul");
        list.className = "subtask-list";
        row.insertAdjacentElement("beforebegin", list);
      }
      const li = document.createElement("li");
      li.className = "subtask-item";
      li.dataset.id = res.subtask.id;
      li.innerHTML = `
        <input type="checkbox" class="subtask-check" data-id="${res.subtask.id}">
        <span class="subtask-text">${escHtml(res.subtask.text)}</span>
        <button class="subtask-delete" data-id="${res.subtask.id}" title="Delete subtask">✕</button>`;
      list.appendChild(li);
      input.value = "";
      row.classList.add("hidden");
    }).catch(() => alert("Failed to add subtask."));
    return;
  }

  const delBtn = e.target.closest(".subtask-delete");
  if (delBtn) {
    const id = delBtn.dataset.id;
    const url = URLS.subtaskDelete.replace("__ID__", id);
    api(url).then(() => {
      document.querySelector(`.subtask-item[data-id="${id}"]`)?.remove();
    }).catch(() => alert("Failed to delete subtask."));
  }
});

document.getElementById("clearCompletedBtn")?.addEventListener("click", async () => {
  try {
    const res = await api(URLS.clearCompleted, { date: VIEW_DATE });
    document.querySelectorAll(".task-item.is-completed").forEach((li) => li.remove());
    updateStats(res.stats);
    applyFilter();
  } catch (err) {
    alert("Failed to clear completed.");
  }
});

document.getElementById("importFileInput")?.addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(URLS.importJson, {
      method: "POST",
      headers: { "X-CSRFToken": CSRF_TOKEN },
      body: formData,
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    alert(`Imported ${data.tasks_created} task(s) for ${data.imported_date}. Redirecting…`);
    window.location.href = data.redirect_url;
  } catch (err) {
    alert("Import failed: " + err.message);
  }
  e.target.value = "";
});

document.getElementById("exportPngBtn")?.addEventListener("click", () => {
  if (typeof html2canvas === "undefined") {
    alert("html2canvas failed to load — check your internet connection.");
    return;
  }
  html2canvas(document.getElementById("captureArea"), {
    backgroundColor: getComputedStyle(document.body).getPropertyValue("--paper") || "#F5F6F1",
    scale: Math.max(2, window.devicePixelRatio || 1),
  }).then((canvas) => {
    canvas.toBlob((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href     = url;
      a.download = `${VIEW_DATE}-daybook.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    });
  });
});
