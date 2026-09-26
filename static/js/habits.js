"use strict";

async function habitApi(url, body = null) {
  const opts = {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": CSRF_TOKEN },
  };
  if (body !== null) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function showBadgeToast(newBadges) {
  if (!newBadges || newBadges.length === 0) return;
  let container = document.getElementById("badgeToastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "badgeToastContainer";
    container.style.cssText = "position:fixed;bottom:20px;left:20px;z-index:60;display:flex;flex-direction:column;gap:8px;";
    document.body.appendChild(container);
  }
  newBadges.forEach((badge) => {
    const toast = document.createElement("div");
    toast.style.cssText = "background:var(--ink);color:var(--paper);border-radius:10px;padding:10px 14px;" +
      "font-size:13px;box-shadow:0 8px 24px -8px rgba(0,0,0,0.35);max-width:260px;";
    toast.innerHTML = `<strong>Badge unlocked:</strong> ${badge.name}`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
  });
}

function updateStreakBadge(card, streak) {
  const badge = card.querySelector(".habit-streak-badge");
  if (!badge) return;
  badge.classList.toggle("is-zero", streak === 0);
  const iconEl = badge.querySelector(".icon");
  badge.innerHTML = "";
  if (iconEl) badge.appendChild(iconEl);
  badge.append(" " + streak);
}

document.querySelectorAll('[data-action="toggle-yesno"]').forEach((btn) => {
  btn.addEventListener("click", async () => {
    const habitId = btn.dataset.habitId;
    const url = HABIT_URLS.toggleYesNo.replace("__ID__", habitId);
    try {
      const res = await habitApi(url);
      btn.classList.toggle("is-completed", res.completed);
      const card = btn.closest(".habit-card");
      if (card) updateStreakBadge(card, res.streak);
    } catch (err) {
      alert("Couldn't update that habit: " + err.message);
    }
  });
});

document.querySelectorAll(".habit-numeric-log-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const habitId = btn.dataset.habitId;
    const card = btn.closest(".habit-card");
    const input = card.querySelector(".habit-numeric-input");
    const value = parseFloat(input.value);
    if (Number.isNaN(value)) {
      alert("Enter a number first.");
      return;
    }
    const url = HABIT_URLS.logNumeric.replace("__ID__", habitId);
    try {
      const res = await habitApi(url, { value });
      updateStreakBadge(card, res.streak);
      showBadgeToast(res.new_badges);
      const track = card.querySelector(".habit-numeric-bar-track");
      const target = parseFloat(card.querySelector(".habit-numeric-target").textContent.replace("/", "").trim());
      if (track && target > 0) {
        const fill = track.querySelector(".habit-numeric-bar-fill");
        const pct = Math.min(100, Math.round((value / target) * 100));
        fill.style.width = pct + "%";
      }
    } catch (err) {
      alert("Couldn't log that value: " + err.message);
    }
  });
});

document.querySelectorAll(".habit-checklist-item input[type=checkbox]").forEach((cb) => {
  cb.addEventListener("change", async () => {
    const habitId = cb.dataset.habitId;
    const itemId = cb.dataset.itemId;
    const url = HABIT_URLS.checklistToggle.replace("__ID__", habitId);
    const row = cb.closest(".habit-checklist-item");
    try {
      const res = await habitApi(url, { item_id: itemId });
      const isChecked = res.checked_item_ids.includes(itemId);
      row.classList.toggle("is-checked", isChecked);
      const card = cb.closest(".habit-card");
      updateStreakBadge(card, res.streak);
      showBadgeToast(res.new_badges);
      const progress = card.querySelector(".habit-checklist-progress");
      if (progress) {
        const total = card.querySelectorAll(".habit-checklist-item").length;
        progress.textContent = `${res.checked_item_ids.length}/${total} done`;
      }
    } catch (err) {
      cb.checked = !cb.checked;
      alert("Couldn't update that item: " + err.message);
    }
  });
});

document.querySelectorAll('[data-action="grace-day"]').forEach((btn) => {
  btn.addEventListener("click", async () => {
    const habitId = btn.dataset.habitId;
    const url = HABIT_URLS.graceDay.replace("__ID__", habitId);
    try {
      const res = await habitApi(url);
      const card = btn.closest(".habit-card");
      updateStreakBadge(card, res.streak);
      showBadgeToast(res.new_badges);
      if (res.grace_remaining > 0) {
        btn.innerHTML = btn.innerHTML.replace(/\(\d+ left\)/, `(${res.grace_remaining} left)`);
      } else {
        btn.remove();
      }
    } catch (err) {
      alert(err.message);
    }
  });
});

document.getElementById("archivedToggle")?.addEventListener("click", () => {
  document.getElementById("archivedList")?.classList.toggle("hidden");
});

function collectAllHabitPositions() {
  const items = [];
  document.querySelectorAll(".habit-cards").forEach((container) => {
    const section = container.dataset.section;
    container.querySelectorAll(".habit-card").forEach((card, index) => {
      items.push({ id: card.dataset.habitId, section, order: index });
    });
  });
  return items;
}

async function persistReorder() {
  try {
    await habitApi(HABIT_URLS.reorder, { items: collectAllHabitPositions() });
  } catch (err) {
    alert("Couldn't save the new order — reloading to stay in sync.");
    location.reload();
  }
}

if (typeof Sortable !== "undefined") {
  document.querySelectorAll(".habit-cards").forEach((container) => {
    Sortable.create(container, {
      group: "habit-sections",
      handle: ".habit-drag-handle",
      animation: 150,
      ghostClass: "sortable-ghost",
      chosenClass: "sortable-chosen",
      onEnd: persistReorder,
    });
  });
}

const selectedHabitIds = new Set();
const habitsWrap = document.querySelector(".habits-wrap");
const bulkBar = document.getElementById("bulkActionBar");
const selectModeBtn = document.getElementById("selectModeBtn");

function updateBulkBar() {
  const count = selectedHabitIds.size;
  document.getElementById("bulkSelectedCount").textContent = `${count} selected`;
  bulkBar?.classList.toggle("hidden", count === 0);
}

function exitSelectMode() {
  selectedHabitIds.clear();
  habitsWrap?.classList.remove("is-selecting");
  document.querySelectorAll(".select-checkbox").forEach((cb) => { cb.checked = false; });
  document.querySelectorAll(".habit-card.is-selected").forEach((c) => c.classList.remove("is-selected"));
  updateBulkBar();
}

selectModeBtn?.addEventListener("click", () => {
  const active = habitsWrap.classList.toggle("is-selecting");
  if (!active) exitSelectMode();
});

document.querySelectorAll(".select-checkbox").forEach((cb) => {
  cb.addEventListener("change", () => {
    const id = cb.dataset.habitId;
    const card = cb.closest(".habit-card");
    if (cb.checked) {
      selectedHabitIds.add(id);
      card?.classList.add("is-selected");
    } else {
      selectedHabitIds.delete(id);
      card?.classList.remove("is-selected");
    }
    updateBulkBar();
  });
});

document.getElementById("bulkCancelBtn")?.addEventListener("click", exitSelectMode);

async function runBulkAction(action, extra = {}) {
  if (selectedHabitIds.size === 0) return;
  try {
    await habitApi(HABIT_URLS.bulkAction, { ids: Array.from(selectedHabitIds), action, ...extra });
    location.reload();
  } catch (err) {
    alert("Bulk action failed: " + err.message);
  }
}

document.getElementById("bulkMoveBtn")?.addEventListener("click", () => {
  const section = document.getElementById("bulkMoveSection").value;
  runBulkAction("move", { section });
});

document.getElementById("bulkArchiveBtn")?.addEventListener("click", () => {
  runBulkAction("archive");
});

document.getElementById("bulkDeleteBtn")?.addEventListener("click", () => {
  if (!confirm(`Delete ${selectedHabitIds.size} habit(s) permanently? This also deletes their history.`)) return;
  runBulkAction("delete");
});
