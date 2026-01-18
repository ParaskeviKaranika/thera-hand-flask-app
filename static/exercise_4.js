(() => {
  const canvas = document.getElementById("gameCanvas");
  const ctx = canvas.getContext("2d");
  const video = document.getElementById("cam");

  const startBtn = document.getElementById("startBtn");
  const restartBtn = document.getElementById("restartBtn");
  const stopBtn = document.getElementById("stopBtn");
  const statusEl = document.getElementById("status");

  const username = document.body.dataset.username || "Guest";
  const age = parseInt(document.body.dataset.age || "0", 10);

  const TT = JSON.parse((document.getElementById("i18n")?.textContent) || "{}");
  const tr = (key, vars = {}) => {
    let s = TT[key] || key;
    for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
    return s;
  };

  const W = canvas.width;
  const H = canvas.height;

  // ✅ same as python
  const repLevels = [5, 10, 15, 20, 25]; // 5 levels
  let currentLevelIndex = 0;

  // Exercises (ids + label_key + image + detector)
  const EXERCISES = [
    {
      id: "close_all_fingers",
      label_key: "game4_ex_close_all_fingers",
      image: "/assets/last_game/hand_gesture_images/close_all_fingers_fist.jpeg",
      detector: detect_all_fingers_closed,
    },
    {
      id: "open_only_thumb",
      label_key: "game4_ex_open_only_thumb",
      image: "/assets/last_game/hand_gesture_images/open_thumb.jpeg",
      detector: detect_only_thumb_open,
    },
    {
      id: "close_index_thumb",
      label_key: "game4_ex_close_index_thumb",
      image: "/assets/last_game/hand_gesture_images/close_index_thumb.jpeg",
      detector: (lm) => {
        const s = get_finger_states(lm);
        return (!s.index && !s.thumb && s.middle && s.ring && s.pinky);
      },
    },
    {
      id: "close_thumb_index_middle",
      label_key: "game4_ex_close_thumb_index_middle",
      image: "/assets/last_game/hand_gesture_images/close_index_thumb_middle.jpeg",
      detector: (lm) => {
        const s = get_finger_states(lm);
        return (!s.thumb && !s.index && !s.middle && s.ring && s.pinky);
      },
    },
    {
      id: "close_only_thumb",
      label_key: "game4_ex_close_only_thumb",
      image: "/assets/last_game/hand_gesture_images/close_thumb.jpeg",
      detector: (lm) => {
        const s = get_finger_states(lm);
        return (!s.thumb && s.index && s.middle && s.ring && s.pinky);
      },
    },
  ];

  // preload images
  const imgs = EXERCISES.map(ex => {
    const im = new Image();
    im.src = ex.image;
    return im;
  });

  // shuffled order
  let exerciseIndices = [];
  let currentExercisePos = 0;

  let score = 0;
  let reps = 0;
  let completed = false;

  let running = false;
  let stream = null;
  let startTime = 0;

  let statsSent = false;

  // mediapipe hand state
  let lastCountAt = 0; // ms (like sleep(0.5))
  let hasHand = false;
  let lastGestureMatch = false;

  function shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  function reset_state() {
    currentLevelIndex = 0;
    exerciseIndices = shuffle([...Array(EXERCISES.length).keys()]);
    currentExercisePos = 0;

    score = 0;
    reps = 0;
    completed = false;
    startTime = Date.now();

    statsSent = false;
    lastCountAt = 0;
    lastGestureMatch = false;

    statusEl.textContent = "OK";
  }

  function currentExercise() {
    return EXERCISES[exerciseIndices[currentExercisePos]];
  }

  function targetReps() {
    return repLevels[currentLevelIndex];
  }

  function elapsedSeconds() {
    return Math.floor((Date.now() - startTime) / 1000);
  }

  async function maybe_send_stats(result) {
    if (statsSent) return;
    statsSent = true;
    try {
      await fetch("/add_stat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          age,
          game_name: "exercise_4",
          score,
          time_seconds: elapsedSeconds(),
          result
        })
      });
    } catch (e) {
      console.warn("sendStats failed", e);
    }
  }

  // ===========================
  // Gesture logic (JS version)
  // ===========================
  function dist(a, b) {
    const dx = a.x - b.x, dy = a.y - b.y;
    return Math.hypot(dx, dy);
  }

  function get_finger_states(lm) {
    // lm: array of 21 landmarks, each has x,y normalized
    const tips = { thumb: 4, index: 8, middle: 12, ring: 16, pinky: 20 };
    const dips = { thumb: 3, index: 7, middle: 11, ring: 15, pinky: 19 };

    const wrist = lm[0];
    const middle_tip = lm[tips.middle];
    const hand_up = middle_tip.y < wrist.y;

    const thumb_tip = lm[tips.thumb];
    const middle_base = lm[9];
    const thumb_to_middle = dist(thumb_tip, middle_base);

    const states = {};
    for (const finger of Object.keys(tips)) {
      const tip = lm[tips[finger]];
      const dip = lm[dips[finger]];
      const d = dist(tip, dip);
      const dy = tip.y - dip.y;

      const is_open_oriented = hand_up ? (dy < 0) : (dy > 0);

      if (finger === "thumb") {
        if (thumb_to_middle < 0.06) states.thumb = false;
        else states.thumb = d > 0.05;
      } else {
        states[finger] = d > 0.04 && is_open_oriented;
      }
    }
    return states;
  }

  function detect_only_thumb_open(lm) {
    const s = get_finger_states(lm);
    return (s.thumb && !s.index && !s.middle && !s.ring && !s.pinky);
  }

  function detect_all_fingers_closed(lm) {
    const s = get_finger_states(lm);
    return (!s.thumb && !s.index && !s.middle && !s.ring && !s.pinky);
  }

  // ===========================
  // Rendering
  // ===========================
  function drawCamera() {
    if (video.videoWidth > 0) {
      ctx.save();
      ctx.translate(W, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(video, 0, 0, W, H);
      ctx.restore();
    } else {
      ctx.fillStyle = "black";
      ctx.fillRect(0, 0, W, H);
    }
  }

  function drawHUD() {
    const ex = currentExercise();
    const img = imgs[exerciseIndices[currentExercisePos]];

    // show target image
    ctx.fillStyle = "rgba(0,0,0,0.35)";
    ctx.fillRect(8, 70, 210, 210);
    if (img.complete) ctx.drawImage(img, 10, 70, 200, 200);

    // top buttons area (visual only)
    ctx.fillStyle = "rgba(128,128,128,0.7)";
    ctx.fillRect(10, 10, 150, 50);
    ctx.fillRect(170, 10, 150, 50);

    ctx.fillStyle = "white";
    ctx.font = "18px Arial";
    ctx.fillText(tr("game4_restart"), 22, 42);
    ctx.fillText(tr("game4_exit"), 220, 42);

    // right HUD
    ctx.font = "20px Arial";
    ctx.fillText(tr("game4_time", { seconds: elapsedSeconds() }), W - 250, 35);
    ctx.fillText(tr("game4_reps", { reps, target: targetReps() }), W - 250, 70);
    ctx.fillText(tr("game4_level", { level: currentLevelIndex + 1 }), W - 250, 105);

    // bottom instruction bar
    ctx.fillStyle = "rgba(0,0,0,0.65)";
    ctx.fillRect(0, H - 60, W, 60);
    ctx.fillStyle = "white";
    ctx.font = "22px Arial";
    const ins = tr(ex.label_key);
    ctx.fillText(tr("game4_instruction", { instruction: ins }), 10, H - 22);
  }

  function drawOverlayMessage(text, color = "rgb(0,255,0)") {
    ctx.fillStyle = "rgba(0,0,0,0.55)";
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = color;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "34px Arial";
    ctx.fillText(text, W / 2, H / 2);
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
  }

  // ===========================
  // Click handling on canvas (restart/exit like python)
  // ===========================
  function inRect(mx, my, x1, y1, x2, y2) {
    return (mx >= x1 && mx <= x2 && my >= y1 && my <= y2);
  }

  canvas.addEventListener("click", (ev) => {
    const r = canvas.getBoundingClientRect();
    const mx = (ev.clientX - r.left) * (W / r.width);
    const my = (ev.clientY - r.top) * (H / r.height);

    // restart area
    if (inRect(mx, my, 10, 10, 160, 60)) {
      reset_state();
      return;
    }
    // exit area
    if (inRect(mx, my, 170, 10, 320, 60)) {
      stopGame("exit");
      return;
    }
  });

  // ===========================
  // Main Loop
  // ===========================
  function step() {
    if (!running) return;

    drawCamera();
    drawHUD();

    // all done
    if (currentLevelIndex >= repLevels.length) {
      drawOverlayMessage(tr("game4_all_done"), "rgb(0,255,255)");
      maybe_send_stats("completed");
      running = false;
      restartBtn.disabled = false;
      stopBtn.disabled = false;
      startBtn.disabled = false;
      return;
    }

    // completed flash
    if (completed) {
      drawOverlayMessage(tr("game4_ex_completed"), "rgb(0,255,0)");
    }

    requestAnimationFrame(step);
  }

  // ===========================
  // MediaPipe
  // ===========================
  if (typeof Hands === "undefined") {
    statusEl.textContent = "❌ MediaPipe Hands δεν φορτώθηκε";
    return;
  }

  const hands = new Hands({
    locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1646424915/${file}`,
  });

  hands.setOptions({
    maxNumHands: 1,
    modelComplexity: 0,
    minDetectionConfidence: 0.7,
    minTrackingConfidence: 0.5,
  });

  hands.onResults((res) => {
    const lms = res.multiHandLandmarks;
    hasHand = !!(lms && lms.length);

    if (!running) return;
    if (!hasHand) return;
    if (completed) return;

    const lm = lms[0]; // 21 landmarks
    const ex = currentExercise();

    const match = !!ex.detector(lm);

    // count reps only on rising edge + 0.5s cooldown
    const now = Date.now();
    const cooldownOk = (now - lastCountAt) > 500;

    if (match && !lastGestureMatch && cooldownOk) {
      reps += 1;
      lastCountAt = now;
    }
    lastGestureMatch = match;

    // reached target
    if (reps >= targetReps() && !completed) {
      completed = true;

      // score rule
      score += 10;

      // after 2s move forward
      setTimeout(() => {
        reps = 0;
        completed = false;
        currentExercisePos += 1;

        // if finished all exercises in level -> next level
        if (currentExercisePos >= exerciseIndices.length) {
          currentExercisePos = 0;
          currentLevelIndex += 1;
          if (currentLevelIndex < repLevels.length) shuffle(exerciseIndices);
          startTime = Date.now(); // reset timer like python
        }
      }, 2000);
    }
  });

  async function processFrame() {
    if (!running) return;
    try {
      await hands.send({ image: video });
    } catch (e) {
      console.error(e);
      statusEl.textContent = "❌ MediaPipe error";
      stopGame("exit");
      return;
    }
    requestAnimationFrame(processFrame);
  }

  // ===========================
  // Camera
  // ===========================
  async function startCamera() {
    statusEl.textContent = "📷 Ζητάω άδεια κάμερας...";
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" },
      audio: false
    });
    video.srcObject = stream;
    await video.play();
    statusEl.textContent = "🎥 OK";
    processFrame();
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
    video.srcObject = null;
  }

  // ===========================
  // Controls
  // ===========================
  async function startGame() {
    // unlock audio if you add sound later
    reset_state();

    running = true;
    startBtn.disabled = true;
    restartBtn.disabled = false;
    stopBtn.disabled = false;

    await startCamera();
    startTime = Date.now();
    requestAnimationFrame(step);
  }

  function stopGame(result) {
    running = false;
    stopCamera();
    if (result) maybe_send_stats(result);

    startBtn.disabled = false;
    restartBtn.disabled = false;
    stopBtn.disabled = false;

    statusEl.textContent = tr("game4_exit_msg");
  }

  startBtn.onclick = startGame;
  restartBtn.onclick = () => reset_state();
  stopBtn.onclick = () => stopGame("exit");

  // init screen (preview without camera)
  reset_state();
  drawCamera(); // black
  drawHUD();
})();
