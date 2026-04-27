// G1 console — browser frontend.
// Talks to the local console server via Server-Sent Events (push) and
// JSON POST (commands). The local server keeps the TCP socket to the Orin.

const KEY_ORDER = "1234567890qwertyuiopasdfghjkl".split("");

const grid           = document.getElementById("grid");
const connEl         = document.getElementById("conn");
const currentEl      = document.getElementById("current");
const latencyEl      = document.getElementById("latency");
const speedReadout   = document.getElementById("speed-readout");
const speedInput     = document.getElementById("speed");
const speedResetBtn  = document.getElementById("speed-reset");
const stopBtn        = document.getElementById("stop-btn");

const tiles      = new Map();   // clip name → { tile, key }
const keyToClip  = new Map();   // keyboard char → clip name
let   currentClip = "idle";
let   connected   = false;
let   hostLabel   = "";

// ---------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------

function renderTiles(clips) {
  grid.innerHTML = "";
  tiles.clear();
  keyToClip.clear();

  clips.forEach((clip, i) => {
    const key = KEY_ORDER[i] || "";
    const tile = document.createElement("button");
    tile.className = "tile";
    tile.type = "button";
    tile.dataset.clip = clip;

    const name = document.createElement("span");
    name.className = "name";
    name.textContent = clip;
    tile.appendChild(name);

    if (key) {
      const k = document.createElement("span");
      k.className = "key";
      k.textContent = key.toUpperCase();
      tile.appendChild(k);
    }

    tile.addEventListener("click", () => triggerClip(clip));
    grid.appendChild(tile);

    tiles.set(clip, { tile, key });
    if (key) keyToClip.set(key, clip);
  });

  applyPlayingState(currentClip);
}

function applyPlayingState(current) {
  for (const [clip, { tile }] of tiles) {
    tile.classList.toggle("playing", clip === current);
  }
  currentEl.textContent = current || "idle";
}

function applyConnState(isConnected, host) {
  connected = isConnected;
  hostLabel = host || hostLabel;
  connEl.classList.toggle("online", isConnected);
  connEl.classList.toggle("offline", !isConnected);
  connEl.textContent = isConnected
    ? `connected · ${hostLabel}`
    : `disconnected · ${hostLabel}`;
  for (const { tile } of tiles.values()) {
    tile.toggleAttribute("disabled", !isConnected);
  }
  stopBtn.toggleAttribute("disabled", !isConnected);
}

function flash(el) {
  el.classList.remove("flash");
  void el.offsetWidth;
  el.classList.add("flash");
}

// ---------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------

async function post(path, body) {
  try {
    const r = await fetch(path, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await r.json().catch(() => ({}));
    if (!data.ok) console.warn(path, "→", data);
    return data;
  } catch (e) {
    console.warn(path, "failed:", e);
    return { ok: false, error: String(e) };
  }
}

function triggerClip(clip) {
  const t = tiles.get(clip);
  if (t) flash(t.tile);
  post("/api/play", { clip });
}

function triggerStop() {
  flash(stopBtn);
  post("/api/stop");
}

let speedDebounce = null;
function setSpeed(v) {
  speedReadout.textContent = `${parseFloat(v).toFixed(2)}×`;
  clearTimeout(speedDebounce);
  speedDebounce = setTimeout(() => {
    post("/api/speed", { value: parseFloat(v) });
  }, 120);
}

// ---------------------------------------------------------------------
// SSE — server → client
// ---------------------------------------------------------------------

function connectEvents() {
  const es = new EventSource("/api/events");

  es.onmessage = (e) => {
    let msg;
    try { msg = JSON.parse(e.data); } catch { return; }

    if (msg.type === "state") {
      applyConnState(!!msg.connected, msg.host || "");
      renderTiles(Array.isArray(msg.clips) ? msg.clips : []);
      currentClip = msg.current || "idle";
      applyPlayingState(currentClip);
      if (typeof msg.latency_ms === "number") {
        latencyEl.textContent = msg.latency_ms.toFixed(0);
      }
    } else if (msg.type === "tick") {
      currentClip = msg.current || "idle";
      applyPlayingState(currentClip);
      if (typeof msg.latency_ms === "number") {
        latencyEl.textContent = msg.latency_ms.toFixed(0);
      }
    }
  };

  es.onerror = () => {
    // EventSource auto-reconnects; reflect that in the UI immediately.
    applyConnState(false, hostLabel || "console server");
    connEl.textContent = "disconnected from console server";
  };
}

// ---------------------------------------------------------------------
// Keyboard
// ---------------------------------------------------------------------

document.addEventListener("keydown", (e) => {
  // Ignore typing in inputs (e.g. range with arrow keys).
  const tag = (e.target && e.target.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA") return;
  if (e.metaKey || e.ctrlKey || e.altKey) return;

  if (e.code === "Space") {
    e.preventDefault();
    if (e.repeat) return;
    triggerStop();
    return;
  }

  if (e.repeat) return;
  const k = e.key.toLowerCase();
  const clip = keyToClip.get(k);
  if (clip) {
    e.preventDefault();
    triggerClip(clip);
  }
});

// ---------------------------------------------------------------------
// Wire up controls
// ---------------------------------------------------------------------

stopBtn.addEventListener("click", triggerStop);
speedInput.addEventListener("input", (e) => setSpeed(e.target.value));
speedResetBtn.addEventListener("click", () => {
  speedInput.value = "1.0";
  setSpeed("1.0");
});

connectEvents();
