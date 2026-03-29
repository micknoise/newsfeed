/**
 * Newsfeed — client-side script
 *
 * Audio is pre-computed server-side using kokoro af_sky:
 *  - docs/audio/summary.ogg        — hourly digest
 *  - docs/audio/items/<id>.ogg     — per-article summary
 *
 * All playback is standard <Audio> — no libraries, no model downloads.
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

  audio.addEventListener("ended",  stopAll);
  audio.addEventListener("error",  () => showToast("Audio not ready yet — try after the next update"));

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
