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
  const isRec = typeof current === "string" && current.startsWith("recording:");
  for (const [clip, { tile }] of tiles) {
    tile.classList.toggle("playing", !isRec && clip === current);
  }
  if (isRec) {
    currentEl.textContent = `● recording ${current.slice("recording:".length)}`;
  } else {
    currentEl.textContent = current || "idle";
  }
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
      populateClipList(Array.isArray(msg.clips) ? msg.clips : []);
      currentClip = msg.current || "idle";
      applyPlayingState(currentClip);
      syncRecordingFromStatus(msg.current);
      if (typeof msg.latency_ms === "number") {
        latencyEl.textContent = msg.latency_ms.toFixed(0);
      }
    } else if (msg.type === "tick") {
      currentClip = msg.current || "idle";
      applyPlayingState(currentClip);
      syncRecordingFromStatus(msg.current);
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

  if (e.code === "Enter") {
    e.preventDefault();
    if (e.repeat) return;
    fireNext();
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

// =====================================================================
// Timeline / cue list
//
// Auto-fire defaults OFF — cues are a prompter, the operator pulls the
// trigger by hitting the relevant clip tile.
// =====================================================================

const ruler          = document.getElementById("ruler");
const playheadEl     = document.getElementById("playhead");
const markersEl      = document.getElementById("markers");
const clockEl        = document.getElementById("clock");
const durationEl     = document.getElementById("duration");
const showNameEl     = document.getElementById("show-name");
const nextNameEl     = document.getElementById("next-name");
const nextMetaEl     = document.getElementById("next-meta");
const nextInEl       = document.getElementById("next-in");
const playBtn        = document.getElementById("t-play");
const pauseBtn       = document.getElementById("t-pause");
const rewindBtn      = document.getElementById("t-rewind");
const autofireEl     = document.getElementById("autofire");
const autofireLabel  = document.getElementById("autofire-label");
const reloadCuesBtn  = document.getElementById("reload-cues");
const cueWarning     = document.getElementById("cue-warning");

let cues = [];
let cueDuration = 0;
let showName = null;
let playheadS = 0;
let playing = false;
let scrubbing = false;
let lastFrameMs = 0;
const fired = new Set();   // cue indices considered "already fired" this run

// Edit-mode state
let editMode = false;
let selectedCueIdx = -1;
let dirty = false;
let dragMarkerIdx = -1;
let dragMouseStartX = 0;
let dragStarted = false;
const DRAG_THRESHOLD_PX = 3;

function fmtTime(s) {
  if (!isFinite(s)) return "—";
  const sign = s < 0 ? "-" : "";
  const a = Math.abs(s);
  const m = Math.floor(a / 60);
  const r = a - m * 60;
  return `${sign}${m}:${r.toFixed(1).padStart(4, "0")}`;
}

function fireT(cue) {
  return cue.t - (cue.preroll || 0);
}

function reseedFired() {
  // Invariant: after any non-playback playhead change, fired ==
  // { i : cue[i].fireT < playheadS }. Cues passed-over are not re-fired.
  fired.clear();
  cues.forEach((c, i) => {
    if (fireT(c) < playheadS) fired.add(i);
  });
}

async function loadCues() {
  try {
    const r = await fetch("/api/cues");
    const data = await r.json();
    cues = Array.isArray(data.cues) ? data.cues : [];
    cueDuration = Number(data.duration) || 0;
    showName = data.name || null;
    showNameEl.textContent = showName || "—";
    durationEl.textContent = cueDuration > 0 ? fmtTime(cueDuration) : "—";
    if (data.warning) {
      cueWarning.textContent = data.warning;
      cueWarning.hidden = false;
    } else {
      cueWarning.hidden = true;
    }
    if (playheadS > cueDuration) playheadS = cueDuration;
    reseedFired();
    selectedCueIdx = -1;
    populateEditRow();
    renderMarkers();
    renderTimeline();
    setDirty(false);
  } catch (e) {
    cueWarning.textContent = `Failed to load cues: ${e}`;
    cueWarning.hidden = false;
  }
}

function renderMarkers() {
  markersEl.innerHTML = "";
  if (cueDuration <= 0) return;
  cues.forEach((c, i) => {
    const m = document.createElement("div");
    m.className = "marker";
    if (c.action === "stop") m.classList.add("stop-cue");
    if (fired.has(i)) m.classList.add("fired");
    m.style.left = `${(c.t / cueDuration) * 100}%`;
    const lbl = document.createElement("span");
    lbl.className = "ml-label";
    lbl.textContent = c.label || c.clip || c.action;
    m.appendChild(lbl);
    m.dataset.idx = String(i);
    markersEl.appendChild(m);
  });
}

function findFireTarget() {
  // Closest unfired cue to playhead — what Enter would fire.
  let bestI = -1, bestD = Infinity;
  for (let i = 0; i < cues.length; i++) {
    if (fired.has(i)) continue;
    const d = Math.abs(cues[i].t - playheadS);
    if (d < bestD) { bestD = d; bestI = i; }
  }
  return bestI;
}

function renderTimeline() {
  // Playhead
  const ratio = cueDuration > 0 ? playheadS / cueDuration : 0;
  playheadEl.style.left = `${Math.max(0, Math.min(1, ratio)) * 100}%`;
  clockEl.textContent = fmtTime(playheadS);

  const targetIdx = findFireTarget();

  // Marker classes — recompute every frame
  for (let i = 0; i < cues.length; i++) {
    const c = cues[i];
    const m = markersEl.children[i];
    if (!m) continue;
    m.classList.toggle("fired",  fired.has(i));
    m.classList.toggle("past",   c.t < playheadS - 0.05 && !fired.has(i));
    m.classList.toggle("next",   i === targetIdx);
    m.classList.toggle("selected", i === selectedCueIdx && editMode);
  }

  // NEXT readout reflects what Enter will fire (closest unfired).
  if (targetIdx >= 0) {
    const c = cues[targetIdx];
    const dt = c.t - playheadS;
    nextNameEl.textContent = c.label || c.clip || c.action;
    const meta = [];
    if (c.label && c.clip)            meta.push(`clip: ${c.clip}`);
    if (c.action === "stop")          meta.push("STOP");
    if (typeof c.speed === "number")  meta.push(`${c.speed.toFixed(2)}× speed`);
    if (c.preroll)                    meta.push(`preroll ${c.preroll}s`);
    nextMetaEl.textContent = meta.length ? `· ${meta.join(" · ")}` : "";
    if (dt >= 0) {
      nextInEl.textContent = `in ${fmtTime(dt)}`;
      nextInEl.classList.remove("late");
    } else {
      nextInEl.textContent = `${fmtTime(-dt)} late`;
      nextInEl.classList.add("late");
    }
    nextInEl.classList.toggle("imminent", Math.abs(dt) <= 3.0);
  } else {
    nextNameEl.textContent = cueDuration > 0 ? "— all cues fired —" : "—";
    nextMetaEl.textContent = "";
    nextInEl.textContent = "";
    nextInEl.classList.remove("imminent", "late");
  }
}

function fireNext() {
  const i = findFireTarget();
  if (i < 0) return;
  fired.add(i);
  fireCue(cues[i]);
  renderTimeline();
}

function fireCue(c) {
  if (c.action === "stop") {
    triggerStop();
    return;
  }
  if (!c.clip) return;
  if (typeof c.speed === "number") {
    speedInput.value = String(c.speed);
    setSpeed(c.speed);
  }
  triggerClip(c.clip);
}

function tick(now) {
  if (!lastFrameMs) lastFrameMs = now;
  const dt = (now - lastFrameMs) / 1000;
  lastFrameMs = now;

  if (playing && !scrubbing && cueDuration > 0) {
    playheadS += dt;
    if (playheadS >= cueDuration) {
      playheadS = cueDuration;
      playing = false;
      updateTransportUI();
      if (typeof videoPause === "function") videoPause();
    }

    if (autofireEl.checked) {
      cues.forEach((c, i) => {
        if (fired.has(i)) return;
        if (playheadS >= fireT(c)) {
          fired.add(i);
          fireCue(c);
        }
      });
    }
    // Manual mode: cues stay unfired as the playhead rolls past so the
    // operator can fire them late via the Enter hotkey.
  }

  renderTimeline();
  requestAnimationFrame(tick);
}

function setPlayheadFromEvent(e) {
  if (cueDuration <= 0) return;
  const rect = ruler.getBoundingClientRect();
  const x = (e.clientX - rect.left) / rect.width;
  playheadS = Math.max(0, Math.min(1, x)) * cueDuration;
  reseedFired();
  renderTimeline();
}

function updateTransportUI() {
  playBtn.classList.toggle("active", playing);
  pauseBtn.classList.toggle("active", !playing && playheadS > 0);
}

ruler.addEventListener("mousedown", (e) => {
  // In edit mode, mousedown on a marker starts a select/drag, not a scrub.
  if (editMode && e.target.closest(".marker")) return;
  scrubbing = true;
  setPlayheadFromEvent(e);
});
window.addEventListener("mousemove", (e) => {
  if (dragMarkerIdx >= 0) {
    if (!dragStarted && Math.abs(e.clientX - dragMouseStartX) < DRAG_THRESHOLD_PX) return;
    dragStarted = true;
    if (cueDuration <= 0) return;
    const rect = ruler.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const newT = Math.max(0, Math.min(1, x)) * cueDuration;
    cues[dragMarkerIdx].t = newT;
    setDirty(true);
    const m = markersEl.children[dragMarkerIdx];
    if (m) {
      m.style.left = `${(newT / cueDuration) * 100}%`;
      m.classList.add("dragging");
    }
    populateEditRow();
    renderTimeline();
    return;
  }
  if (scrubbing) setPlayheadFromEvent(e);
});
window.addEventListener("mouseup", () => {
  scrubbing = false;
  if (dragMarkerIdx >= 0) {
    const m = markersEl.children[dragMarkerIdx];
    if (m) m.classList.remove("dragging");
  }
  dragMarkerIdx = -1;
  dragStarted = false;
});

playBtn.addEventListener("click", () => {
  if (cueDuration <= 0) return;
  if (playheadS >= cueDuration) {
    playheadS = 0;
    fired.clear();
    renderMarkers();
  }
  playing = true;
  updateTransportUI();
});
pauseBtn.addEventListener("click", () => {
  playing = false;
  updateTransportUI();
});
rewindBtn.addEventListener("click", () => {
  playheadS = 0;
  playing = false;
  fired.clear();
  renderMarkers();
  updateTransportUI();
});
autofireEl.addEventListener("change", () => {
  autofireLabel.classList.toggle("on", autofireEl.checked);
});
reloadCuesBtn.addEventListener("click", () => {
  if (dirty && !confirm("Discard unsaved cue changes?")) return;
  loadCues();
});

// =====================================================================
// Edit mode — drag markers, rename, save
// =====================================================================

const editmodeEl     = document.getElementById("editmode");
const editmodeLabel  = document.getElementById("editmode-label");
const editRowEl      = document.getElementById("edit-row");
const editTimeEl     = document.getElementById("edit-time");
const editClipEl     = document.getElementById("edit-clip");
const editLabelInput = document.getElementById("edit-label");
const editDeselectBtn = document.getElementById("edit-deselect");
const addCueBtn      = document.getElementById("add-cue");
const deleteCueBtn   = document.getElementById("delete-cue");
const saveBtn        = document.getElementById("save-cues");
const clipListEl     = document.getElementById("clip-list");

function populateClipList(clips) {
  clipListEl.innerHTML = "";
  clips.forEach((c) => {
    const o = document.createElement("option");
    o.value = c;
    clipListEl.appendChild(o);
  });
}

function setDirty(d) {
  dirty = !!d;
  saveBtn.classList.toggle("dirty", dirty);
}

function populateEditRow() {
  if (!editMode || selectedCueIdx < 0 || !cues[selectedCueIdx]) {
    editRowEl.hidden = true;
    return;
  }
  const c = cues[selectedCueIdx];
  editRowEl.hidden = false;
  editTimeEl.textContent = fmtTime(c.t);
  editClipEl.value  = c.clip || "";
  editLabelInput.value = c.label || "";
}

function selectCue(i) {
  selectedCueIdx = i;
  populateEditRow();
  renderTimeline();
}

editmodeEl.addEventListener("change", () => {
  editMode = editmodeEl.checked;
  editmodeLabel.classList.toggle("on", editMode);
  document.body.classList.toggle("edit-mode", editMode);
  saveBtn.hidden  = !editMode;
  addCueBtn.hidden = !editMode;
  if (!editMode) {
    selectedCueIdx = -1;
    populateEditRow();
    renderTimeline();
  }
});

function addCueAtPlayhead() {
  if (!editMode) return;
  if (cueDuration <= 0) {
    // Bootstrap an empty file: assume a 60s show until the user adjusts.
    cueDuration = 60;
    durationEl.textContent = fmtTime(cueDuration);
  }
  const t = Math.max(0, Math.min(cueDuration, playheadS));
  cues.push({ t, action: "play" });
  const newIdx = cues.length - 1;
  setDirty(true);
  renderMarkers();
  selectCue(newIdx);
  // Focus the clip field so the user can type immediately.
  setTimeout(() => editClipEl.focus(), 0);
}

function deleteSelectedCue() {
  if (!editMode || selectedCueIdx < 0) return;
  cues.splice(selectedCueIdx, 1);
  // Indices shift — drop fired flags whose owner was removed or shifted.
  fired.clear();
  reseedFired();
  selectedCueIdx = -1;
  setDirty(true);
  populateEditRow();
  renderMarkers();
  renderTimeline();
}

addCueBtn.addEventListener("click", addCueAtPlayhead);
deleteCueBtn.addEventListener("click", deleteSelectedCue);

markersEl.addEventListener("mousedown", (e) => {
  if (!editMode) return;
  const m = e.target.closest(".marker");
  if (!m) return;
  e.stopPropagation();
  e.preventDefault();
  const idx = parseInt(m.dataset.idx, 10);
  if (Number.isNaN(idx)) return;
  dragMarkerIdx = idx;
  dragMouseStartX = e.clientX;
  dragStarted = false;
  selectCue(idx);
});

editClipEl.addEventListener("input", () => {
  if (selectedCueIdx < 0) return;
  const v = editClipEl.value.trim();
  if (v) cues[selectedCueIdx].clip = v;
  else   delete cues[selectedCueIdx].clip;
  setDirty(true);
  // Refresh the marker label (falls back to clip if no label).
  const m = markersEl.children[selectedCueIdx];
  if (m) {
    const lbl = m.querySelector(".ml-label");
    const c = cues[selectedCueIdx];
    if (lbl) lbl.textContent = c.label || c.clip || c.action;
  }
});

editLabelInput.addEventListener("input", () => {
  if (selectedCueIdx < 0) return;
  const v = editLabelInput.value;
  if (v) cues[selectedCueIdx].label = v;
  else   delete cues[selectedCueIdx].label;
  setDirty(true);
  const m = markersEl.children[selectedCueIdx];
  if (m) {
    const lbl = m.querySelector(".ml-label");
    const c = cues[selectedCueIdx];
    if (lbl) lbl.textContent = c.label || c.clip || c.action;
  }
});

editDeselectBtn.addEventListener("click", () => {
  selectedCueIdx = -1;
  populateEditRow();
  renderTimeline();
});

async function saveCues() {
  const payload = {
    name: showName,
    duration: cueDuration,
    cues: cues.map((c) => {
      const out = { t: Number(c.t.toFixed(3)), action: c.action || "play" };
      if (c.clip)   out.clip   = c.clip;
      if (c.label)  out.label  = c.label;
      if (typeof c.speed   === "number") out.speed   = c.speed;
      if (typeof c.preroll === "number") out.preroll = c.preroll;
      return out;
    }).sort((a, b) => a.t - b.t),
  };
  saveBtn.disabled = true;
  try {
    const r = await fetch("/api/cues", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await r.json().catch(() => ({}));
    if (!data.ok) {
      alert(`Save failed: ${data.error || data.msg || r.status}`);
      return;
    }
    setDirty(false);
    // Reload from disk so the in-memory copy matches the canonical sort/format.
    await loadCues();
  } catch (e) {
    alert(`Save failed: ${e}`);
  } finally {
    saveBtn.disabled = false;
  }
}

saveBtn.addEventListener("click", saveCues);

window.addEventListener("beforeunload", (e) => {
  if (dirty) { e.preventDefault(); e.returnValue = ""; }
});

// =====================================================================
// Video previz — slaved to the timeline.
//
// On Play: video seeks to playhead, then plays. On Pause: video pauses.
// On Scrub: video.currentTime = playhead (throttled so dragging the
// playhead doesn't fire seeks every frame). During playback we don't
// continuously sync — both clocks run real-time, drift is shown but
// uncorrected. Scrubbing or restarting Play is the resync.
// =====================================================================

const videoPanel    = document.getElementById("video-panel");
const videoEl       = document.getElementById("previz-video");
const videoFnameEl  = document.getElementById("video-filename");
const videoDriftEl  = document.getElementById("video-drift");
const videoMuteBtn  = document.getElementById("video-mute");
const videoHideBtn  = document.getElementById("video-hide");

let videoAvail = false;
let lastVideoSeek = 0;
const VIDEO_SEEK_THROTTLE_MS = 80;

async function setupVideo() {
  try {
    const r = await fetch("/api/video/info");
    const info = await r.json();
    if (!info.available) return;
    videoFnameEl.textContent = info.filename || "";
    videoEl.src = "/api/video";
    videoPanel.hidden = false;
    videoAvail = true;
    videoEl.addEventListener("loadedmetadata", () => {
      // If the cue file has no duration, adopt the video's so the timeline
      // matches the video length.
      if (cueDuration <= 0 && isFinite(videoEl.duration)) {
        cueDuration = videoEl.duration;
        durationEl.textContent = fmtTime(cueDuration);
        renderTimeline();
      }
    });
  } catch {
    // No video endpoint configured — leave panel hidden.
  }
}

function videoSync(time, hard) {
  if (!videoAvail) return;
  const now = performance.now();
  if (!hard && now - lastVideoSeek < VIDEO_SEEK_THROTTLE_MS) return;
  lastVideoSeek = now;
  try {
    if (videoEl.fastSeek) videoEl.fastSeek(time);
    else                  videoEl.currentTime = time;
  } catch { /* ignore */ }
}

function videoPlay()  { if (videoAvail) videoEl.play().catch(() => {}); }
function videoPause() { if (videoAvail) videoEl.pause(); }

videoMuteBtn.addEventListener("click", () => {
  videoEl.muted = !videoEl.muted;
  videoMuteBtn.textContent = videoEl.muted ? "🔇" : "🔊";
});
videoHideBtn.addEventListener("click", () => {
  const collapsed = videoPanel.classList.toggle("collapsed");
  videoHideBtn.textContent = collapsed ? "Show" : "Hide";
});

// Hook into existing transport. We append listeners; the originals
// continue to handle the timeline-side state.
playBtn.addEventListener("click", () => {
  if (videoAvail) { videoSync(playheadS, true); videoPlay(); }
});
pauseBtn.addEventListener("click", videoPause);
rewindBtn.addEventListener("click", () => {
  videoPause();
  videoSync(0, true);
});

// Hook scrub: setPlayheadFromEvent already sets playheadS. We intercept
// by listening on the ruler and (after the original handler runs) sync
// the video. Mousemove during drag covers the dragging case.
function maybeSeekVideoFromPlayhead() { videoSync(playheadS, false); }
ruler.addEventListener("mousedown", maybeSeekVideoFromPlayhead);
window.addEventListener("mousemove", () => {
  if (scrubbing) maybeSeekVideoFromPlayhead();
});

// Drift display — informational, not corrective.
setInterval(() => {
  if (!videoAvail || !playing) {
    videoDriftEl.textContent = "";
    videoDriftEl.classList.remove("warn");
    return;
  }
  const drift = videoEl.currentTime - playheadS;
  videoDriftEl.textContent = `drift ${drift >= 0 ? "+" : ""}${drift.toFixed(2)}s`;
  videoDriftEl.classList.toggle("warn", Math.abs(drift) > 0.5);
}, 250);

setupVideo();

// =====================================================================
// Record clip
//
// "Record" toggle in the controls row opens a panel with name/interval/
// interp inputs (mirrors record_continuous.py). While recording, the
// panel shows an elapsed timer and Stop/Cancel buttons. The recording
// state is detected from the SSE 'tick' event ("recording:<name>").
// =====================================================================

const recordToggle    = document.getElementById("record-toggle");
const recordPanel     = document.getElementById("record-panel");
const recordForm      = document.getElementById("record-form");
const recordActive    = document.getElementById("record-active");
const recNameEl       = document.getElementById("rec-name");
const recIntervalEl   = document.getElementById("rec-interval");
const recInterpEl     = document.getElementById("rec-interp");
const recStartBtn     = document.getElementById("rec-start");
const recSaveBtn      = document.getElementById("rec-save");
const recExitBtn      = document.getElementById("rec-exit");
const recNameActiveEl = document.getElementById("rec-name-active");
const recElapsedEl    = document.getElementById("rec-elapsed");
const recWarning      = document.getElementById("rec-warning");

let recording = false;   // actively capturing
let unsaved   = false;   // capture stopped, buffer not yet saved
let recordStartMs = 0;
let recCounter = 1;

function nextRecName() {
  return `clip_${String(recCounter++).padStart(3, "0")}`;
}

const recFormFields = [recNameEl, recIntervalEl, recInterpEl];

function setFormFieldsDisabled(disabled) {
  recFormFields.forEach(el => { el.disabled = disabled; });
}

function showRecording(name) {
  recording = true;
  unsaved   = false;
  recordPanel.hidden = false;
  recordActive.hidden = false;
  recordToggle.classList.add("recording");
  recordPanel.classList.add("recording");
  recordToggle.textContent = "● Recording…";
  recNameActiveEl.textContent = name || recNameEl.value || "—";
  recStartBtn.textContent = "Stop";
  recSaveBtn.disabled = true;
  setFormFieldsDisabled(true);
  recordStartMs = performance.now();
}

function showStopped() {
  recording = false;
  unsaved   = true;
  recordActive.hidden = true;
  recordToggle.classList.remove("recording");
  recordPanel.classList.remove("recording");
  recordToggle.textContent = "● Record";
  recStartBtn.textContent = "Start";
  recSaveBtn.disabled = false;
  setFormFieldsDisabled(false);
}

function resetRecording() {
  recording = false;
  unsaved   = false;
  recordActive.hidden = true;
  recordPanel.hidden  = true;
  recordToggle.classList.remove("recording");
  recordPanel.classList.remove("recording");
  recordToggle.textContent = "● Record";
  recStartBtn.textContent = "Start";
  recSaveBtn.disabled = true;
  setFormFieldsDisabled(false);
  recWarn("");
}

function recWarn(msg) {
  recWarning.textContent = msg || "";
  recWarning.hidden = !msg;
}

recordToggle.addEventListener("click", () => {
  if (recording) {
    recordPanel.hidden = false;
    return;
  }
  const opening = recordPanel.hidden;
  recordPanel.hidden = !recordPanel.hidden;
  if (opening) {
    recNameEl.value = nextRecName();
    recSaveBtn.disabled = !unsaved;
  }
  recWarn("");
});

recStartBtn.addEventListener("click", async () => {
  recWarn("");
  if (recording) {
    // Stop capture — keep buffer for save.
    recStartBtn.disabled = true;
    try {
      const r = await fetch("/api/record/stop_capture", { method: "POST" });
      const data = await r.json();
      if (!data.ok) { recWarn(data.msg || "Stop failed."); return; }
      showStopped();
    } catch (e) {
      recWarn(`Network error: ${e}`);
    } finally {
      recStartBtn.disabled = false;
    }
    return;
  }
  // Start a new recording — overwrites any unsaved buffer on the server.
  const name = recNameEl.value.trim();
  if (!name) { recWarn("Name required."); return; }
  const interval = parseFloat(recIntervalEl.value);
  if (!isFinite(interval) || interval <= 0) { recWarn("Invalid interval."); return; }
  const interp = recInterpEl.value;
  recStartBtn.disabled = true;
  try {
    const r = await fetch("/api/record/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, interval, interp }),
    });
    const data = await r.json();
    if (!data.ok) { recWarn(data.msg || data.error || "Start failed."); return; }
    showRecording(name);
  } catch (e) {
    recWarn(`Network error: ${e}`);
  } finally {
    recStartBtn.disabled = false;
  }
});

recSaveBtn.addEventListener("click", async () => {
  recSaveBtn.disabled = true;
  try {
    const r = await fetch("/api/record/save", { method: "POST" });
    const data = await r.json();
    if (!data.ok) {
      recWarn(data.msg || "Save failed.");
      recSaveBtn.disabled = false;
      return;
    }
    unsaved = false;
    recWarn("");
  } catch (e) {
    recWarn(`Network error: ${e}`);
    recSaveBtn.disabled = false;
  }
});

recExitBtn.addEventListener("click", async () => {
  if (unsaved || recording) {
    if (!confirm("Recording not saved. Discard and exit?")) return;
  }
  recExitBtn.disabled = true;
  try {
    await fetch("/api/record/cancel", { method: "POST" });
  } catch (_) {
    // best-effort — close the panel regardless
  } finally {
    recExitBtn.disabled = false;
  }
  resetRecording();
});

// Sync state with what the server says (recovers if the page reloads
// while recording, or if another client started a recording).
function syncRecordingFromStatus(currentStr) {
  const isRec = typeof currentStr === "string" && currentStr.startsWith("recording:");
  if (isRec && !recording) {
    showRecording(currentStr.slice("recording:".length));
  } else if (!isRec && recording) {
    showStopped();
  }
}

// Update elapsed counter ~10Hz when recording.
setInterval(() => {
  if (!recording) return;
  const sec = (performance.now() - recordStartMs) / 1000;
  const m = Math.floor(sec / 60);
  const r = sec - m * 60;
  recElapsedEl.textContent = `${m}:${r.toFixed(1).padStart(4, "0")}`;
}, 100);

loadCues();
requestAnimationFrame(tick);
