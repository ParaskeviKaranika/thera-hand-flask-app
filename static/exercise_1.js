// =======================================
// TheraHand – Exercise 1
// ✅ No "JS loaded" message (status stays empty)
// ✅ Stop closes camera reliably (tracks.stop + video.pause + srcObject=null)
// ✅ i18n buttons + HUD text (from <script id="i18n"> JSON)
// ✅ Win/Lose message is drawn INSIDE the canvas (overlay)
// =======================================

(() => {
  // ---------- Basic UI / session ----------
  // Get DOM elements (buttons, status area, canvas, hidden video)
  const statusEl = document.getElementById("status");
  const startBtn = document.getElementById("startBtn");
  const restartBtn = document.getElementById("restartBtn");
  const stopBtn = document.getElementById("stopBtn");

  const canvas = document.getElementById("gameCanvas");
  const ctx = canvas.getContext("2d");
  const video = document.getElementById("cam");

  // Safety check: if any element is missing, exit early
  if (!statusEl || !startBtn || !restartBtn || !stopBtn || !canvas || !ctx || !video) {
    console.error("Missing DOM element(s). Check ids.");
    return;
  }

  // Keep status empty (we show win/lose inside the canvas instead)
  statusEl.textContent = "";

  // Read session/user info from data-* attributes on <body>
  const username = document.body.dataset.username || "Guest";
  const age = parseInt(document.body.dataset.age || "0", 10);

  // ---------- i18n from HTML ----------
  // Read translated strings from the embedded JSON script tag.
  // This allows the same JS file to work in Greek/English without hardcoding.
  const i18nEl = document.getElementById("i18n");
  const TT = i18nEl ? JSON.parse(i18nEl.textContent || "{}") : {};

  // Translation helper: tr("key") returns translated text; supports {placeholders}
  const tr = (key, vars = {}) => {
    let s = TT[key] || key;
    for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
    return s;
  };

  // Overwrite button labels using translations (GR/EN)
  startBtn.textContent = tr("btn_start");
  restartBtn.textContent = tr("btn_restart");
  stopBtn.textContent = tr("btn_stop");

  // ---------- Canvas sizes ----------
  // Note: W/H are the *internal* resolution (canvas width/height attributes).
  const W = canvas.width;
  const H = canvas.height;

  // ---------- Constants ----------
  const GAME_TIME = 30;   // game duration in seconds
  const WIN_SCORE = 10;   // stars needed to win
  const STAR_SIZE = 40;   // star render size
  const HAND_SIZE = 80;   // hand icon render size

  // ---------- Assets ----------
  // Images are served from Flask under /assets/first_game/
  const bg = new Image();
  bg.src = "/assets/first_game/sky.jpg";

  const starImg = new Image();
  starImg.src = "/assets/first_game/star.png";

  const handImg = new Image();
  handImg.src = "/assets/first_game/hand.png";

  // --- Remove white background from star (simple "color key") ---
  // We preprocess the star image once into an offscreen canvas and make near-white pixels transparent.
  let starProcessed = null;
  starImg.onload = () => {
    const off = document.createElement("canvas");
    off.width = STAR_SIZE;
    off.height = STAR_SIZE;
    const octx = off.getContext("2d");

    octx.drawImage(starImg, 0, 0, STAR_SIZE, STAR_SIZE);
    const imgData = octx.getImageData(0, 0, STAR_SIZE, STAR_SIZE);
    const d = imgData.data;

    for (let i = 0; i < d.length; i += 4) {
      const r = d[i], g = d[i + 1], b = d[i + 2];
      // Anything very close to white becomes transparent
      if (r >= 245 && g >= 245 && b >= 245) d[i + 3] = 0;
    }
    octx.putImageData(imgData, 0, 0);
    starProcessed = off;
  };

  // ---------- Game State ----------
  let score = 0;
  let running = false;     // main game loop flag
  let startTime = 0;       // timestamp when game starts

  // Used to draw an end-screen overlay inside the canvas
  let gameState = "ready"; // ready | playing | win | lose

  let stars = [];
  let hand = { visible: false, x9: 0, y9: 0, x12: 0, y12: 0 };

  // Random integer helper
  function rand(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  // Create 5 random stars on the canvas
  function resetStars() {
    stars = Array.from({ length: 5 }, () => ({
      x: rand(0, W - STAR_SIZE),
      y: rand(0, H - STAR_SIZE),
    }));
  }

  // Remaining time (seconds)
  function timeLeft() {
    if (!running) return GAME_TIME;
    return Math.max(0, GAME_TIME - Math.floor((Date.now() - startTime) / 1000));
  }

  // ---------- Text helpers (auto-fit) ----------
  // These helpers make long strings fit the canvas width (important for Greek).
  function fitFontSize(text, maxWidth, startSize, minSize = 14) {
    let size = startSize;
    while (size > minSize) {
      ctx.font = `${size}px Arial`;
      if (ctx.measureText(text).width <= maxWidth) break;
      size -= 1;
    }
    return size;
  }

  function drawCenteredFit(text, cx, cy, startSize, maxWidth, color = "white") {
    const size = fitFontSize(text, maxWidth, startSize);
    ctx.font = `${size}px Arial`;
    ctx.fillStyle = color;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, cx, cy);
  }

  // ---------- Render ----------
  function draw() {
    ctx.clearRect(0, 0, W, H);

    // Background
    if (bg.complete) ctx.drawImage(bg, 0, 0, W, H);

    // Stars
    for (const s of stars) {
      if (starProcessed) ctx.drawImage(starProcessed, s.x, s.y, STAR_SIZE, STAR_SIZE);
      else if (starImg.complete) ctx.drawImage(starImg, s.x, s.y, STAR_SIZE, STAR_SIZE);
    }

    // Hand cursor icon (follows landmark 9)
    if (hand.visible && handImg.complete) {
      ctx.drawImage(handImg, hand.x9 - HAND_SIZE / 2, hand.y9 - HAND_SIZE / 2, HAND_SIZE, HAND_SIZE);
    }

    // HUD (localized)
    ctx.fillStyle = "white";
    ctx.font = "22px Arial";
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    ctx.fillText(`${tr("hud_score")}: ${score}`, 10, 30);
    ctx.fillText(`${tr("hud_time")}: ${timeLeft()}s`, 10, 60);

    // Win/Lose overlay inside canvas (instead of using status text below)
    if (gameState === "win" || gameState === "lose") {
      ctx.fillStyle = "rgba(0,0,0,0.60)";
      ctx.fillRect(0, 0, W, H);

      const cx = W / 2;
      const cy = H / 2;
      const maxW = W - 40;

      drawCenteredFit(
        gameState === "win" ? tr("win_title") : tr("lose_title"),
        cx,
        cy - 22,
        40,
        maxW,
        gameState === "win" ? "rgb(0,255,0)" : "white"
      );

      drawCenteredFit(tr("tap_restart"), cx, cy + 22, 18, maxW, "white");

      // Restore defaults for any future left-aligned drawing
      ctx.textAlign = "left";
      ctx.textBaseline = "alphabetic";
    }
  }

  // ---------- Game logic ----------
  function checkCollisions() {
    if (!hand.visible) return;

    // Gesture condition: "open hand" style check (y12 > y9)
    // You can change this condition if you prefer a different gesture.
    if (hand.y12 <= hand.y9) return;

    // If hand center intersects a star area -> collect it
    for (let i = 0; i < stars.length; i++) {
      const s = stars[i];
      const hit =
        hand.x9 > s.x &&
        hand.x9 < s.x + STAR_SIZE &&
        hand.y9 > s.y &&
        hand.y9 < s.y + STAR_SIZE;

      if (hit) {
        // Respawn this star somewhere else
        stars[i] = { x: rand(0, W - STAR_SIZE), y: rand(0, H - STAR_SIZE) };
        score++;
        break;
      }
    }
  }

  // End the game and show overlay
  function endGame(result) {
    running = false;
    gameState = result; // "win" | "lose"

    // Keep status area empty (no message below canvas)
    statusEl.textContent = "";

    // Save stats to backend (does not block rendering)
    sendStats(result);

    // Enable/disable buttons
    startBtn.disabled = false;
    restartBtn.disabled = false;
    stopBtn.disabled = true;

    // Draw final frame with overlay
    draw();
  }

  // Main animation loop
  function loop() {
    if (!running) return;

    checkCollisions();
    draw();

    if (score >= WIN_SCORE) {
      endGame("win");
      return;
    }
    if (timeLeft() <= 0) {
      endGame("lose");
      return;
    }

    requestAnimationFrame(loop);
  }

  // ---------- Backend stats ----------
  async function sendStats(result) {
    try {
      await fetch("/add_stat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          age,
          game_name: "Άσκηση 1",
          score,
          time_seconds: GAME_TIME - timeLeft(),
          result
        })
      });
    } catch (e) {
      // Non-fatal: game can still run even if stats fail
      console.warn("sendStats failed:", e);
    }
  }

  // ---------- MediaPipe Hands ----------
  // Uses Hands landmarks to track hand position.
  if (typeof Hands === "undefined") {
    console.error("❌ MediaPipe Hands not loaded");
    statusEl.textContent = "❌ MediaPipe not loaded";
    return;
  }

  const hands = new Hands({
    locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1646424915/${file}`,
  });

  hands.setOptions({
    maxNumHands: 1,
    modelComplexity: 0,
    minDetectionConfidence: 0.5,
    minTrackingConfidence: 0.5,
  });

  // Called after each processed frame
  hands.onResults((res) => {
    const lms = res.multiHandLandmarks;
    if (!lms || lms.length === 0) {
      hand.visible = false;
      return;
    }

    // We use landmark 9 (middle finger MCP) as a stable hand "center"
    // and landmark 12 (middle fingertip) to check the gesture condition.
    const lm = lms[0];
    hand.visible = true;
    hand.x9 = lm[9].x * W;
    hand.y9 = lm[9].y * H;
    hand.x12 = lm[12].x * W;
    hand.y12 = lm[12].y * H;
  });

  // ---------- Camera ----------
  let stream = null;
  let processing = false; // Hard stop flag for the frame processing loop

  async function startCamera() {
    try {
      statusEl.textContent = ""; // keep UI clean

      // Request user-facing camera stream
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false
      });

      // Attach stream to hidden video element
      video.srcObject = stream;
      video.setAttribute("playsinline", "");
      await video.play();

      // Start MediaPipe frame loop
      processing = true;
      processFrame();
    } catch (e) {
      console.error("startCamera failed:", e);
      statusEl.textContent = "❌ Camera failed";

      running = false;
      processing = false;

      startBtn.disabled = false;
      restartBtn.disabled = false;
      stopBtn.disabled = true;
    }
  }

  // Sends each video frame into MediaPipe
  async function processFrame() {
    if (!running || !processing) return;
    if (!video.srcObject) return;

    try {
      await hands.send({ image: video });
    } catch (e) {
      console.error("hands.send failed:", e);
      statusEl.textContent = "❌ MediaPipe error";
      running = false;
      processing = false;
      return;
    }

    requestAnimationFrame(processFrame);
  }

  // Stops camera stream + MediaPipe loop
  function stopCamera() {
    processing = false;

    // Stop all camera tracks (this actually releases the camera)
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }

    // Stop the video element
    try { video.pause(); } catch {}
    video.srcObject = null;

    // Clear hand state so cursor disappears
    hand.visible = false;
  }

  // ---------- Buttons ----------
  startBtn.onclick = async () => {
    score = 0;
    resetStars();
    startTime = Date.now();

    running = true;
    gameState = "playing";

    startBtn.disabled = true;
    restartBtn.disabled = true;
    stopBtn.disabled = false;

    await startCamera();
    requestAnimationFrame(loop);
  };

  // Restart simply calls Start again
  restartBtn.onclick = () => startBtn.onclick();

  stopBtn.onclick = () => {
    running = false;
    stopCamera();

    startBtn.disabled = false;
    restartBtn.disabled = false;
    stopBtn.disabled = true;

    gameState = "ready";
    statusEl.textContent = ""; // keep UI clean
    draw();
  };

  // ---------- Init ----------
  resetStars();
  draw();
})();
