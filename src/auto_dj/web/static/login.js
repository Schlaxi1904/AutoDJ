const loginForm = document.getElementById("login-form");
const toast = document.getElementById("toast");
const toastMessage = document.getElementById("toast-message");

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

if (loginForm) {
  loginForm.addEventListener("submit", submitLogin);
  const username = document.getElementById("login-username");
  if (username) {
    username.focus();
  }
}
