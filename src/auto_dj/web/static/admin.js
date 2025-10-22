const loginForm = document.getElementById("login-form");
const loginCard = document.getElementById("login-card");
const accountsCard = document.getElementById("accounts-card");
const accountsList = document.getElementById("accounts-list");
const logoutButton = document.getElementById("logout-button");
const toast = document.getElementById("toast");
const toastMessage = document.getElementById("toast-message");

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
      loginCard.hidden = true;
      accountsCard.hidden = false;
      showToast("Anmeldung erfolgreich", "success");
      await fetchAccounts();
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
      window.location.reload();
    }
  });
}

if (accountsCard && !accountsCard.hasAttribute("hidden")) {
  fetchAccounts();
}
