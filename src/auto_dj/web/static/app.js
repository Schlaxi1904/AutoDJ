const API = {
  queue: "/queue",
  nowPlaying: "/now-playing",
  search: "/tracks/search",
};

const guestSessionKey = "auto-dj-guest-session";
let guestSession = window.localStorage.getItem(guestSessionKey);
if (!guestSession) {
  guestSession = crypto.randomUUID();
  window.localStorage.setItem(guestSessionKey, guestSession);
}

const toastEl = document.querySelector("#toast");
const toastMessageEl = document.querySelector("#toast-message");

const queueListEl = document.querySelector("#queue-list");
const queueRemainingEl = document.querySelector("#queue-remaining");
const nowPlayingBpmEl = document.querySelector("#now-playing-bpm");
const nowPlayingContainer = document.querySelector(".now-playing");
const searchForm = document.querySelector("#request-form");
const searchInput = document.querySelector("#request-query");
const searchStatusEl = document.querySelector("#search-status");
const searchResultsEl = document.querySelector("#search-results");

let searchDebounceHandle;

function showToast(message, timeout = 2600) {
  toastMessageEl.textContent = message;
  toastEl.hidden = false;
  if (timeout) {
    setTimeout(() => {
      toastEl.hidden = true;
    }, timeout);
  }
}

function msToTimeString(duration) {
  const minutes = Math.floor(duration / 60000);
  const seconds = Math.floor((duration % 60000) / 1000)
    .toString()
    .padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function renderQueue(status) {
  queueRemainingEl.textContent = status.remaining_slots;
  queueListEl.innerHTML = "";

  if (!status.entries.length) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "Noch keine Titel in der Queue.";
    queueListEl.appendChild(empty);
    return;
  }

  status.entries.forEach((entry) => {
    const item = document.createElement("li");
    item.className = "queue-item";
    item.dataset.entryId = entry.id;

    item.innerHTML = `
      <div>
        <span class="queue-item__title">${entry.track.title}</span>
        <span class="queue-item__artist">${entry.track.artist}</span>
      </div>
      <div class="queue-item__meta">
        <span class="queue-item__badge queue-item__badge--${entry.source}">${entry.source}</span>
        <span class="queue-item__time">${msToTimeString(entry.track.duration_ms)}</span>
      </div>
    `;

    queueListEl.appendChild(item);
  });
}

function renderNowPlaying(entry) {
  const existingCard = nowPlayingContainer.querySelector(".track-card");
  const emptyState = nowPlayingContainer.querySelector(".empty-state");

  if (!entry) {
    if (existingCard) existingCard.remove();
    if (!emptyState) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.innerHTML = "<p>Noch kein Track aktiv. Sobald der Mix startet, erscheint er hier.</p>";
      nowPlayingContainer.appendChild(empty);
    }
    nowPlayingBpmEl.textContent = "-- BPM";
    return;
  }

  if (emptyState) emptyState.remove();

  const markup = `
    <article class="track-card" data-track-id="${entry.track.id}">
      <div class="track-card__art" aria-hidden="true">
        <div class="placeholder-art">🎵</div>
      </div>
      <div class="track-card__meta">
        <h3 class="track-card__title">${entry.track.title}</h3>
        <p class="track-card__artist">${entry.track.artist}</p>
        <dl class="track-card__stats">
          <div>
            <dt>Genre</dt>
            <dd>${entry.track.genre}</dd>
          </div>
          <div>
            <dt>Key</dt>
            <dd>${entry.track.key_camelot}</dd>
          </div>
          <div>
            <dt>Energie</dt>
            <dd>${Math.round(entry.track.energy_avg * 100)}%</dd>
          </div>
        </dl>
      </div>
    </article>
  `;

  if (existingCard) {
    existingCard.replaceWith(document.createRange().createContextualFragment(markup));
  } else {
    nowPlayingContainer.appendChild(document.createRange().createContextualFragment(markup));
  }

  nowPlayingBpmEl.textContent = entry.track.bpm ? `${Math.round(entry.track.bpm)} BPM` : "-- BPM";
}

async function updateQueue() {
  try {
    const response = await fetch(API.queue);
    if (!response.ok) throw new Error("Queue konnte nicht geladen werden");
    const data = await response.json();
    renderQueue(data);
  } catch (error) {
    console.error(error);
    showToast("Verbindung zur Queue fehlgeschlagen");
  }
}

async function updateNowPlaying() {
  try {
    const response = await fetch(API.nowPlaying);
    if (!response.ok) throw new Error("Now Playing konnte nicht geladen werden");
    const data = await response.json();
    renderNowPlaying(data);
  } catch (error) {
    console.error(error);
  }
}

function renderSearchResults(results) {
  searchResultsEl.innerHTML = "";

  if (!results.length) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "Keine Treffer – probier einen anderen Begriff.";
    searchResultsEl.appendChild(empty);
    return;
  }

  results.forEach((track) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <div class="search-result__header">
        <h3 class="search-result__title">${track.title}</h3>
        <span class="search-result__meta">${msToTimeString(track.duration_ms)}</span>
      </div>
      <div class="search-result__meta">
        <span>${track.artist}</span>
        <span>${track.genre}</span>
        <span>Energie ${Math.round(track.energy_avg * 100)}%</span>
      </div>
      <div class="search-result__actions">
        <button class="button" data-track-id="${track.id}">In Queue legen</button>
      </div>
    `;

    const button = item.querySelector("button");
    button.addEventListener("click", () => submitRequest(track.id, button));

    searchResultsEl.appendChild(item);
  });
}

async function submitRequest(trackId, button) {
  const payload = {
    track_id: trackId,
    guest_session: guestSession,
  };

  button.disabled = true;

  try {
    const response = await fetch(API.queue, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || "Track konnte nicht eingereiht werden");
    }

    showToast("Wunsch erfolgreich eingereiht! ✨");
    await updateQueue();
  } catch (error) {
    console.error(error);
    showToast(error.message || "Fehler beim Einreihen");
  } finally {
    button.disabled = false;
  }
}

async function performSearch(query) {
  if (!query || query.length < 2) {
    searchStatusEl.textContent = "Bitte mindestens zwei Zeichen eingeben.";
    searchResultsEl.innerHTML = "";
    return;
  }

  searchStatusEl.textContent = "Suche läuft …";

  try {
    const params = new URLSearchParams({ query });
    const response = await fetch(`${API.search}?${params.toString()}`);
    if (!response.ok) throw new Error("Suche fehlgeschlagen");
    const data = await response.json();
    renderSearchResults(data);
    searchStatusEl.textContent = `${data.length} Treffer gefunden.`;
  } catch (error) {
    console.error(error);
    searchStatusEl.textContent = "Verbindung zur Suche fehlgeschlagen.";
  }
}

searchInput.addEventListener("input", (event) => {
  const value = event.target.value.trim();
  clearTimeout(searchDebounceHandle);
  searchDebounceHandle = setTimeout(() => performSearch(value), 250);
});

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  performSearch(searchInput.value.trim());
});

updateQueue();
updateNowPlaying();
setInterval(updateQueue, 7000);
setInterval(updateNowPlaying, 5000);
