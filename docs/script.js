/**
 * Newsfeed — client-side script
 *
 * Two TTS modes:
 *  1. Pre-computed OGG (digest): kokoro af_sky voice, generated server-side each hour.
 *  2. Ad-hoc reading (cards/articles): hits the local Kokoro TTS server on
 *     localhost:8765 for consistent af_sky quality. Falls back to Web Speech API
 *     if the server isn't running (e.g. browsing from another machine).
 */

const TTS_SERVER = "http://localhost:8765";
const TTS_VOICE  = "af_sky";

// ── 1. Pre-computed OGG player ─────────────────────────────────────────────
const digestAudio = document.getElementById("digest-audio");
const playBtn     = document.getElementById("play-digest");

if (digestAudio && playBtn) {
  const pauseIcon = `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;
  const playIcon  = `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;

  playBtn.addEventListener("click", () => {
    if (digestAudio.paused) {
      digestAudio.play().then(() => {
        playBtn.innerHTML = pauseIcon;
        playBtn.classList.add("playing");
      }).catch(() => {
        showToast("Audio not available yet — check back after the next update");
      });
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

// ── Toast ──────────────────────────────────────────────────────────────────
const toast = document.getElementById("tts-toast");

function showToast(msg, duration = 2500) {
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toast.classList.remove("show"), duration);
}

// ── 2. Ad-hoc TTS ─────────────────────────────────────────────────────────
let serverAvailable = null; // null = unchecked, true/false = result
let activeAudio = null;
let activeBtn   = null;

async function checkServer() {
  if (serverAvailable !== null) return serverAvailable;
  try {
    const r = await fetch(`${TTS_SERVER}/ping`, { signal: AbortSignal.timeout(1000) });
    serverAvailable = r.ok;
  } catch {
    serverAvailable = false;
  }
  return serverAvailable;
}

function stopSpeaking() {
  if (activeAudio) {
    if (activeAudio instanceof Audio) {
      activeAudio.pause();
      activeAudio.src = "";
    } else {
      // SpeechSynthesisUtterance fallback
      window.speechSynthesis?.cancel();
    }
    activeAudio = null;
  }
  if (activeBtn) {
    activeBtn.classList.remove("active");
    activeBtn = null;
  }
}

async function speakWithServer(text, btn) {
  const url = `${TTS_SERVER}/tts?text=${encodeURIComponent(text)}&voice=${TTS_VOICE}`;
  showToast("Generating audio…", 15000);

  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`TTS server error: ${resp.status}`);

  const blob     = await resp.blob();
  const audioUrl = URL.createObjectURL(blob);
  const audio    = new Audio(audioUrl);

  audio.onended = () => {
    URL.revokeObjectURL(audioUrl);
    btn.classList.remove("active");
    if (activeBtn === btn) activeBtn = null;
  };
  audio.onerror = () => {
    URL.revokeObjectURL(audioUrl);
    btn.classList.remove("active");
    if (activeBtn === btn) activeBtn = null;
  };

  activeAudio = audio;
  await audio.play();
  showToast("Speaking…", (audio.duration || 10) * 1000);
}

function speakWithWebSpeech(text, btn) {
  const synth = window.speechSynthesis;
  if (!synth) { showToast("Speech not supported"); return; }

  const utterance = new SpeechSynthesisUtterance(text.trim());
  utterance.rate  = 1.05;

  const voices   = synth.getVoices();
  const preferred = voices.find(v =>
    v.lang.startsWith("en") && (v.name.includes("Ava") || v.name.includes("Samantha"))
  ) || voices.find(v => v.lang.startsWith("en-GB") || v.lang.startsWith("en-US"));
  if (preferred) utterance.voice = preferred;

  utterance.onend = utterance.onerror = () => {
    btn.classList.remove("active");
    if (activeBtn === btn) activeBtn = null;
  };

  activeAudio = utterance;
  synth.speak(utterance);
}

async function speakText(text, btn) {
  const t = text?.trim();
  if (!t) return;

  if (activeBtn === btn) { stopSpeaking(); return; }
  stopSpeaking();

  btn.classList.add("active");
  activeBtn = btn;

  try {
    const hasServer = await checkServer();
    if (hasServer) {
      await speakWithServer(t, btn);
    } else {
      showToast("TTS server offline — using browser voice");
      speakWithWebSpeech(t, btn);
    }
  } catch (err) {
    console.error("[TTS]", err);
    // Server call failed mid-flight — retry once with Web Speech
    serverAvailable = false;
    showToast("Falling back to browser voice");
    speakWithWebSpeech(t, btn);
  }
}

// ── Wire up .btn-tts buttons ───────────────────────────────────────────────
function wireButtons() {
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
