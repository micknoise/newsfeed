/**
 * Newsfeed — client-side script
 *
 * Two TTS modes:
 *  1. Pre-computed OGG: the #digest-audio <audio> element + #play-digest button
 *  2. Browser TTS: kokoro-js via esm.sh (downloads ~80 MB ONNX model on first use,
 *     cached by the browser). Falls back to Web Speech API if kokoro-js fails.
 */

// ── 1. Pre-computed audio player ──────────────────────────────────────────
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

// ── 2. Browser TTS ────────────────────────────────────────────────────────
const KOKORO_CDN  = "https://esm.sh/kokoro-js@1.2.1";
const TTS_MODEL   = "onnx-community/Kokoro-82M-ONNX";
const TTS_VOICE   = "af_sky";

let kokoroTTS    = null;   // KokoroTTS instance
let useWebSpeech = false;  // fallback flag
let ttsLoading   = false;
let activeSource = null;   // AudioBufferSourceNode or SpeechSynthesisUtterance
let activeBtn    = null;

const toast = document.getElementById("tts-toast");

function showToast(msg, duration = 3000) {
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toast.classList.remove("show"), duration);
}

async function loadTTS() {
  if (kokoroTTS || useWebSpeech) return true;
  if (ttsLoading) return false;
  ttsLoading = true;

  showToast("Loading speech model… (first use only)", 30000);
  try {
    const { KokoroTTS } = await import(KOKORO_CDN);
    kokoroTTS = await KokoroTTS.from_pretrained(TTS_MODEL, {
      dtype: { model: "q8", embeddings: "fp32" },
    });
    showToast("Speech model ready");
    return true;
  } catch (err) {
    console.warn("[TTS] kokoro-js unavailable, falling back to Web Speech API:", err);
    if ("speechSynthesis" in window) {
      useWebSpeech = true;
      showToast("Using browser voice (kokoro unavailable)");
      return true;
    }
    showToast("TTS unavailable");
    return false;
  } finally {
    ttsLoading = false;
  }
}

function stopSpeaking() {
  if (useWebSpeech) {
    window.speechSynthesis.cancel();
  } else if (activeSource) {
    try { activeSource.stop(); } catch (_) {}
    activeSource = null;
  }
  if (activeBtn) {
    activeBtn.classList.remove("active");
    activeBtn = null;
  }
}

async function speakWithKokoro(text, btn) {
  const result = await kokoroTTS.generate(text.trim(), { voice: TTS_VOICE });
  // result is a RawAudio-like object: { audio: Float32Array, sampling_rate: number }
  const audio         = result.audio;
  const sampling_rate = result.sampling_rate;

  const ctx    = new (window.AudioContext || window.webkitAudioContext)();
  const buffer = ctx.createBuffer(1, audio.length, sampling_rate);
  buffer.getChannelData(0).set(audio);

  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.connect(ctx.destination);
  source.onended = () => {
    btn.classList.remove("active");
    if (activeBtn === btn) activeBtn = null;
  };
  source.start();
  activeSource = source;
  showToast("Speaking…", (audio.length / sampling_rate) * 1000 + 500);
}

function speakWithWebSpeech(text, btn) {
  const utterance = new SpeechSynthesisUtterance(text.trim());
  utterance.rate  = 1.0;
  utterance.onend = () => {
    btn.classList.remove("active");
    if (activeBtn === btn) activeBtn = null;
  };
  window.speechSynthesis.speak(utterance);
  activeSource = utterance;
  showToast("Speaking…", 30000);
}

async function speakText(text, btn) {
  if (!text || !text.trim()) return;

  if (activeBtn === btn) { stopSpeaking(); return; }
  stopSpeaking();

  const ready = await loadTTS();
  if (!ready) return;

  btn.classList.add("active");
  activeBtn = btn;

  try {
    if (useWebSpeech) {
      speakWithWebSpeech(text, btn);
    } else {
      showToast("Generating audio…", 30000);
      await speakWithKokoro(text, btn);
    }
  } catch (err) {
    console.error("[TTS] Synthesis error:", err);
    showToast("TTS error — see console");
    btn.classList.remove("active");
    activeBtn = null;
  }
}

// ── Wire up all .btn-tts buttons ──────────────────────────────────────────
function wireButtons() {
  document.querySelectorAll(".btn-tts").forEach(btn => {
    btn.addEventListener("click", async () => {
      let text;
      const targetId = btn.dataset.target;
      if (targetId) {
        const el = document.getElementById(targetId);
        text = el ? el.innerText : "";
      } else {
        text = btn.dataset.text || "";
      }
      await speakText(text, btn);
    });
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", wireButtons);
} else {
  wireButtons();
}
