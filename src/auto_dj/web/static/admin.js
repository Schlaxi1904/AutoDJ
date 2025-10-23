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
const libraryMusicSelect = document.getElementById("library-music-select");
const libraryMusicPath = document.getElementById("library-music-path");
const libraryDatabaseDsn = document.getElementById("library-database-dsn");
const libraryRescanButton = document.getElementById("library-rescan");

const lightForm = document.getElementById("light-form");
const lightHost = document.getElementById("light-host");
const lightPort = document.getElementById("light-port");
const lightResyncButton = document.getElementById("light-resync");

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

let systemInterval = null;
let togglesUpdating = false;

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

async function fetchLightSettings() {
  try {
    const response = await apiFetch("/admin/light/settings");
    if (!response.ok) {
      throw new Error("Lichtsteuerung konnte nicht geladen werden");
    }
    const data = await response.json();
    if (lightHost) lightHost.value = data.target_host;
    if (lightPort) lightPort.value = data.target_port;
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

async function loadControlCenter() {
  await Promise.all([
    fetchSystemOverview(),
    fetchAccounts(),
    fetchAudioOutput(),
    fetchMixerSettings(),
    fetchLibrarySettings(),
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

if (lightForm) {
  lightForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      target_host: lightHost?.value,
      target_port: lightPort?.value ? Number(lightPort.value) : undefined,
      superscenes_enabled: Boolean(lightSuperscenesToggle?.checked),
      fog_enabled: Boolean(lightFogToggle?.checked),
    };
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
