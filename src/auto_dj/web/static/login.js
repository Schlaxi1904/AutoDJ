const loginForm = document.getElementById("login-form");
const toast = document.getElementById("toast");
const toastMessage = document.getElementById("toast-message");
const resetToggle = document.getElementById("reset-toggle");
const resetForm = document.getElementById("reset-form");

function showToast(message, variant = "info") {
  if (!toast || !toastMessage) {
    return;
  }
  toastMessage.textContent = message;
  toast.dataset.variant = variant;
  toast.hidden = false;
  setTimeout(() => {
    toast.hidden = true;
    toastMessage.textContent = "";
  }, 3000);
}

async function submitLogin(event) {
  event.preventDefault();
  if (!loginForm) {
    return;
  }
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
    window.location.href = "/admin";
  } catch (error) {
    if (error instanceof Error) {
      showToast(error.message, "error");
    } else {
      showToast("Unbekannter Fehler", "error");
    }
  }
}

function toggleResetForm() {
  if (!resetForm) {
    return;
  }
  const shouldShow = resetForm.hasAttribute("hidden");
  if (shouldShow) {
    resetForm.removeAttribute("hidden");
    const username = resetForm.querySelector("#reset-username");
    if (username instanceof HTMLInputElement) {
      username.focus();
    }
  } else {
    resetForm.setAttribute("hidden", "hidden");
  }
}

async function submitPasswordReset(event) {
  event.preventDefault();
  if (!resetForm) {
    return;
  }
  const formData = new FormData(resetForm);
  const username = formData.get("username");
  const newPassword = formData.get("new_password");
  const confirmPassword = formData.get("confirm_password");
  const resetCode = formData.get("reset_code");

  if (!username || !newPassword || !confirmPassword || !resetCode) {
    showToast("Bitte alle Felder ausfüllen", "error");
    return;
  }

  if (newPassword !== confirmPassword) {
    showToast("Passwörter stimmen nicht überein", "error");
    return;
  }

  try {
    const response = await fetch("/admin/password-reset", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        new_password: newPassword,
        reset_code: resetCode,
      }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "Zurücksetzen fehlgeschlagen");
    }
    resetForm.reset();
    resetForm.setAttribute("hidden", "hidden");
    showToast("Passwort erfolgreich zurückgesetzt", "success");
  } catch (error) {
    if (error instanceof Error) {
      showToast(error.message, "error");
    } else {
      showToast("Unbekannter Fehler", "error");
    }
  }
}

if (loginForm) {
  loginForm.addEventListener("submit", submitLogin);
  const username = document.getElementById("login-username");
  if (username) {
    username.focus();
  }
}

if (resetToggle) {
  resetToggle.addEventListener("click", toggleResetForm);
}

if (resetForm) {
  resetForm.addEventListener("submit", submitPasswordReset);
}
