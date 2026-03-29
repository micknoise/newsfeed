/**
 * Newsfeed — client-side script
 *
 * Two TTS modes:
 *  1. Pre-computed OGG (digest): kokoro af_sky voice, generated server-side each hour.
 *  2. Ad-hoc reading (cards/articles): Web Speech API — built-in, zero download,
 *     uses the best available system voice (macOS: neural Ava/Siri, etc.)
 */

// ── 1. Pre-computed OGG player ─────────────────────────────────────────────
const digestAudio = document.getElementById("digest-audio");
const playBtn     = document.getElementById("play-digest");

if (digestAudio && playBtn) {
  const pauseIcon = `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;
  const playIcon  = `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;

  playBtn.addEventListener("click", () => {
    if (digestAudio.paused) {
      digestAudio.play();
      playBtn.innerHTML = pauseIcon;
      playBtn.classList.add("playing");
    } else {
      digestAudio.pause();
      playBtn.innerHTML = playIcon;
      playBtn.classList.remove("playing");
    }
  });

  digestAudio.addEventListener("ended", () => {
    playBtn.innerHTML = playIcon;
    playBtn.classList.remove("playing");
  });
}

// ── 2. Ad-hoc TTS via Web Speech API ──────────────────────────────────────
const toast = document.getElementById("tts-toast");

function showToast(msg, duration = 2500) {
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toast.classList.remove("show"), duration);
}

const synth = window.speechSynthesis;
let activeBtn = null;

function stopSpeaking() {
  synth.cancel();
  if (activeBtn) {
    activeBtn.classList.remove("active");
    activeBtn = null;
  }
}

function speakText(text, btn) {
  if (!text || !text.trim()) return;

  // Toggle off if same button clicked again
  if (activeBtn === btn) { stopSpeaking(); return; }
  stopSpeaking();

  if (!synth) { showToast("Speech not supported in this browser"); return; }

  const utterance = new SpeechSynthesisUtterance(text.trim());
  utterance.rate  = 1.05;

  // Prefer a high-quality English voice if available (macOS neural voices)
  const voices = synth.getVoices();
  const preferred = voices.find(v =>
    v.lang.startsWith("en") && (v.name.includes("Ava") || v.name.includes("Samantha") || v.name.includes("Karen"))
  ) || voices.find(v => v.lang.startsWith("en"));
  if (preferred) utterance.voice = preferred;

  utterance.onend = () => {
    btn.classList.remove("active");
    if (activeBtn === btn) activeBtn = null;
  };
  utterance.onerror = () => {
    btn.classList.remove("active");
    if (activeBtn === btn) activeBtn = null;
  };

  activeBtn = btn;
  btn.classList.add("active");
  synth.speak(utterance);
}

// Voices load asynchronously in some browsers
if (synth && synth.onvoiceschanged !== undefined) {
  synth.onvoiceschanged = () => {};
}

// ── Wire up all .btn-tts buttons ───────────────────────────────────────────
function wireButtons() {
  if (!synth) return; // silently hide if browser has no speech support

  document.querySelectorAll(".btn-tts").forEach(btn => {
    btn.addEventListener("click", () => {
      let text;
      const targetId = btn.dataset.target;
      if (targetId) {
        const el = document.getElementById(targetId);
        text = el ? el.innerText : "";
      } else {
        text = btn.dataset.text || "";
      }
      speakText(text, btn);
    });
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", wireButtons);
} else {
  wireButtons();
}
