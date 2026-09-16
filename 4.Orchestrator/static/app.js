(() => {
  const errorBox = document.getElementById("error");
  const chatLog = document.getElementById("chat-log");
  const progressTag = document.getElementById("progress-tag");

  const steps = ["describe", "confirm", "photo", "location", "ready", "completed"];
  const STEP_LABELS = {
    describe: "Step 1 of 5 - Tell us the problem",
    confirm: "Step 2 of 5 - Confirm details",
    photo: "Step 3 of 5 - Add a photo",
    location: "Step 4 of 5 - Share location",
    ready: "Step 5 of 5 - Review and submit",
    completed: "Done",
  };

  let sessionId = null;
  let deviceLat = null;
  let deviceLon = null;
  let sourceLanguage = "en";
  let currentAudio = null;

  function showStep(name) {
    for (const s of steps) {
      document.getElementById(`step-${s}`).hidden = s !== name;
    }
    progressTag.textContent = STEP_LABELS[name] || "";
  }

  function addMessage(text, from) {
    chatLog.style.display = "block";
    const div = document.createElement("div");
    div.className = `msg ${from}`;
    div.textContent = text;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  // Speaks a system message aloud in the citizen's chosen language (via
  // Bhashini) - text is always shown too, speech is a best-effort overlay
  // that silently does nothing if the language isn't supported or the
  // service is unreachable.
  async function speak(text) {
    try {
      if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
      }
      const response = await fetch("/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language: sourceLanguage }),
      });
      if (response.status !== 200) return; // 204 = no speech available for this language
      const blob = await response.blob();
      currentAudio = new Audio(URL.createObjectURL(blob));
      await currentAudio.play();
    } catch {
      // Never let a speech failure break the (already-shown) text flow.
    }
  }

  function announceSystem(text) {
    addMessage(text, "system");
    speak(text);
  }

  // Plays a pre-generated "I'm working on it" clip the instant the citizen
  // submits, in parallel with the (slow, ~30s: ASR + Ollama classification)
  // /conversation/describe call - masks perceived latency, doesn't reduce
  // real processing time. speak()'s own currentAudio.pause() cuts this off
  // cleanly once the real reply is ready to play. Best-effort: a missing
  // clip (language not in generate_filler_audio.py's list, e.g. Santali, or
  // the one-time generation script hasn't been run yet) must never block
  // submission - autoplay is also blocked by some browsers outside a user
  // gesture, which this call always is (invoked from a click handler).
  function playFiller() {
    try {
      if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
      }
      const audio = new Audio(`/static/audio/filler_${sourceLanguage}.wav`);
      currentAudio = audio;
      audio.play().catch(() => {});
    } catch {
      // Ignored - see comment above.
    }
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.style.display = "block";
  }
  function hideError() {
    errorBox.style.display = "none";
  }
  function escapeText(value) {
    return String(value ?? "");
  }

  async function api(path, { method = "GET", body, isJson = false } = {}) {
    const opts = { method };
    if (body) {
      opts.body = body;
      if (isJson) opts.headers = { "Content-Type": "application/json" };
    }
    const response = await fetch(path, opts);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }

  function tryGetDeviceLocation() {
    return new Promise((resolve) => {
      if (!navigator.geolocation) return resolve(null);
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => resolve(null),
        { enableHighAccuracy: true, timeout: 6000 }
      );
    });
  }

  // ==================== Step 1: Describe ====================
  const micBtn = document.getElementById("mic-btn");
  const audioPreview = document.getElementById("audio-preview");
  const recordingStatus = document.getElementById("recording-status");
  let mediaRecorder = null;
  let recordedChunks = [];
  let recordedBlob = null;

  micBtn.addEventListener("click", async () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recordedChunks = [];
      const preferredType = ["audio/webm", "audio/mp4", "audio/ogg"].find(
        (t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t)
      );
      mediaRecorder = preferredType
        ? new MediaRecorder(stream, { mimeType: preferredType })
        : new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunks.push(e.data);
      };
      mediaRecorder.onstop = () => {
        const actualType = mediaRecorder.mimeType || "audio/webm";
        recordedBlob = new Blob(recordedChunks, { type: actualType });
        audioPreview.src = URL.createObjectURL(recordedBlob);
        audioPreview.style.display = "block";
        fixMediaRecorderDuration(audioPreview);
        recordingStatus.textContent = `Recorded ${(recordedBlob.size / 1024).toFixed(1)} KB`;
        recordingStatus.className = "geo-status ok";
        stream.getTracks().forEach((track) => track.stop());
        micBtn.textContent = "🎙️ Re-record";
        micBtn.classList.remove("recording");
      };
      recordingStatus.textContent = "Recording...";
      recordingStatus.className = "geo-status";
      mediaRecorder.start();
      micBtn.textContent = "⏹ Stop recording";
      micBtn.classList.add("recording");
    } catch (err) {
      showError("Microphone access failed: " + err.message);
    }
  });

  function fixMediaRecorderDuration(audioEl) {
    const onLoaded = () => {
      audioEl.removeEventListener("loadedmetadata", onLoaded);
      if (audioEl.duration === Infinity || Number.isNaN(audioEl.duration)) {
        const onTimeUpdate = () => {
          audioEl.removeEventListener("timeupdate", onTimeUpdate);
          audioEl.currentTime = 0;
        };
        audioEl.addEventListener("timeupdate", onTimeUpdate);
        audioEl.currentTime = 1e101;
      }
    };
    audioEl.addEventListener("loadedmetadata", onLoaded);
  }

  document.getElementById("describe-btn").addEventListener("click", async () => {
    hideError();
    const text = document.getElementById("text").value.trim();
    if (!text && !recordedBlob) {
      showError("Type a description or record a voice note first.");
      return;
    }

    sourceLanguage = document.getElementById("language").value;

    const formData = new FormData();
    if (text) formData.append("text", text);
    formData.append("source_language", sourceLanguage);
    if (recordedBlob) {
      const ext = recordedBlob.type.includes("mp4") ? "mp4" : recordedBlob.type.includes("ogg") ? "ogg" : "webm";
      formData.append("audio", recordedBlob, `recording.${ext}`);
    }

    addMessage(text || "(voice recording)", "user");
    const btn = document.getElementById("describe-btn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Processing...';
    playFiller();
    try {
      const data = await api("/conversation/describe", { method: "POST", body: formData });
      sessionId = data.session_id;
      announceSystem(data.message);
      if (data.warning) showError(data.warning);
      document.getElementById("confirm-statement").textContent = data.understood_statement;
      document.getElementById("confirm-domain").textContent = data.domain;
      document.getElementById("confirm-severity").textContent = data.severity;
      document.getElementById("correction-text").value = data.understood_statement;
      showStep("confirm");
    } catch (err) {
      showError(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Submit";
    }
  });

  // ==================== Step 2: Confirm ====================
  document.getElementById("confirm-yes-btn").addEventListener("click", async () => {
    hideError();
    addMessage("Yes, that's correct", "user");
    try {
      const data = await api(`/conversation/${sessionId}/confirm`, {
        method: "POST",
        isJson: true,
        body: JSON.stringify({ confirmed: true }),
      });
      announceSystem(data.message);
      showStep("photo");
    } catch (err) {
      showError(err.message);
    }
  });

  document.getElementById("confirm-no-btn").addEventListener("click", () => {
    document.getElementById("correction-box").style.display = "block";
  });

  document.getElementById("correction-submit-btn").addEventListener("click", async () => {
    hideError();
    const correctedText = document.getElementById("correction-text").value.trim();
    if (!correctedText) {
      showError("Enter the corrected description.");
      return;
    }
    addMessage(`Correction: ${correctedText}`, "user");
    try {
      const data = await api(`/conversation/${sessionId}/confirm`, {
        method: "POST",
        isJson: true,
        body: JSON.stringify({ confirmed: false, corrected_text: correctedText }),
      });
      announceSystem(data.message);
      document.getElementById("correction-box").style.display = "none";
      showStep("photo");
    } catch (err) {
      showError(err.message);
    }
  });

  // ==================== Step 3: Photo ====================
  const imageInput = document.getElementById("image");
  const imagePreview = document.getElementById("image-preview");
  const photoWarning = document.getElementById("photo-warning");
  const photoForceBtn = document.getElementById("photo-force-btn");

  imageInput.addEventListener("change", () => {
    const file = imageInput.files[0];
    photoWarning.style.display = "none";
    photoForceBtn.style.display = "none";
    if (!file) {
      imagePreview.style.display = "none";
      return;
    }
    imagePreview.src = URL.createObjectURL(file);
    imagePreview.style.display = "block";
    // Best-effort: grab device location now so it's ready if the photo has no EXIF GPS.
    tryGetDeviceLocation().then((loc) => {
      if (loc) {
        deviceLat = loc.lat;
        deviceLon = loc.lon;
      }
    });
  });

  async function uploadPhoto(force) {
    hideError();
    const file = imageInput.files[0];
    if (!file) {
      showError("Choose a photo first.");
      return;
    }
    const formData = new FormData();
    formData.append("image", file);
    if (deviceLat !== null) formData.append("device_lat", deviceLat);
    if (deviceLon !== null) formData.append("device_lon", deviceLon);
    if (force) formData.append("force", "true");

    const btn = document.getElementById("photo-btn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Analyzing photo...';
    try {
      const data = await api(`/conversation/${sessionId}/photo`, { method: "POST", body: formData });
      if (data.photo_matches === false && !force) {
        photoWarning.textContent = data.message;
        photoWarning.style.display = "block";
        photoForceBtn.style.display = "inline-block";
        return;
      }
      photoWarning.style.display = "none";
      photoForceBtn.style.display = "none";
      addMessage("(photo uploaded)", "user");
      announceSystem(data.message);
      if (data.state === "awaiting_location") {
        showStep("location");
      } else if (data.state === "ready") {
        await populateReadyStep();
        showStep("ready");
      }
    } catch (err) {
      showError(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Upload photo";
    }
  }

  document.getElementById("photo-btn").addEventListener("click", () => uploadPhoto(false));
  photoForceBtn.addEventListener("click", () => uploadPhoto(true));

  // ==================== Step 4: Location ====================
  document.getElementById("geo-btn").addEventListener("click", async () => {
    hideError();
    const geoStatus = document.getElementById("geo-status");
    geoStatus.textContent = "Requesting location...";
    geoStatus.className = "geo-status";
    const loc = await tryGetDeviceLocation();
    if (!loc) {
      geoStatus.textContent = "Could not get your location. Please check permissions and try again.";
      geoStatus.className = "geo-status err";
      return;
    }
    try {
      const data = await api(`/conversation/${sessionId}/location`, {
        method: "POST",
        isJson: true,
        body: JSON.stringify({ latitude: loc.lat, longitude: loc.lon }),
      });
      addMessage(`Location: ${loc.lat.toFixed(5)}, ${loc.lon.toFixed(5)}`, "user");
      announceSystem(data.message);
      await populateReadyStep();
      showStep("ready");
    } catch (err) {
      showError(err.message);
    }
  });

  document.getElementById("address-btn").addEventListener("click", async () => {
    hideError();
    const addressText = document.getElementById("address-text").value.trim();
    if (!addressText) {
      showError("Type a place name first.");
      return;
    }
    const btn = document.getElementById("address-btn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Looking up...';
    try {
      const data = await api(`/conversation/${sessionId}/location`, {
        method: "POST",
        isJson: true,
        body: JSON.stringify({ address_text: addressText }),
      });
      addMessage(addressText, "user");
      announceSystem(data.message);
      await populateReadyStep();
      showStep("ready");
    } catch (err) {
      showError(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Use this place";
    }
  });

  // ==================== Step 5: Ready / Finalize ====================
  async function populateReadyStep() {
    const summary = document.getElementById("ready-summary");
    const statement = document.getElementById("confirm-statement").textContent;
    summary.innerHTML = `
      <div><dt>Problem</dt><dd>${escapeText(statement)}</dd></div>
      <div><dt>Photo</dt><dd>Attached</dd></div>
      <div><dt>Location</dt><dd>Captured</dd></div>
    `;
  }

  document.getElementById("finalize-btn").addEventListener("click", async () => {
    hideError();
    const btn = document.getElementById("finalize-btn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Submitting...';
    try {
      const data = await api(`/conversation/${sessionId}/finalize`, { method: "POST" });
      announceSystem(data.message);
      document.getElementById("completed-message").textContent = data.message;
      showStep("completed");
    } catch (err) {
      showError(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Submit report";
    }
  });

  document.getElementById("restart-btn").addEventListener("click", () => window.location.reload());

  showStep("describe");
})();
