/**
 * Newsfeed — client-side script
 *
 * Two independent playback paths:
 *
 *  1. Pre-rendered audio (kokoro af_sky), served as OGG. Disabled by default
 *     (settings.audio_enabled: false), so these controls are usually absent.
 *  2. Browser TTS via the Web Speech API — always available, no server work
 *     and no download. This is what the "Read aloud" button uses.
 *
 * No libraries, no model downloads.
 */

// ── Shared player state ────────────────────────────────────────────────────
let activeAudio = null;
let activeBtn   = null;

const toast = document.getElementById("tts-toast");

function showToast(msg, duration = 2500) {
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toast.classList.remove("show"), duration);
}

function stopAll() {
  if (activeAudio) {
    activeAudio.onended = null;
    activeAudio.onerror = null;
    activeAudio.pause();
    activeAudio.src = "";
    activeAudio = null;
  }
  if (activeBtn) {
    activeBtn.classList.remove("playing");
    activeBtn = null;
  }
}

function playAudio(src, btn) {
  // Toggle off if same button
  if (activeBtn === btn) { stopAll(); return; }
  stopAll();

  const audio = new Audio(src);

  audio.addEventListener("canplaythrough", () => {
    audio.play().catch(() => showToast("Audio unavailable"));
  }, { once: true });

  audio.addEventListener("playing", () => {
    btn.classList.add("playing");
    activeAudio = audio;
    activeBtn   = btn;
  });

  audio.onended = stopAll;
  audio.onerror = () => showToast("Audio not ready yet — try after the next update");

  audio.load();
}

// ── Digest player ──────────────────────────────────────────────────────────
const digestPlayBtn = document.getElementById("play-digest");
if (digestPlayBtn) {
  const pauseIcon = `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;
  const playIcon  = `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;

  digestPlayBtn.addEventListener("click", () => {
    const wasPlaying = activeBtn === digestPlayBtn;
    if (wasPlaying) {
      stopAll();
      digestPlayBtn.innerHTML = playIcon;
    } else {
      playAudio("audio/summary.ogg", digestPlayBtn);
      // Icon updates once audio starts playing
      const orig = digestPlayBtn.addEventListener.bind(digestPlayBtn);
      const onPlay = () => { digestPlayBtn.innerHTML = pauseIcon; };
      const onStop = () => { digestPlayBtn.innerHTML = playIcon; };
      document.addEventListener("playing",  onPlay,  { once: true });
      document.addEventListener("ended",    onStop,  { once: true });
    }
  });
}

// ── Per-article play buttons ───────────────────────────────────────────────
document.querySelectorAll(".btn-play-item").forEach(btn => {
  btn.addEventListener("click", () => {
    const src = btn.dataset.audio;
    if (!src) return;

    // Swap icon
    const playIcon  = `<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
    const pauseIcon = `<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;

    if (activeBtn === btn) {
      stopAll();
      btn.innerHTML = playIcon;
      return;
    }

    // Reset any previously active item button icon
    if (activeBtn && activeBtn !== digestPlayBtn) {
      activeBtn.innerHTML = playIcon;
    }

    playAudio(src, btn);
    btn.innerHTML = pauseIcon;

    // Restore icon on end/error
    const restore = () => { btn.innerHTML = playIcon; };
    if (activeAudio) {
      activeAudio.addEventListener("ended", restore, { once: true });
      activeAudio.addEventListener("error", restore, { once: true });
    }
  });
});

// ── Browser TTS (Web Speech API) ───────────────────────────────────────────
// Uses whatever speech engine the device already has — no download, works
// offline, and picks up the user's own installed voices.

const synth = window.speechSynthesis;
const ttsSupported = !!synth && typeof window.SpeechSynthesisUtterance === "function";

const tts = { btn: null, chunks: [], idx: 0, active: false, keepAlive: null };

/** Prefer a voice matching the page language; prefer offline voices. */
function pickVoice() {
  const voices = synth.getVoices();
  if (!voices.length) return null;                       // not loaded yet — use engine default
  const want = (document.documentElement.lang || "en").slice(0, 2).toLowerCase();
  const byLang = voices.filter(v => (v.lang || "").slice(0, 2).toLowerCase() === want);
  const pool = byLang.length ? byLang : voices;
  return pool.find(v => v.localService) || pool[0];
}

/**
 * Split into utterance-sized pieces at sentence boundaries.
 * Chrome truncates long utterances (~15s), so short chunks are not just
 * tidier — they're what makes a multi-paragraph digest play to the end.
 */
function splitForSpeech(text, max = 200) {
  const out = [];
  const sentences = text.replace(/\s+/g, " ").trim().match(/[^.!?]+[.!?]*\s*/g) || [];
  let buf = "";
  for (const s of sentences) {
    if (buf && (buf + s).length > max) { out.push(buf.trim()); buf = ""; }
    if (s.length > max) {
      let rest = s.trim();
      while (rest.length > max) {
        let cut = rest.lastIndexOf(" ", max);
        if (cut <= 0) cut = max;
        out.push(rest.slice(0, cut).trim());
        rest = rest.slice(cut).trim();
      }
      buf = rest;
    } else {
      // Sentences from the regex keep their trailing space, but a remainder
      // handed over from the hard-split path above has been trimmed — so make
      // sure we never fuse two sentences into one word.
      buf = buf && !/\s$/.test(buf) ? buf + " " + s : buf + s;
    }
  }
  if (buf.trim()) out.push(buf.trim());
  return out.filter(Boolean);
}

/** Button label lives in a span so we can swap it without losing the icon. */
function ttsLabel(btn) {
  let el = btn.querySelector(".btn-tts-label");
  if (!el) {
    el = document.createElement("span");
    el.className = "btn-tts-label";
    for (const n of [...btn.childNodes]) {
      if (n.nodeType === Node.TEXT_NODE && n.textContent.trim()) {
        el.textContent = n.textContent.trim();
        n.remove();
      }
    }
    if (!el.textContent) el.textContent = "Read aloud";
    btn.appendChild(el);
  }
  return el;
}

function ttsStop() {
  tts.active = false;
  clearInterval(tts.keepAlive);
  tts.keepAlive = null;
  try { synth.cancel(); } catch (_) {}
  if (tts.btn) {
    tts.btn.classList.remove("speaking");
    tts.btn.setAttribute("aria-pressed", "false");
    ttsLabel(tts.btn).textContent = tts.btn.dataset.labelIdle || "Read aloud";
    tts.btn = null;
  }
  tts.chunks = [];
  tts.idx = 0;
}

function speakNext() {
  if (!tts.active) return;
  if (tts.idx >= tts.chunks.length) { ttsStop(); return; }

  const u = new SpeechSynthesisUtterance(tts.chunks[tts.idx]);
  const v = pickVoice();
  if (v) { u.voice = v; u.lang = v.lang; }
  u.rate = 1.0;
  u.pitch = 1.0;

  u.onend = () => { if (tts.active) { tts.idx++; speakNext(); } };
  u.onerror = (e) => {
    // Cancelling mid-utterance fires an error; that's us, not a fault.
    if (e.error === "interrupted" || e.error === "canceled") return;
    showToast("Speech failed — " + (e.error || "unknown"));
    ttsStop();
  };

  synth.speak(u);
}

function ttsStart(btn, text) {
  stopAll();                       // don't talk over the OGG player
  tts.btn = btn;
  tts.chunks = splitForSpeech(text);
  tts.idx = 0;
  tts.active = true;

  btn.dataset.labelIdle = btn.dataset.labelIdle || ttsLabel(btn).textContent;
  btn.classList.add("speaking");
  btn.setAttribute("aria-pressed", "true");
  ttsLabel(btn).textContent = "Stop";

  // Chrome can drop into a paused state on long reads; nudge it back.
  tts.keepAlive = setInterval(() => {
    if (tts.active && synth.paused) synth.resume();
  }, 5000);

  speakNext();
}

document.querySelectorAll(".btn-tts").forEach(btn => {
  ttsLabel(btn);                                        // normalise markup up front
  btn.dataset.labelIdle = ttsLabel(btn).textContent;
  btn.setAttribute("aria-pressed", "false");

  if (!ttsSupported) {
    btn.disabled = true;
    btn.title = "Your browser doesn't support speech synthesis";
    return;
  }

  btn.addEventListener("click", () => {
    if (tts.active && tts.btn === btn) { ttsStop(); return; }   // toggle off
    if (tts.active) ttsStop();                                  // switch source

    const target = document.getElementById(btn.dataset.target || "");
    const text = (target?.innerText || "").trim();
    if (!text) { showToast("Nothing to read yet"); return; }

    ttsStart(btn, text);
  });
});

// Voices load asynchronously in most browsers; nothing to do but be ready.
if (ttsSupported && typeof synth.onvoiceschanged !== "undefined") {
  synth.addEventListener("voiceschanged", () => {}, { once: true });
}

// Speech outlives navigation in some browsers — make sure it doesn't.
window.addEventListener("beforeunload", () => { if (tts.active) ttsStop(); });
window.addEventListener("pagehide",     () => { if (tts.active) ttsStop(); });
