const controlCard = document.getElementById("control-card");
const accountsList = document.getElementById("accounts-list");
const logoutButton = document.getElementById("logout-button");
const toast = document.getElementById("toast");
const toastMessage = document.getElementById("toast-message");

const tabButtons = Array.from(document.querySelectorAll(".tab-button"));
const tabPanels = Array.from(document.querySelectorAll(".tab-panel"));

const systemNowPlaying = document.getElementById("system-now-playing");
const systemNextTrack = document.getElementById("system-next-track");
const systemQueue = document.getElementById("system-queue");
const systemRemaining = document.getElementById("system-remaining");
const systemRefreshButton = document.getElementById("system-refresh");
const systemCpu = document.getElementById("system-cpu");
const systemRam = document.getElementById("system-ram");
const systemTemp = document.getElementById("system-temp");
const systemXruns = document.getElementById("system-xruns");
const systemOsc = document.getElementById("system-osc");
const systemNetwork = document.getElementById("system-network");
const systemTogglesForm = document.getElementById("system-toggles-form");

const toggleFog = document.getElementById("toggle-fog");
const toggleSuperscenes = document.getElementById("toggle-superscenes");
const togglePublic = document.getElementById("toggle-public");
const lightFogToggle = document.getElementById("light-fog");
const lightSuperscenesToggle = document.getElementById("light-superscenes");

const audioScanButton = document.getElementById("audio-scan");
const audioForm = document.getElementById("audio-output-form");
const audioDeviceSelect = document.getElementById("audio-device-select");

const bluetoothScanButton = document.getElementById("bluetooth-scan");
const bluetoothRefreshButton = document.getElementById("bluetooth-refresh");
const bluetoothPairForm = document.getElementById("bluetooth-pair-form");
const bluetoothAddressInput = document.getElementById("bluetooth-address");
const bluetoothSetDefault = document.getElementById("bluetooth-set-default");
const bluetoothDeviceList = document.getElementById("bluetooth-devices");

const mixerForm = document.getElementById("mixer-form");
const mixerCrossfade = document.getElementById("mixer-crossfade");
const mixerVolumeCurve = document.getElementById("mixer-volume-curve");
const mixerBassHz = document.getElementById("mixer-bass-hz");
const mixerBassCurve = document.getElementById("mixer-bass-curve");
const mixerFilterHp = document.getElementById("mixer-filter-hp");
const mixerFilterLp = document.getElementById("mixer-filter-lp");
const mixerTimeStretch = document.getElementById("mixer-time-stretch");

const libraryForm = document.getElementById("library-form");
const libraryTrackCount = document.getElementById("library-track-count");
const libraryQuarantine = document.getElementById("library-quarantine");
const libraryFilesystemCount = document.getElementById("library-filesystem-count");
const libraryFilesystemPreview = document.getElementById("library-filesystem-preview");
const libraryMusicSelect = document.getElementById("library-music-select");
const libraryMusicPath = document.getElementById("library-music-path");
const libraryDatabaseDsn = document.getElementById("library-database-dsn");
const libraryRescanButton = document.getElementById("library-rescan");
const playlistRefreshButton = document.getElementById("playlist-refresh");
const playlistList = document.getElementById("playlist-list");
const playlistCreateForm = document.getElementById("playlist-create-form");
const playlistCreateName = document.getElementById("playlist-create-name");
const playlistCreateDescription = document.getElementById("playlist-create-description");
const playlistEmpty = document.getElementById("playlist-empty");
const playlistDetailContent = document.getElementById("playlist-detail-content");
const playlistDetailName = document.getElementById("playlist-detail-name");
const playlistDetailDescription = document.getElementById("playlist-detail-description");
const playlistDetailCount = document.getElementById("playlist-detail-count");
const playlistDetailFallback = document.getElementById("playlist-detail-fallback");
const playlistSetFallbackButton = document.getElementById("playlist-set-fallback");
const playlistDeleteButton = document.getElementById("playlist-delete");
const playlistEditForm = document.getElementById("playlist-edit-form");
const playlistEditName = document.getElementById("playlist-edit-name");
const playlistEditDescription = document.getElementById("playlist-edit-description");
const playlistTrackSearchInput = document.getElementById("playlist-track-search");
const playlistTrackSearchButton = document.getElementById("playlist-track-search-button");
const playlistTrackResults = document.getElementById("playlist-track-results");
const playlistTracksList = document.getElementById("playlist-tracks");

const lightForm = document.getElementById("light-form");
const lightHost = document.getElementById("light-host");
const lightPort = document.getElementById("light-port");
const lightResyncButton = document.getElementById("light-resync");
const lightBindingsContainer = document.getElementById("light-bindings");

const analysisForm = document.getElementById("analysis-form");
const analysisKey = document.getElementById("analysis-key");
const analysisBpm = document.getElementById("analysis-bpm");
const analysisEnergy = document.getElementById("analysis-energy");
const analysisGenre = document.getElementById("analysis-genre");
const analysisRecency = document.getElementById("analysis-recency");
const analysisRequest = document.getElementById("analysis-request");
const analysisSpacing = document.getElementById("analysis-spacing");

const diagnosticsRuntime = document.getElementById("diagnostics-runtime");
const diagnosticsPersistent = document.getElementById("diagnostics-persistent");
const diagnosticsCache = document.getElementById("diagnostics-cache");
const diagnosticsConfig = document.getElementById("diagnostics-config");
const diagnosticsLastError = document.getElementById("diagnostics-last-error");
const diagnosticsRunButton = document.getElementById("diagnostics-run");
const diagnosticsResults = document.getElementById("diagnostics-results");

let systemInterval = null;
let togglesUpdating = false;
const LIGHT_DEFAULT_ACTION_ORDER = ["idle", "break", "build", "drop", "outro"];
let lightActionLabels = {};
let playlistSummaries = [];
let currentPlaylistId = null;
let playlistTrackSearchAbort = null;

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => {
    switch (char) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      case "'":
        return "&#39;";
      default:
        return char;
    }
  });
}

function formatDuration(durationMs) {
  if (!Number.isFinite(durationMs)) {
    return "--:--";
  }
  const totalSeconds = Math.max(0, Math.round(durationMs / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

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
  }, 3500);
}

async function apiFetch(url, options = {}) {
  try {
    const response = await fetch(url, options);
    if (response.status === 401) {
      setAuthenticated(false);
      throw new Error("Session abgelaufen. Bitte erneut anmelden.");
    }
    return response;
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("Netzwerkfehler");
  }
}

function activateTab(target) {
  tabButtons.forEach((button) => {
    const isActive = button.dataset.tabTarget === target;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  tabPanels.forEach((panel) => {
    const isActive = panel.dataset.tab === target;
    panel.classList.toggle("is-active", isActive);
    if (isActive) {
      panel.removeAttribute("hidden");
    } else {
      panel.setAttribute("hidden", "true");
    }
  });
}

function stopSystemUpdates() {
  if (systemInterval) {
    clearInterval(systemInterval);
    systemInterval = null;
  }
}

function startSystemUpdates() {
  stopSystemUpdates();
  fetchSystemOverview();
  systemInterval = setInterval(fetchSystemOverview, 5000);
}

function clearSystemCards() {
  if (systemNowPlaying) {
    systemNowPlaying.innerHTML = "<p class=\"admin-empty\">Keine Wiedergabe aktiv.</p>";
  }
  if (systemNextTrack) {
    systemNextTrack.innerHTML = "";
  }
  if (systemQueue) {
    systemQueue.innerHTML = "";
  }
  if (systemRemaining) {
    systemRemaining.textContent = "--";
  }
}

function setAuthenticated(isAuthenticated) {
  if (!isAuthenticated) {
    stopSystemUpdates();
    clearSystemCards();
    window.location.href = "/admin/login";
    return;
  }

  if (controlCard) {
    controlCard.hidden = false;
  }
  activateTab("system");
  loadControlCenter();
  startSystemUpdates();
}

function renderAccounts(accounts) {
  if (!accountsList) {
    return;
  }
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
        const response = await apiFetch(`/admin/accounts/${account.id}/password`, {
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
  if (!systemNowPlaying) {
    return;
  }
  systemNowPlaying.innerHTML = "";
  if (!entry) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = "Keine Wiedergabe aktiv.";
    systemNowPlaying.appendChild(empty);
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
  systemNowPlaying.appendChild(card);
}

function renderNext(entry) {
  if (!systemNextTrack) {
    return;
  }
  systemNextTrack.innerHTML = "";
  if (!entry) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = "Kein nächster Titel geplant.";
    systemNextTrack.appendChild(empty);
    return;
  }
  const wrapper = document.createElement("p");
  wrapper.innerHTML = `<strong>Nächster Track:</strong> ${entry.track.title} – ${entry.track.artist}`;
  systemNextTrack.appendChild(wrapper);
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
  if (!systemQueue) {
    return;
  }
  systemQueue.innerHTML = "";
  if (!entries.length) {
    const empty = document.createElement("li");
    empty.className = "admin-empty";
    empty.textContent = "Keine Einträge in der Queue.";
    systemQueue.appendChild(empty);
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
    actions.append(
      createQueueAction("Als Nächstes", "play"),
      createQueueAction("Priorisieren", "promote"),
      createQueueAction("Entfernen", "delete"),
    );
    item.appendChild(actions);

    systemQueue.appendChild(item);
  }
}

function updateToggleInputs(toggles) {
  togglesUpdating = true;
  if (toggleFog) {
    toggleFog.checked = Boolean(toggles.fog_enabled);
  }
  if (toggleSuperscenes) {
    toggleSuperscenes.checked = Boolean(toggles.superscenes_enabled);
  }
  if (togglePublic) {
    togglePublic.checked = Boolean(toggles.public_enabled);
  }
  if (lightFogToggle) {
    lightFogToggle.checked = Boolean(toggles.fog_enabled);
  }
  if (lightSuperscenesToggle) {
    lightSuperscenesToggle.checked = Boolean(toggles.superscenes_enabled);
  }
  togglesUpdating = false;
}

function renderSystemOverview(data) {
  renderNowPlaying(data.now_playing);
  renderNext(data.next_entry);
  renderQueue(data.queue || []);
  if (systemRemaining) {
    systemRemaining.textContent = data.remaining_slots;
  }
  if (systemCpu) {
    systemCpu.textContent =
      typeof data.cpu_percent === "number" ? `${data.cpu_percent.toFixed(1)} %` : "--";
  }
  if (systemRam) {
    systemRam.textContent =
      typeof data.memory_percent === "number" ? `${data.memory_percent.toFixed(1)} %` : "--";
  }
  if (systemTemp) {
    systemTemp.textContent =
      typeof data.temperature_c === "number" ? `${data.temperature_c.toFixed(1)} °C` : "--";
  }
  if (systemXruns) {
    systemXruns.textContent = data.xrun_count;
  }
  if (systemOsc) {
    systemOsc.textContent = data.osc_connected ? "Aktiv" : "Timeout";
  }
  if (systemNetwork) {
    systemNetwork.textContent = data.network_mode;
  }
  if (data.toggles) {
    updateToggleInputs(data.toggles);
  }
}

function getLightActionOrder(labels = {}) {
  const order = [];
  for (const key of Object.keys(labels)) {
    if (!order.includes(key)) {
      order.push(key);
    }
  }
  for (const fallback of LIGHT_DEFAULT_ACTION_ORDER) {
    if (!order.includes(fallback)) {
      order.push(fallback);
    }
  }
  return order;
}

function renderLightBindings(bindings = [], labels = {}) {
  if (!lightBindingsContainer) {
    return;
  }
  lightBindingsContainer.innerHTML = "";
  lightActionLabels = labels ? { ...labels } : {};
  const order = getLightActionOrder(lightActionLabels);
  if (!Array.isArray(bindings) || bindings.length === 0) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = "Keine Zuordnungen verfügbar.";
    lightBindingsContainer.appendChild(empty);
    return;
  }

  for (const binding of bindings) {
    const panel = document.createElement("div");
    panel.className = "light-binding";
    if (binding.genre) {
      panel.dataset.genre = binding.genre;
    }
    if (typeof binding.bank === "number" && binding.bank > 0) {
      panel.dataset.bank = String(binding.bank);
    }

    const title = document.createElement("div");
    title.className = "light-binding__title";
    const bankSuffix = binding.bank && binding.bank > 0 ? ` (Bank ${binding.bank})` : "";
    title.textContent = `${binding.label || binding.genre}${bankSuffix}`;
    panel.appendChild(title);

    const grid = document.createElement("div");
    grid.className = "light-binding__grid";

    for (const action of order) {
      const wrapper = document.createElement("label");
      wrapper.className = "input";
      const span = document.createElement("span");
      span.className = "input__label";
      span.textContent = lightActionLabels[action] || action;
      const input = document.createElement("input");
      input.type = "number";
      input.min = "0";
      input.max = "99";
      input.step = "1";
      input.placeholder = "--";
      input.dataset.action = action;
      if (binding.actions && action in binding.actions && binding.actions[action] !== null) {
        input.value = binding.actions[action];
      }
      wrapper.appendChild(span);
      wrapper.appendChild(input);
      grid.appendChild(wrapper);
    }

    panel.appendChild(grid);
    lightBindingsContainer.appendChild(panel);
  }
}

function collectLightBindings() {
  if (!lightBindingsContainer) {
    return null;
  }
  const result = {};
  const panels = Array.from(lightBindingsContainer.querySelectorAll(".light-binding"));
  for (const panel of panels) {
    const genre = panel.dataset.genre;
    if (!genre) {
      continue;
    }
    const inputs = Array.from(panel.querySelectorAll("input[data-action]"));
    const actionMap = {};
    for (const input of inputs) {
      if (!(input instanceof HTMLInputElement)) {
        continue;
      }
      const action = input.dataset.action;
      if (!action) {
        continue;
      }
      const value = input.value.trim();
      if (!value) {
        continue;
      }
      const parsed = Number.parseInt(value, 10);
      if (Number.isNaN(parsed)) {
        continue;
      }
      actionMap[action] = parsed;
    }
    if (Object.keys(actionMap).length > 0) {
      result[genre] = actionMap;
    }
  }
  return Object.keys(result).length > 0 ? result : null;
}

async function fetchSystemOverview() {
  try {
    const response = await apiFetch("/admin/system/overview");
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "Systemstatus konnte nicht geladen werden");
    }
    const data = await response.json();
    renderSystemOverview(data);
  } catch (error) {
    showToast(error.message || "Unbekannter Fehler", "error");
  }
}

async function fetchAccounts() {
  try {
    const response = await apiFetch("/admin/accounts");
    if (!response.ok) {
      throw new Error("Laden der Accounts fehlgeschlagen");
    }
    const accounts = await response.json();
    renderAccounts(accounts);
  } catch (error) {
    showToast(error.message || "Unbekannter Fehler", "error");
  }
}

function populateSelect(select, items, valueKey, labelKey, activeValue) {
  select.innerHTML = "";
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item[valueKey];
    option.textContent = item[labelKey];
    select.appendChild(option);
  }
  if (activeValue) {
    select.value = activeValue;
  }
}

async function fetchAudioOutput(showToastMessage = false) {
  if (!audioDeviceSelect) {
    return;
  }
  try {
    const response = await apiFetch("/admin/audio/output");
    if (!response.ok) {
      throw new Error("Audio-Ausgänge konnten nicht geladen werden");
    }
    const data = await response.json();
    populateSelect(audioDeviceSelect, data.devices, "identifier", "label", data.active_device_id);
    if (showToastMessage) {
      showToast("Geräteliste aktualisiert", "success");
    }
  } catch (error) {
    showToast(error.message || "Unbekannter Fehler", "error");
  }
}

function renderBluetoothDevices(devices) {
  if (!bluetoothDeviceList) {
    return;
  }
  bluetoothDeviceList.innerHTML = "";
  if (!Array.isArray(devices) || !devices.length) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = "Noch keine Geräte gefunden.";
    bluetoothDeviceList.appendChild(empty);
    return;
  }

  devices.forEach((device) => {
    const item = document.createElement("div");
    item.className = "bluetooth-device";
    item.dataset.address = device.address;

    const meta = document.createElement("div");
    meta.className = "bluetooth-device__meta";

    const name = document.createElement("div");
    name.className = "bluetooth-device__name";
    name.textContent = device.name || device.address;
    meta.appendChild(name);

    const status = document.createElement("div");
    status.className = "bluetooth-device__status";
    const addressSpan = document.createElement("span");
    addressSpan.textContent = device.address;
    const statusSpan = document.createElement("span");
    const statusParts = [device.connected ? "Verbunden" : "Getrennt"];
    if (device.paired) statusParts.push("Gekoppelt");
    if (device.trusted) statusParts.push("Vertraut");
    statusSpan.textContent = statusParts.join(" · ") || "Unbekannter Status";
    status.append(addressSpan, statusSpan);
    meta.appendChild(status);

    const actions = document.createElement("div");
    actions.className = "bluetooth-device__actions";

    if (device.connected) {
      const disconnect = document.createElement("button");
      disconnect.type = "button";
      disconnect.className = "button button--ghost";
      disconnect.dataset.action = "disconnect";
      disconnect.dataset.address = device.address;
      disconnect.textContent = "Trennen";
      actions.appendChild(disconnect);

      const setOutput = document.createElement("button");
      setOutput.type = "button";
      setOutput.className = "button";
      setOutput.dataset.action = "connect-default";
      setOutput.dataset.address = device.address;
      setOutput.textContent = "Als Ausgabe setzen";
      actions.appendChild(setOutput);
    } else {
      const connect = document.createElement("button");
      connect.type = "button";
      connect.className = "button button--ghost";
      connect.dataset.action = "connect";
      connect.dataset.address = device.address;
      connect.textContent = "Verbinden";
      actions.appendChild(connect);

      const connectDefault = document.createElement("button");
      connectDefault.type = "button";
      connectDefault.className = "button";
      connectDefault.dataset.action = "connect-default";
      connectDefault.dataset.address = device.address;
      connectDefault.textContent = "Verbinden & Ausgabe";
      actions.appendChild(connectDefault);
    }

    item.append(meta, actions);
    bluetoothDeviceList.appendChild(item);
  });
}

async function fetchBluetoothDevices(showToastMessage = false) {
  if (!bluetoothDeviceList) {
    return;
  }
  try {
    const response = await apiFetch("/admin/audio/bluetooth");
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "Bluetooth-Geräte konnten nicht geladen werden");
    }
    const data = await response.json();
    renderBluetoothDevices(data.devices || []);
    if (showToastMessage) {
      showToast("Bluetooth-Liste aktualisiert", "success");
    }
  } catch (error) {
    renderBluetoothDevices([]);
    showToast(error.message || "Bluetooth-Geräte konnten nicht geladen werden", "error");
  }
}

async function scanBluetoothDevices() {
  if (!bluetoothDeviceList) {
    return;
  }
  try {
    const response = await apiFetch("/admin/audio/bluetooth/scan", { method: "POST" });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "Scan fehlgeschlagen");
    }
    const data = await response.json();
    renderBluetoothDevices(data.devices || []);
    showToast("Bluetooth-Scan abgeschlossen", "success");
  } catch (error) {
    showToast(error.message || "Scan fehlgeschlagen", "error");
  }
}

async function fetchMixerSettings() {
  if (!mixerForm) {
    return;
  }
  try {
    const response = await apiFetch("/admin/audio/mixer");
    if (!response.ok) {
      throw new Error("Mixer-Einstellungen konnten nicht geladen werden");
    }
    const data = await response.json();
    if (mixerCrossfade) mixerCrossfade.value = data.crossfade_seconds;
    if (mixerVolumeCurve) mixerVolumeCurve.value = data.volume_curve;
    if (mixerBassHz) mixerBassHz.value = data.bass_crossover_hz;
    if (mixerBassCurve) mixerBassCurve.value = data.bass_curve;
    if (mixerFilterHp) mixerFilterHp.checked = data.filter_hp_to_lp;
    if (mixerFilterLp) mixerFilterLp.checked = data.filter_lp_to_hp;
    if (mixerTimeStretch) mixerTimeStretch.value = data.time_stretch_mode;
  } catch (error) {
    showToast(error.message || "Unbekannter Fehler", "error");
  }
}

async function fetchLibrarySettings() {
  try {
    const response = await apiFetch("/admin/library/settings");
    if (!response.ok) {
      throw new Error("Bibliotheksdaten konnten nicht geladen werden");
    }
    const data = await response.json();
    if (libraryTrackCount) libraryTrackCount.textContent = data.track_count;
    if (libraryQuarantine) libraryQuarantine.textContent = data.quarantine_path;
    if (libraryFilesystemCount) libraryFilesystemCount.textContent = data.filesystem_count;
    if (libraryFilesystemPreview) {
      if (Array.isArray(data.filesystem_preview) && data.filesystem_preview.length) {
        libraryFilesystemPreview.innerHTML = data.filesystem_preview
          .map((item) => `<span>${escapeHtml(item)}</span>`)
          .join("");
      } else {
        libraryFilesystemPreview.innerHTML = "<span>Keine Mediendateien gefunden</span>";
      }
    }
    if (libraryMusicPath) libraryMusicPath.value = data.music_path;
    if (libraryDatabaseDsn) libraryDatabaseDsn.value = data.database_dsn;
    await refreshMusicLocations(data.music_path);
  } catch (error) {
    showToast(error.message || "Unbekannter Fehler", "error");
  }
}

function syncLibrarySelectWithInput() {
  if (!libraryMusicSelect || !libraryMusicPath) {
    return;
  }
  const value = libraryMusicPath.value.trim();
  const matchingOption = Array.from(libraryMusicSelect.options).find(
    (option) => option.value === value && option.value !== "__custom__"
  );
  if (matchingOption) {
    libraryMusicSelect.value = matchingOption.value;
  } else {
    libraryMusicSelect.value = "__custom__";
  }
}

async function refreshMusicLocations(currentPath) {
  if (!libraryMusicSelect) {
    return false;
  }
  const desiredPath = typeof currentPath === "string" && currentPath.length
    ? currentPath.trim()
    : (libraryMusicPath?.value || "").trim();
  try {
    const response = await apiFetch("/admin/library/locations");
    if (!response.ok) {
      throw new Error("Speicherorte konnten nicht geladen werden");
    }
    const locations = await response.json();
    libraryMusicSelect.innerHTML = "";
    let matched = false;
    locations.forEach((location) => {
      const option = document.createElement("option");
      option.value = location.path;
      option.dataset.kind = location.kind;
      option.textContent = `${location.label} — ${location.path}${
        location.available ? "" : " (nicht gefunden)"
      }`;
      if (desiredPath && location.path === desiredPath) {
        option.selected = true;
        matched = true;
      }
      libraryMusicSelect.appendChild(option);
    });
    const customOption = document.createElement("option");
    customOption.value = "__custom__";
    customOption.textContent = "Eigener Pfad …";
    if (!matched) {
      customOption.selected = true;
    }
    libraryMusicSelect.appendChild(customOption);
    if (libraryMusicPath) {
      if (desiredPath) {
        libraryMusicPath.value = desiredPath;
      } else if (matched && libraryMusicSelect.value !== "__custom__") {
        libraryMusicPath.value = libraryMusicSelect.value;
      }
      syncLibrarySelectWithInput();
    }
  } catch (error) {
    showToast(error.message || "Speicherorte konnten nicht geladen werden", "error");
    return false;
  }
  return true;
}

function getFallbackPlaylistId() {
  const fallback = playlistSummaries.find((item) => item.is_fallback);
  return fallback ? fallback.id : null;
}

function resetPlaylistDetail() {
  currentPlaylistId = null;
  if (playlistDetailContent) playlistDetailContent.hidden = true;
  if (playlistEmpty) playlistEmpty.hidden = false;
  if (playlistDetailName) playlistDetailName.textContent = "Playlist";
  if (playlistDetailDescription) playlistDetailDescription.textContent = "";
  if (playlistDetailCount) playlistDetailCount.textContent = "0 Titel";
  if (playlistDetailFallback) playlistDetailFallback.hidden = true;
  if (playlistSetFallbackButton) {
    playlistSetFallbackButton.disabled = true;
    playlistSetFallbackButton.textContent = "Als Autoplay nutzen";
  }
  if (playlistDeleteButton) playlistDeleteButton.disabled = true;
  if (playlistEditName) playlistEditName.value = "";
  if (playlistEditDescription) playlistEditDescription.value = "";
  if (playlistTrackResults) playlistTrackResults.innerHTML = "";
  if (playlistTracksList) playlistTracksList.innerHTML = "";
}

function renderPlaylistList(summaries) {
  if (!playlistList) {
    return;
  }
  playlistList.innerHTML = "";
  if (!summaries.length) {
    const emptyItem = document.createElement("li");
    emptyItem.className = "playlist-track__empty";
    emptyItem.textContent = "Noch keine Playlisten angelegt.";
    playlistList.appendChild(emptyItem);
    resetPlaylistDetail();
    return;
  }

  const fallbackId = getFallbackPlaylistId();
  summaries.forEach((item) => {
    const listItem = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "playlist-item";
    button.dataset.id = String(item.id);
    button.dataset.selected = item.id === currentPlaylistId ? "true" : "false";

    const title = document.createElement("span");
    title.className = "playlist-item__title";
    title.textContent = item.name;

    const meta = document.createElement("span");
    meta.className = "playlist-item__meta";
    const metaParts = [`${item.track_count} Tracks`];
    if (fallbackId && item.id === fallbackId) {
      metaParts.push("Autoplay");
    }
    meta.textContent = metaParts.join(" • ");

    button.appendChild(title);
    button.appendChild(meta);
    button.addEventListener("click", () => {
      loadPlaylistDetail(item.id, { scrollIntoView: true });
    });

    listItem.appendChild(button);
    playlistList.appendChild(listItem);
  });
}

function renderPlaylistTracks(tracks) {
  if (!playlistTracksList) {
    return;
  }
  playlistTracksList.innerHTML = "";
  if (!tracks.length) {
    const empty = document.createElement("li");
    empty.className = "playlist-track playlist-track__empty";
    empty.textContent = "Keine Tracks in dieser Playlist.";
    playlistTracksList.appendChild(empty);
    return;
  }

  tracks.forEach((track) => {
    const item = document.createElement("li");
    item.className = "playlist-track";
    item.dataset.trackId = String(track.id);

    const info = document.createElement("div");
    info.className = "playlist-track__info";
    const title = document.createElement("strong");
    title.textContent = `${track.artist} – ${track.title}`;
    const meta = document.createElement("span");
    const parts = [];
    if (Number.isFinite(track.duration_ms)) {
      parts.push(formatDuration(track.duration_ms));
    }
    if (track.genre) {
      parts.push(track.genre);
    }
    if (track.energy_avg != null) {
      parts.push(`Energy ${track.energy_avg.toFixed(2)}`);
    }
    meta.textContent = parts.join(" • ");
    info.appendChild(title);
    if (parts.length) {
      info.appendChild(meta);
    }

    const actions = document.createElement("div");
    actions.className = "playlist-track__actions";
    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "button button--ghost";
    removeButton.textContent = "Entfernen";
    removeButton.addEventListener("click", () => {
      if (currentPlaylistId != null) {
        removeTrackFromPlaylist(currentPlaylistId, track.id);
      }
    });
    actions.appendChild(removeButton);

    item.appendChild(info);
    item.appendChild(actions);
    playlistTracksList.appendChild(item);
  });
}

function renderPlaylistSearchResults(results) {
  if (!playlistTrackResults) {
    return;
  }
  playlistTrackResults.innerHTML = "";
  if (!results.length) {
    const empty = document.createElement("li");
    empty.className = "playlist-track__empty";
    empty.textContent = "Keine Treffer.";
    playlistTrackResults.appendChild(empty);
    return;
  }

  results.forEach((track) => {
    const item = document.createElement("li");
    item.className = "playlist-result";
    const info = document.createElement("div");
    info.className = "playlist-result__info";
    const title = document.createElement("strong");
    title.textContent = `${track.artist} – ${track.title}`;
    const meta = document.createElement("span");
    const parts = [];
    if (Number.isFinite(track.duration_ms)) {
      parts.push(formatDuration(track.duration_ms));
    }
    if (track.genre) {
      parts.push(track.genre);
    }
    if (track.energy_avg != null) {
      parts.push(`Energy ${track.energy_avg.toFixed(2)}`);
    }
    meta.textContent = parts.join(" • ");
    info.appendChild(title);
    if (parts.length) {
      info.appendChild(meta);
    }

    const actions = document.createElement("div");
    actions.className = "playlist-result__actions";
    const addButton = document.createElement("button");
    addButton.type = "button";
    addButton.className = "button button--ghost";
    addButton.textContent = "Hinzufügen";
    addButton.addEventListener("click", () => {
      if (currentPlaylistId != null) {
        addTrackToPlaylist(currentPlaylistId, track.id);
      }
    });
    actions.appendChild(addButton);

    item.appendChild(info);
    item.appendChild(actions);
    playlistTrackResults.appendChild(item);
  });
}

async function refreshPlaylists({ keepSelection = true } = {}) {
  try {
    const response = await apiFetch("/admin/playlists");
    if (!response.ok) {
      throw new Error("Playlisten konnten nicht geladen werden");
    }
    const data = await response.json();
    playlistSummaries = Array.isArray(data) ? data : [];
    if (keepSelection && currentPlaylistId != null) {
      const stillExists = playlistSummaries.some((item) => item.id === currentPlaylistId);
      if (!stillExists) {
        resetPlaylistDetail();
      }
    }
    renderPlaylistList(playlistSummaries);
  } catch (error) {
    showToast(error.message || "Playlisten konnten nicht geladen werden", "error");
  }
}

function applyDetailToUi(detail) {
  currentPlaylistId = detail.id;
  if (playlistEmpty) playlistEmpty.hidden = true;
  if (playlistDetailContent) playlistDetailContent.hidden = false;
  if (playlistDetailName) playlistDetailName.textContent = detail.name;
  if (playlistDetailDescription) {
    playlistDetailDescription.textContent = detail.description || "Keine Beschreibung hinterlegt.";
  }
  if (playlistDetailCount) {
    playlistDetailCount.textContent = `${detail.track_count} ${detail.track_count === 1 ? "Titel" : "Titel"}`;
  }
  if (playlistDetailFallback) {
    playlistDetailFallback.hidden = !detail.is_fallback;
  }
  if (playlistSetFallbackButton) {
    playlistSetFallbackButton.disabled = false;
    playlistSetFallbackButton.textContent = detail.is_fallback
      ? "Autoplay deaktivieren"
      : "Als Autoplay nutzen";
  }
  if (playlistDeleteButton) playlistDeleteButton.disabled = false;
  if (playlistEditName) playlistEditName.value = detail.name;
  if (playlistEditDescription) playlistEditDescription.value = detail.description || "";
  renderPlaylistTracks(detail.tracks || []);
  renderPlaylistList(playlistSummaries);
}

function updateSummariesFromDetail(detail) {
  const summary = {
    id: detail.id,
    name: detail.name,
    description: detail.description,
    track_count: detail.track_count,
    is_fallback: detail.is_fallback,
  };
  const index = playlistSummaries.findIndex((item) => item.id === detail.id);
  if (index >= 0) {
    playlistSummaries[index] = summary;
  } else {
    playlistSummaries.push(summary);
  }
  if (detail.is_fallback) {
    playlistSummaries = playlistSummaries.map((item) => ({
      ...item,
      is_fallback: item.id === detail.id,
    }));
  }
}

async function loadPlaylistDetail(playlistId, { scrollIntoView = false } = {}) {
  try {
    const response = await apiFetch(`/admin/playlists/${playlistId}`);
    if (!response.ok) {
      if (response.status === 404) {
        await refreshPlaylists({ keepSelection: false });
      }
      throw new Error("Playlist konnte nicht geladen werden");
    }
    const detail = await response.json();
    updateSummariesFromDetail(detail);
    applyDetailToUi(detail);
    if (scrollIntoView && playlistDetailContent) {
      playlistDetailContent.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (error) {
    showToast(error.message || "Playlist konnte nicht geladen werden", "error");
  }
}

async function addTrackToPlaylist(playlistId, trackId) {
  try {
    const response = await apiFetch(`/admin/playlists/${playlistId}/tracks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ track_id: trackId }),
    });
    if (!response.ok) {
      throw new Error("Track konnte nicht hinzugefügt werden");
    }
    const detail = await response.json();
    updateSummariesFromDetail(detail);
    applyDetailToUi(detail);
    showToast("Track hinzugefügt", "success");
  } catch (error) {
    showToast(error.message || "Track konnte nicht hinzugefügt werden", "error");
  }
}

async function removeTrackFromPlaylist(playlistId, trackId) {
  try {
    const response = await apiFetch(`/admin/playlists/${playlistId}/tracks/${trackId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error("Track konnte nicht entfernt werden");
    }
    const detail = await response.json();
    updateSummariesFromDetail(detail);
    applyDetailToUi(detail);
    showToast("Track entfernt", "success");
  } catch (error) {
    showToast(error.message || "Track konnte nicht entfernt werden", "error");
  }
}

async function searchPlaylistTracks() {
  if (!playlistTrackSearchInput) {
    return;
  }
  if (currentPlaylistId == null) {
    showToast("Bitte zuerst eine Playlist auswählen", "warning");
    return;
  }
  const query = playlistTrackSearchInput.value.trim();
  if (query.length < 2) {
    showToast("Bitte mindestens zwei Zeichen eingeben", "warning");
    return;
  }
  if (playlistTrackSearchAbort) {
    playlistTrackSearchAbort.abort();
  }
  playlistTrackSearchAbort = new AbortController();
  try {
    const response = await apiFetch(`/tracks/search?query=${encodeURIComponent(query)}&limit=25`, {
      signal: playlistTrackSearchAbort.signal,
    });
    if (!response.ok) {
      throw new Error("Suche fehlgeschlagen");
    }
    const results = await response.json();
    renderPlaylistSearchResults(Array.isArray(results) ? results : []);
  } catch (error) {
    if (error.name === "AbortError") {
      return;
    }
    showToast(error.message || "Suche fehlgeschlagen", "error");
  }
}

async function updatePlaylistMetadata(playlistId, payload) {
  try {
    const response = await apiFetch(`/admin/playlists/${playlistId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error("Playlist konnte nicht aktualisiert werden");
    }
    const detail = await response.json();
    updateSummariesFromDetail(detail);
    applyDetailToUi(detail);
    showToast("Playlist aktualisiert", "success");
  } catch (error) {
    showToast(error.message || "Playlist konnte nicht aktualisiert werden", "error");
  }
}

async function deletePlaylist(playlistId) {
  try {
    const response = await apiFetch(`/admin/playlists/${playlistId}`, { method: "DELETE" });
    if (!response.ok) {
      throw new Error("Playlist konnte nicht gelöscht werden");
    }
    playlistSummaries = playlistSummaries.filter((item) => item.id !== playlistId);
    renderPlaylistList(playlistSummaries);
    resetPlaylistDetail();
    showToast("Playlist gelöscht", "success");
  } catch (error) {
    showToast(error.message || "Playlist konnte nicht gelöscht werden", "error");
  }
}

async function setFallbackPlaylist(playlistId) {
  try {
    const response = await apiFetch("/admin/playlists/fallback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ playlist_id: playlistId }),
    });
    if (!response.ok) {
      throw new Error("Autoplay-Auswahl konnte nicht aktualisiert werden");
    }
    const data = await response.json();
    const activeId = data.playlist_id ?? null;
    playlistSummaries = playlistSummaries.map((item) => ({
      ...item,
      is_fallback: activeId != null && item.id === activeId,
    }));
    renderPlaylistList(playlistSummaries);
    if (currentPlaylistId != null && currentPlaylistId === activeId) {
      if (playlistDetailFallback) playlistDetailFallback.hidden = false;
      if (playlistSetFallbackButton) {
        playlistSetFallbackButton.textContent = "Autoplay deaktivieren";
      }
    } else if (currentPlaylistId != null) {
      if (playlistDetailFallback) playlistDetailFallback.hidden = true;
      if (playlistSetFallbackButton) {
        playlistSetFallbackButton.textContent = "Als Autoplay nutzen";
      }
    }
    showToast("Autoplay-Einstellung gespeichert", "success");
  } catch (error) {
    showToast(error.message || "Autoplay-Einstellung konnte nicht gespeichert werden", "error");
  }
}

async function fetchLightSettings() {
  try {
    const response = await apiFetch("/admin/light/settings");
    if (!response.ok) {
      throw new Error("Lichtsteuerung konnte nicht geladen werden");
    }
    const data = await response.json();
    if (lightHost) lightHost.value = data.target_host;
    if (lightPort) lightPort.value = data.target_port;
    renderLightBindings(data.scene_bindings || [], data.action_labels || {});
    updateToggleInputs({
      fog_enabled: data.fog_enabled,
      superscenes_enabled: data.superscenes_enabled,
      public_enabled: togglePublic ? togglePublic.checked : false,
    });
  } catch (error) {
    showToast(error.message || "Unbekannter Fehler", "error");
  }
}

async function fetchAnalysisSettings() {
  if (!analysisForm) {
    return;
  }
  try {
    const response = await apiFetch("/admin/analysis/settings");
    if (!response.ok) {
      throw new Error("Analyse-Parameter konnten nicht geladen werden");
    }
    const data = await response.json();
    if (analysisKey) analysisKey.value = data.key_weight;
    if (analysisBpm) analysisBpm.value = data.bpm_weight;
    if (analysisEnergy) analysisEnergy.value = data.energy_weight;
    if (analysisGenre) analysisGenre.value = data.genre_weight;
    if (analysisRecency) analysisRecency.value = data.recency_weight;
    if (analysisRequest) analysisRequest.value = data.request_weight;
    if (analysisSpacing) analysisSpacing.value = data.soft_spacing;
  } catch (error) {
    showToast(error.message || "Unbekannter Fehler", "error");
  }
}

async function fetchDiagnostics() {
  try {
    const response = await apiFetch("/admin/logs/diagnostics");
    if (!response.ok) {
      throw new Error("Diagnoseinformationen konnten nicht geladen werden");
    }
    const data = await response.json();
    if (diagnosticsRuntime) diagnosticsRuntime.textContent = data.runtime_log_path;
    if (diagnosticsPersistent) diagnosticsPersistent.textContent = data.persistent_log_path;
    if (diagnosticsCache) diagnosticsCache.textContent = data.cache_path;
    if (diagnosticsConfig) diagnosticsConfig.textContent = data.config_path;
    if (diagnosticsLastError) diagnosticsLastError.textContent = data.last_error || "Keine Einträge";
  } catch (error) {
    showToast(error.message || "Unbekannter Fehler", "error");
  }
}

function renderDiagnosticsResults(results) {
  if (!diagnosticsResults) {
    return;
  }
  diagnosticsResults.innerHTML = "";
  if (!Array.isArray(results) || !results.length) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = "Noch keine Ergebnisse.";
    diagnosticsResults.appendChild(empty);
    return;
  }

  results.forEach((entry) => {
    const item = document.createElement("div");
    item.className = "diagnostics-result";
    item.dataset.success = entry.success ? "true" : "false";

    const title = document.createElement("span");
    title.textContent = entry.name || "Check";

    const detail = document.createElement("span");
    detail.textContent = entry.detail || "";

    item.append(title, detail);
    diagnosticsResults.appendChild(item);
  });
}

async function loadControlCenter() {
  await Promise.all([
    fetchSystemOverview(),
    fetchAccounts(),
    fetchAudioOutput(),
    fetchBluetoothDevices(),
    fetchMixerSettings(),
    fetchLibrarySettings(),
    refreshPlaylists(),
    fetchLightSettings(),
    fetchAnalysisSettings(),
    fetchDiagnostics(),
  ]);
}

if (logoutButton) {
  logoutButton.addEventListener("click", async () => {
    try {
      await apiFetch("/admin/logout", { method: "POST" });
    } finally {
      showToast("Abgemeldet", "info");
      setAuthenticated(false);
    }
  });
}

if (tabButtons.length) {
  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.tabTarget;
      if (target) {
        activateTab(target);
      }
    });
  });
}

if (systemRefreshButton) {
  systemRefreshButton.addEventListener("click", () => {
    fetchSystemOverview();
  });
}

if (systemQueue) {
  systemQueue.addEventListener("click", async (event) => {
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
      let url = "";
      let method = "POST";
      if (action === "delete") {
        url = `/admin/queue/${entryId}`;
        method = "DELETE";
      } else if (action === "promote") {
        url = `/admin/queue/${entryId}/promote`;
      } else if (action === "play") {
        url = `/admin/queue/${entryId}/play`;
      }
      if (!url) {
        return;
      }
      const response = await apiFetch(url, { method });
      if (!response.ok) {
        throw new Error("Aktion fehlgeschlagen");
      }
      showToast("Aktion ausgeführt", "success");
      fetchSystemOverview();
    } catch (error) {
      showToast(error.message || "Unbekannter Fehler", "error");
    }
  });
}

if (systemTogglesForm) {
  systemTogglesForm.addEventListener("change", async (event) => {
    if (togglesUpdating) {
      return;
    }
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || !target.name) {
      return;
    }
    const payload = { [target.name]: target.checked };
    try {
      const response = await apiFetch("/admin/system/toggles", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Schalter konnte nicht gespeichert werden");
      }
      const data = await response.json();
      updateToggleInputs(data);
      showToast("Schalter aktualisiert", "success");
    } catch (error) {
      showToast(error.message || "Unbekannter Fehler", "error");
      fetchSystemOverview();
    }
  });
}

if (audioScanButton) {
  audioScanButton.addEventListener("click", () => {
    fetchAudioOutput(true);
  });
}

if (audioForm && audioDeviceSelect) {
  audioForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const deviceId = audioDeviceSelect.value;
    try {
      const response = await apiFetch("/admin/audio/output", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ device_id: deviceId }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Ausgabegerät konnte nicht gesetzt werden");
      }
      const data = await response.json();
      populateSelect(audioDeviceSelect, data.devices, "identifier", "label", data.active_device_id);
      showToast("Audio-Gerät aktualisiert", "success");
    } catch (error) {
      showToast(error.message || "Unbekannter Fehler", "error");
    }
  });
}

if (bluetoothRefreshButton) {
  bluetoothRefreshButton.addEventListener("click", () => {
    fetchBluetoothDevices(true);
  });
}

if (bluetoothScanButton) {
  bluetoothScanButton.addEventListener("click", async () => {
    const original = bluetoothScanButton.textContent;
    bluetoothScanButton.disabled = true;
    bluetoothScanButton.textContent = "Suche…";
    try {
      await scanBluetoothDevices();
    } finally {
      bluetoothScanButton.disabled = false;
      bluetoothScanButton.textContent = original;
    }
  });
}

if (bluetoothPairForm) {
  bluetoothPairForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const address = (bluetoothAddressInput?.value || "").trim();
    if (!address) {
      showToast("Bitte eine Bluetooth-Adresse eingeben", "error");
      return;
    }
    const payload = {
      address,
      set_default: bluetoothSetDefault ? bluetoothSetDefault.checked : true,
    };
    try {
      const response = await apiFetch("/admin/audio/bluetooth/pair", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Bluetooth-Gerät konnte nicht gekoppelt werden");
      }
      showToast(data.message || "Bluetooth-Gerät verbunden", "success");
      if (bluetoothAddressInput) {
        bluetoothAddressInput.value = "";
      }
      await fetchBluetoothDevices();
      if (payload.set_default && data.audio_device_id) {
        await fetchAudioOutput();
      }
    } catch (error) {
      showToast(error.message || "Bluetooth-Gerät konnte nicht gekoppelt werden", "error");
    }
  });
}

if (bluetoothDeviceList) {
  bluetoothDeviceList.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) {
      return;
    }
    const { address, action } = target.dataset;
    if (!address || !action) {
      return;
    }
    const payload = {
      address,
      connect: action !== "disconnect",
      set_default: action === "connect-default",
    };
    target.disabled = true;
    try {
      const response = await apiFetch("/admin/audio/bluetooth/connect", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Bluetooth-Aktion fehlgeschlagen");
      }
      await fetchBluetoothDevices();
      if (payload.set_default && data.audio_device_id) {
        await fetchAudioOutput();
      }
      const variant = payload.connect ? "success" : "info";
      showToast(data.message || "Bluetooth-Aktion abgeschlossen", variant);
    } catch (error) {
      showToast(error.message || "Bluetooth-Aktion fehlgeschlagen", "error");
    } finally {
      target.disabled = false;
    }
  });
}

if (diagnosticsRunButton) {
  diagnosticsRunButton.addEventListener("click", async () => {
    const original = diagnosticsRunButton.textContent;
    diagnosticsRunButton.disabled = true;
    diagnosticsRunButton.textContent = "System-Check läuft…";
    try {
      const response = await apiFetch("/admin/diagnostics/run", { method: "POST" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "System-Check fehlgeschlagen");
      }
      renderDiagnosticsResults(data.results || []);
      if (Number(data.exit_code) === 0) {
        showToast("System-Check erfolgreich abgeschlossen", "success");
      } else {
        showToast("System-Check meldet Fehler", "error");
      }
    } catch (error) {
      showToast(error.message || "System-Check fehlgeschlagen", "error");
    } finally {
      diagnosticsRunButton.disabled = false;
      diagnosticsRunButton.textContent = original;
    }
  });
}

if (mixerForm) {
  mixerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      crossfade_seconds: parseFloat(mixerCrossfade?.value || "0") || 0,
      volume_curve: mixerVolumeCurve?.value,
      bass_crossover_hz: parseInt(mixerBassHz?.value || "0", 10) || 0,
      bass_curve: mixerBassCurve?.value,
      filter_hp_to_lp: Boolean(mixerFilterHp?.checked),
      filter_lp_to_hp: Boolean(mixerFilterLp?.checked),
      time_stretch_mode: mixerTimeStretch?.value,
    };
    try {
      const response = await apiFetch("/admin/audio/mixer", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Mixer konnte nicht gespeichert werden");
      }
      await response.json();
      showToast("Mixer-Einstellungen gespeichert", "success");
    } catch (error) {
      showToast(error.message || "Unbekannter Fehler", "error");
    }
  });
}

if (libraryMusicSelect) {
  libraryMusicSelect.addEventListener("change", () => {
    if (!libraryMusicPath) {
      return;
    }
    if (libraryMusicSelect.value === "__custom__") {
      libraryMusicPath.focus();
    } else {
      libraryMusicPath.value = libraryMusicSelect.value;
    }
  });
}

if (libraryMusicPath) {
  libraryMusicPath.addEventListener("input", () => {
    syncLibrarySelectWithInput();
  });
}

if (libraryRescanButton) {
  libraryRescanButton.addEventListener("click", async () => {
    const success = await refreshMusicLocations(libraryMusicPath?.value || "");
    if (success) {
      showToast("Speicherorte aktualisiert", "success");
    }
  });
}

if (libraryForm) {
  libraryForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(libraryForm);
    const payload = {};
    const musicPathValue = (formData.get("music_path") || "").toString().trim();
    const databaseDsnValue = (formData.get("database_dsn") || "").toString().trim();
    if (musicPathValue) {
      payload.music_path = musicPathValue;
    }
    if (databaseDsnValue) {
      payload.database_dsn = databaseDsnValue;
    }
    try {
      const response = await apiFetch("/admin/library/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Bibliothek konnte nicht gespeichert werden");
      }
      const data = await response.json();
      if (libraryTrackCount) libraryTrackCount.textContent = data.track_count;
      if (libraryQuarantine) libraryQuarantine.textContent = data.quarantine_path;
      if (libraryMusicPath) libraryMusicPath.value = data.music_path;
      if (libraryDatabaseDsn) libraryDatabaseDsn.value = data.database_dsn;
      await refreshMusicLocations(data.music_path);
      showToast("Bibliothek aktualisiert", "success");
    } catch (error) {
      showToast(error.message || "Unbekannter Fehler", "error");
    }
  });
}

if (playlistRefreshButton) {
  playlistRefreshButton.addEventListener("click", () => {
    refreshPlaylists();
  });
}

if (playlistCreateForm) {
  playlistCreateForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = playlistCreateName?.value.trim();
    const description = playlistCreateDescription?.value.trim();
    if (!name) {
      showToast("Bitte einen Namen für die Playlist angeben", "warning");
      return;
    }
    const payload = { name };
    if (description) {
      payload.description = description;
    }
    try {
      const response = await apiFetch("/admin/playlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Playlist konnte nicht angelegt werden");
      }
      const detail = await response.json();
      updateSummariesFromDetail(detail);
      applyDetailToUi(detail);
      if (playlistCreateName) playlistCreateName.value = "";
      if (playlistCreateDescription) playlistCreateDescription.value = "";
      renderPlaylistList(playlistSummaries);
      showToast("Playlist angelegt", "success");
    } catch (error) {
      showToast(error.message || "Playlist konnte nicht angelegt werden", "error");
    }
  });
}

if (playlistEditForm) {
  playlistEditForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (currentPlaylistId == null) {
      showToast("Bitte zuerst eine Playlist auswählen", "warning");
      return;
    }
    const name = playlistEditName?.value.trim();
    const description = playlistEditDescription?.value.trim() ?? "";
    if (!name) {
      showToast("Der Name darf nicht leer sein", "warning");
      return;
    }
    updatePlaylistMetadata(currentPlaylistId, {
      name,
      description,
    });
  });
}

if (playlistSetFallbackButton) {
  playlistSetFallbackButton.addEventListener("click", () => {
    if (currentPlaylistId == null) {
      showToast("Bitte zuerst eine Playlist auswählen", "warning");
      return;
    }
    const isActive = playlistSummaries.some(
      (item) => item.id === currentPlaylistId && item.is_fallback
    );
    setFallbackPlaylist(isActive ? null : currentPlaylistId);
  });
}

if (playlistDeleteButton) {
  playlistDeleteButton.addEventListener("click", () => {
    if (currentPlaylistId == null) {
      return;
    }
    if (window.confirm("Playlist wirklich löschen?")) {
      deletePlaylist(currentPlaylistId);
    }
  });
}

if (playlistTrackSearchButton) {
  playlistTrackSearchButton.addEventListener("click", () => {
    searchPlaylistTracks();
  });
}

if (playlistTrackSearchInput) {
  playlistTrackSearchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchPlaylistTracks();
    }
  });
}

if (lightForm) {
  lightForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      target_host: lightHost?.value,
      target_port: lightPort?.value ? Number(lightPort.value) : undefined,
      superscenes_enabled: Boolean(lightSuperscenesToggle?.checked),
      fog_enabled: Boolean(lightFogToggle?.checked),
    };
    const sceneBindingsPayload = collectLightBindings();
    if (sceneBindingsPayload) {
      payload.scene_bindings = sceneBindingsPayload;
    }
    try {
      const response = await apiFetch("/admin/light/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "OSC-Konfiguration konnte nicht gespeichert werden");
      }
      const data = await response.json();
      if (lightHost) lightHost.value = data.target_host;
      if (lightPort) lightPort.value = data.target_port;
      renderLightBindings(data.scene_bindings || [], data.action_labels || {});
      updateToggleInputs({
        fog_enabled: data.fog_enabled,
        superscenes_enabled: data.superscenes_enabled,
        public_enabled: togglePublic ? togglePublic.checked : false,
      });
      showToast("OSC-Einstellungen gespeichert", "success");
    } catch (error) {
      showToast(error.message || "Unbekannter Fehler", "error");
    }
  });
}

if (lightResyncButton) {
  lightResyncButton.addEventListener("click", async () => {
    try {
      const response = await apiFetch("/admin/light/resync", { method: "POST" });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Re-Sync fehlgeschlagen");
      }
      showToast("Bar-Reset gesendet", "success");
      fetchSystemOverview();
    } catch (error) {
      showToast(error.message || "Unbekannter Fehler", "error");
    }
  });
}

if (analysisForm) {
  analysisForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      key_weight: parseFloat(analysisKey?.value || "0") || 0,
      bpm_weight: parseFloat(analysisBpm?.value || "0") || 0,
      energy_weight: parseFloat(analysisEnergy?.value || "0") || 0,
      genre_weight: parseFloat(analysisGenre?.value || "0") || 0,
      recency_weight: parseFloat(analysisRecency?.value || "0") || 0,
      request_weight: parseFloat(analysisRequest?.value || "0") || 0,
      soft_spacing: parseInt(analysisSpacing?.value || "0", 10) || 0,
    };
    try {
      const response = await apiFetch("/admin/analysis/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Analyse konnte nicht gespeichert werden");
      }
      await response.json();
      showToast("Analyse-Parameter gespeichert", "success");
    } catch (error) {
      showToast(error.message || "Unbekannter Fehler", "error");
    }
  });
}

if (controlCard) {
  setAuthenticated(true);
}
