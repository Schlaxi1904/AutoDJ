const loginForm = document.getElementById("login-form");
const loginCard = document.getElementById("login-card");
const accountsCard = document.getElementById("accounts-card");
const accountsList = document.getElementById("accounts-list");
const dashboardCard = document.getElementById("dashboard-card");
const dashboardNowPlaying = document.getElementById("dashboard-now-playing");
const dashboardRemaining = document.getElementById("dashboard-remaining");
const dashboardQueue = document.getElementById("dashboard-queue");
const refreshDashboardButton = document.getElementById("refresh-dashboard");
const logoutButton = document.getElementById("logout-button");
const toast = document.getElementById("toast");
const toastMessage = document.getElementById("toast-message");

let dashboardInterval = null;

function showToast(message, variant = "info") {
  toastMessage.textContent = message;
  toast.dataset.variant = variant;
  toast.hidden = false;
  setTimeout(() => {
    toast.hidden = true;
    toastMessage.textContent = "";
  }, 3500);
}

async function fetchAccounts() {
  try {
    const response = await fetch("/admin/accounts");
    if (!response.ok) {
      throw new Error("Laden der Accounts fehlgeschlagen");
    }
    const accounts = await response.json();
    renderAccounts(accounts);
  } catch (error) {
    showToast(error.message || "Unbekannter Fehler", "error");
  }
}

function renderAccounts(accounts) {
  accountsList.innerHTML = "";
  if (!accounts.length) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = "Keine Admin-Accounts gefunden.";
    accountsList.appendChild(empty);
    return;
  }

  for (const account of accounts) {
    const card = document.createElement("article");
    card.className = "account-item";
    card.setAttribute("role", "listitem");

    const header = document.createElement("header");
    header.className = "account-item__header";
    header.innerHTML = `<h3>${account.username}</h3>`;
    if (account.last_login_at) {
      const lastLogin = document.createElement("span");
      lastLogin.className = "account-item__meta";
      const date = new Date(account.last_login_at);
      lastLogin.textContent = `Zuletzt angemeldet: ${date.toLocaleString()}`;
      header.appendChild(lastLogin);
    }
    card.appendChild(header);

    const form = document.createElement("form");
    form.className = "admin-form account-item__form";
    form.innerHTML = `
      <label class="input">
        <span class="input__label">Neues Passwort</span>
        <input type="password" name="new_password" minlength="8" required />
      </label>
      <button class="button" type="submit">Passwort speichern</button>
    `;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(form);
      const newPassword = formData.get("new_password");
      try {
        const response = await fetch(`/admin/accounts/${account.id}/password`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ new_password: newPassword }),
        });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail || "Speichern fehlgeschlagen");
        }
        form.reset();
        showToast(`Passwort für ${account.username} aktualisiert`, "success");
      } catch (error) {
        showToast(error.message || "Unbekannter Fehler", "error");
      }
    });
    card.appendChild(form);

    accountsList.appendChild(card);
  }
}

function renderNowPlaying(entry) {
  dashboardNowPlaying.innerHTML = "";
  if (!entry) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = "Keine Wiedergabe aktiv.";
    dashboardNowPlaying.appendChild(empty);
    return;
  }

  const card = document.createElement("article");
  card.className = "dashboard-now__card";
  card.innerHTML = `
    <header>
      <h4>${entry.track.title}</h4>
      <p>${entry.track.artist}</p>
    </header>
    <dl>
      <div><dt>Quelle</dt><dd>${entry.source}</dd></div>
      <div><dt>Status</dt><dd>${entry.status}</dd></div>
      <div><dt>Energie</dt><dd>${Math.round(entry.track.energy_avg * 100)}%</dd></div>
      <div><dt>BPM</dt><dd>${Math.round(entry.track.bpm)}</dd></div>
    </dl>
  `;
  dashboardNowPlaying.appendChild(card);
}

function createQueueAction(label, action) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "button button--ghost queue-action";
  button.textContent = label;
  button.dataset.action = action;
  return button;
}

function renderQueue(entries) {
  dashboardQueue.innerHTML = "";
  if (!entries.length) {
    const empty = document.createElement("li");
    empty.className = "admin-empty";
    empty.textContent = "Keine Einträge in der Queue.";
    dashboardQueue.appendChild(empty);
    return;
  }

  for (const entry of entries) {
    const item = document.createElement("li");
    item.className = "dashboard-queue__item";
    item.dataset.entryId = entry.id;

    const meta = document.createElement("div");
    meta.className = "dashboard-queue__meta";
    meta.innerHTML = `
      <h4>${entry.track.title}</h4>
      <p>${entry.track.artist}</p>
      <span class="badge">${entry.source}</span>
    `;
    item.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "dashboard-queue__actions";
    const playButton = createQueueAction("Als Nächstes", "play");
    const promoteButton = createQueueAction("Priorisieren", "promote");
    const deleteButton = createQueueAction("Entfernen", "delete");
    actions.append(playButton, promoteButton, deleteButton);
    item.appendChild(actions);

    dashboardQueue.appendChild(item);
  }
}

async function fetchDashboard() {
  try {
    const response = await fetch("/admin/state");
    if (!response.ok) {
      throw new Error("Dashboard konnte nicht geladen werden");
    }
    const data = await response.json();
    dashboardRemaining.textContent = data.remaining_slots;
    renderNowPlaying(data.now_playing);
    renderQueue(data.queue);
  } catch (error) {
    showToast(error.message || "Unbekannter Fehler", "error");
  }
}

function stopDashboardUpdates() {
  if (dashboardInterval) {
    clearInterval(dashboardInterval);
    dashboardInterval = null;
  }
}

function startDashboardUpdates() {
  stopDashboardUpdates();
  fetchDashboard();
  dashboardInterval = setInterval(fetchDashboard, 5000);
}

function setAuthenticated(isAuthenticated) {
  if (!loginCard || !accountsCard || !dashboardCard) {
    return;
  }
  loginCard.hidden = isAuthenticated;
  accountsCard.hidden = !isAuthenticated;
  dashboardCard.hidden = !isAuthenticated;

  if (isAuthenticated) {
    fetchAccounts();
    startDashboardUpdates();
  } else {
    stopDashboardUpdates();
    accountsList.innerHTML = "";
    dashboardQueue.innerHTML = "";
    dashboardNowPlaying.innerHTML = "";
  }
}

if (loginForm) {
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(loginForm);
    const payload = Object.fromEntries(formData.entries());
    try {
      const response = await fetch("/admin/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Login fehlgeschlagen");
      }
      showToast("Anmeldung erfolgreich", "success");
      setAuthenticated(true);
    } catch (error) {
      showToast(error.message || "Unbekannter Fehler", "error");
    }
  });
}

if (logoutButton) {
  logoutButton.addEventListener("click", async () => {
    try {
      await fetch("/admin/logout", { method: "POST" });
    } finally {
      showToast("Abgemeldet", "info");
      setAuthenticated(false);
      window.location.reload();
    }
  });
}

if (dashboardCard && !dashboardCard.hasAttribute("hidden")) {
  setAuthenticated(true);
}

if (refreshDashboardButton) {
  refreshDashboardButton.addEventListener("click", () => {
    fetchDashboard();
  });
}

if (dashboardQueue) {
  dashboardQueue.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const action = target.dataset.action;
    if (!action) {
      return;
    }
    const item = target.closest(".dashboard-queue__item");
    if (!item) {
      return;
    }
    const entryId = item.dataset.entryId;
    if (!entryId) {
      return;
    }

    try {
      if (action === "delete") {
        const response = await fetch(`/admin/queue/${entryId}`, { method: "DELETE" });
        if (!response.ok) {
          throw new Error("Entfernen fehlgeschlagen");
        }
      } else if (action === "promote") {
        const response = await fetch(`/admin/queue/${entryId}/promote`, { method: "POST" });
        if (!response.ok) {
          throw new Error("Priorisieren fehlgeschlagen");
        }
      } else if (action === "play") {
        const response = await fetch(`/admin/queue/${entryId}/play`, { method: "POST" });
        if (!response.ok) {
          throw new Error("Übergabe fehlgeschlagen");
        }
      }
      showToast("Aktion ausgeführt", "success");
      fetchDashboard();
    } catch (error) {
      showToast(error.message || "Unbekannter Fehler", "error");
    }
  });
}
