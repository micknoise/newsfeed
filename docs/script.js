/**
 * Newsfeed — client-side script
 *
 * Two TTS modes:
 *  1. Pre-computed OGG: the #digest-audio <audio> element + #play-digest button
 *  2. Browser TTS: @huggingface/transformers Kokoro model (downloaded on first use,
 *     then cached by the browser). Triggered by any .btn-tts button.
 *
 * The transformers.js model (~80 MB quantised) is loaded lazily — only when the
 * user first clicks a "Read aloud" button.
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

// ── 2. Browser TTS via @huggingface/transformers ───────────────────────────
const TRANSFORMERS_CDN =
  "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3/dist/transformers.min.js";
const TTS_MODEL = "onnx-community/Kokoro-82M-v1.0";
const TTS_VOICE = "af_sky";

let ttsModule   = null;   // the imported transformers module
let ttsPipeline = null;   // the loaded TTS pipeline
let ttsLoading  = false;
let activeSource = null;  // currently speaking AudioBufferSourceNode
let activeBtn    = null;  // currently active .btn-tts button

const toast = document.getElementById("tts-toast");

function showToast(msg, duration = 3000) {
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toast.classList.remove("show"), duration);
}

async function loadTTS() {
  if (ttsPipeline) return ttsPipeline;
  if (ttsLoading)  return null;
  ttsLoading = true;

  showToast("Loading speech model… (first use only)", 20000);
  try {
    ttsModule = await import(TRANSFORMERS_CDN);
    // Allow remote model downloads and use the browser cache
    ttsModule.env.allowRemoteModels = true;
    ttsModule.env.useBrowserCache   = true;

    ttsPipeline = await ttsModule.pipeline("text-to-speech", TTS_MODEL, {
      dtype: { model: "q8", embeddings: "fp32" },
    });
    showToast("Speech model ready");
    return ttsPipeline;
  } catch (err) {
    console.error("[TTS] Failed to load model:", err);
    showToast("Speech model failed to load — check console");
    return null;
  } finally {
    ttsLoading = false;
  }
}

function stopSpeaking() {
  if (activeSource) {
    try { activeSource.stop(); } catch (_) {}
    activeSource = null;
  }
  if (activeBtn) {
    activeBtn.classList.remove("active");
    activeBtn = null;
  }
}

async function speakText(text, btn) {
  if (!text || !text.trim()) return;

  // If same button clicked again → stop
  if (activeBtn === btn) {
    stopSpeaking();
    return;
  }
  stopSpeaking();

  const synth = await loadTTS();
  if (!synth) return;

  btn.classList.add("active");
  activeBtn = btn;
  showToast("Generating audio…", 30000);

  try {
    const output = await synth(text.trim(), { voice: TTS_VOICE });
    // output.audio is Float32Array, output.sampling_rate is a number
    const { audio, sampling_rate } = output;

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
    showToast("Speaking…", audio.length / sampling_rate * 1000 + 500);
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

// Run after DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", wireButtons);
} else {
  wireButtons();
}
