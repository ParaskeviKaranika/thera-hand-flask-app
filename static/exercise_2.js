(() => {
  // ==============================
  // DOM references
  // ==============================
  const statusEl = document.getElementById("status");
  const startBtn = document.getElementById("startBtn");
  const restartBtn = document.getElementById("restartBtn");
  const stopBtn = document.getElementById("stopBtn");
  const canvas = document.getElementById("gameCanvas");
  const ctx = canvas.getContext("2d");
  const video = document.getElementById("cam");

  // User/session data passed from Flask (used for stats saving)
  const username = document.body.dataset.username || "Guest";
  const age = parseInt(document.body.dataset.age || "0", 10);

  // Canvas internal resolution (not CSS size)
  const W = canvas.width;
  const H = canvas.height;

  // ==============================
  // Game settings (mirrors the Python version)
  // ==============================
  // Target drop zone (green rectangle)
  const target = { x: 100, y: 100, w: 200, h: 200 };

  // Points to reach per level
  const LEVELS = [10, 15, 20];

  // Seconds per level
  const TIME_LIMIT = 60;

  // Shape dimensions
  const circleR = 50;
  const cubeSize = 70;
  const rectW = 100;
  const rectH = 60;
  const triSize = 80;

  // ==============================
  // Game state variables
  // ==============================
  let shapes = [];
  let levelIndex = 0;
  let score = 0;
  let startTime = 0;
  let running = false;

  // playing | win | lose
  let gameState = "playing";

  // Index of currently grabbed shape (null = none grabbed)
  let holdingIndex = null;

  // Brief highlight animation on target when a shape is placed correctly
  let highlightStart = 0;
  const highlightDuration = 0.5;

  // ==============================
  // Helpers
  // ==============================
  function randInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  function randColor() {
    return `rgb(${randInt(0, 255)},${randInt(0, 255)},${randInt(0, 255)})`;
  }

  // Create a random shape with random position & color
  function createRandomShape() {
    const type = ["cube", "rectangle", "circle", "triangle"][randInt(0, 3)];
    return { type, x: randInt(100, 500), y: randInt(100, 400), color: randColor() };
  }

  // Prevent stats from being submitted multiple times
  let sentOnce = false;

  // Reset everything to initial game state
  function resetGame() {
    // Initial set of shapes (fixed colors/positions)
    shapes = [
      { type: "cube", x: 500, y: 100, color: "rgb(0,255,255)" },
      { type: "rectangle", x: 500, y: 200, color: "rgb(255,255,0)" },
      { type: "circle", x: 500, y: 300, color: "rgb(0,0,0)" },
      { type: "triangle", x: 500, y: 400, color: "rgb(128,128,128)" },
    ];

    levelIndex = 0;
    score = 0;
    startTime = Date.now();

    gameState = "playing";
    holdingIndex = null;
    highlightStart = 0;
    sentOnce = false;

    // Draw one frame immediately
    draw();
  }

  // Remaining time for the current level
  function remainingSeconds() {
    const elapsed = (Date.now() - startTime) / 1000;
    return Math.max(0, Math.floor(TIME_LIMIT - elapsed));
  }

  // Hit-test: check if a point is inside a given shape
  function isInsideShape(px, py, shp) {
    const x = shp.x, y = shp.y;

    if (shp.type === "cube") {
      return (x < px && px < x + cubeSize && y < py && py < y + cubeSize);
    }

    if (shp.type === "rectangle") {
      return (x < px && px < x + rectW && y < py && py < y + rectH);
    }

    // Triangle uses a simple bounding-box hit-test (not perfect geometry, but OK for UX)
    if (shp.type === "triangle") {
      return (x < px && px < x + triSize && y < py && py < y + triSize);
    }

    if (shp.type === "circle") {
      const cx = x + circleR, cy = y + circleR;
      const dx = px - cx, dy = py - cy;
      return (dx * dx + dy * dy) < (circleR * circleR);
    }

    return false;
  }

  // Check if a shape is inside the target zone
  function isInsideTarget(shp) {
    // For circles, we check the center point
    let sx = shp.x, sy = shp.y;
    if (shp.type === "circle") {
      sx += circleR;
      sy += circleR;
    }

    return (
      target.x < sx && sx < target.x + target.w &&
      target.y < sy && sy < target.y + target.h
    );
  }

  // ==============================
  // Rendering
  // ==============================
  function drawTarget() {
    // Make the target outline thicker for a brief moment after success
    const now = Date.now();
    const inHighlight = highlightStart && (now - highlightStart) / 1000 < highlightDuration;

    ctx.strokeStyle = "rgb(0,255,0)";
    ctx.lineWidth = inHighlight ? 6 : 2;
    ctx.strokeRect(target.x, target.y, target.w, target.h);
  }

  // Draw a single shape based on its type
  function drawShape(shp) {
    ctx.fillStyle = shp.color;
    const x = Math.round(shp.x), y = Math.round(shp.y);

    if (shp.type === "cube") {
      ctx.fillRect(x, y, cubeSize, cubeSize);

    } else if (shp.type === "rectangle") {
      ctx.fillRect(x, y, rectW, rectH);

    } else if (shp.type === "circle") {
      ctx.beginPath();
      ctx.arc(x + circleR, y + circleR, circleR, 0, Math.PI * 2);
      ctx.fill();

    } else if (shp.type === "triangle") {
      ctx.beginPath();
      ctx.moveTo(x, y + triSize);
      ctx.lineTo(x + triSize / 2, y);
      ctx.lineTo(x + triSize, y + triSize);
      ctx.closePath();
      ctx.fill();
    }
  }

  // Outline + fill text for better visibility
  function strokeText(text, x, y) {
    ctx.lineWidth = 5;
    ctx.strokeStyle = "rgba(0,0,0,0.7)";
    ctx.strokeText(text, x, y);
    ctx.fillStyle = "white";
    ctx.fillText(text, x, y);
  }

  // HUD with current level/score and remaining time
  function drawHUD() {
    ctx.font = "22px Arial";
    strokeText(`Level: ${levelIndex + 1}   Score: ${score}/${LEVELS[levelIndex]}`, 10, 30);
    strokeText(`Time: ${remainingSeconds()}s`, 10, 60);
  }

  // Button hitboxes for end screen (clickable inside canvas)
  const restartBtnRect = { x: 250, y: 200, w: 120, h: 50 };
  const exitBtnRect = { x: 250, y: 300, w: 120, h: 50 };

  // Draw a rounded "pill" button
  function drawPillButton(btn, label) {
    const { x, y, w, h } = btn;
    const r = Math.floor(h / 2);

    ctx.fillStyle = "rgb(128,128,128)";
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.arc(x + w - r, y + r, r, -Math.PI / 2, Math.PI / 2);
    ctx.lineTo(x + r, y + h);
    ctx.arc(x + r, y + r, r, Math.PI / 2, -Math.PI / 2);
    ctx.closePath();
    ctx.fill();

    ctx.font = "24px Arial";
    ctx.fillStyle = "white";
    ctx.fillText(label, x + 22, y + 33);
  }

  // End screen overlay (win/lose + clickable buttons)
  function drawEndScreen() {
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.fillRect(0, 0, W, H);

    ctx.font = "48px Arial";
    ctx.fillStyle = (gameState === "win") ? "rgb(0,255,0)" : "rgb(255,255,0)";
    ctx.fillText(gameState === "win" ? "You Win!" : "You Lose!", 170, 170);

    drawPillButton(restartBtnRect, "Restart");
    drawPillButton(exitBtnRect, "Exit");
  }

  // ==============================
  // Hand marker state (for debugging/feedback)
  // ==============================
  let avgX = 0, avgY = 0;
  let pinch = false;

  function draw() {
    ctx.clearRect(0, 0, W, H);

    // Camera as background (mirrored selfie view)
    if (video.videoWidth > 0 && video.videoHeight > 0) {
      ctx.save();
      ctx.translate(W, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(video, 0, 0, W, H);
      ctx.restore();
    } else {
      // Fallback background if camera is not ready
      ctx.fillStyle = "black";
      ctx.fillRect(0, 0, W, H);
    }

    // Target + shapes
    drawTarget();
    for (const shp of shapes) drawShape(shp);

    // Draw the tracked hand point (red = open, green = pinch)
    if (video.readyState >= 2 && avgX && avgY) {
      ctx.fillStyle = pinch ? "lime" : "red";
      ctx.beginPath();
      ctx.arc(avgX, avgY, 10, 0, Math.PI * 2);
      ctx.fill();
    }

    drawHUD();

    // Show end screen overlay if game ended
    if (gameState !== "playing") drawEndScreen();
  }

  // ==============================
  // Game loop logic
  // ==============================
  function tick() {
    if (!running) return;

    if (gameState === "playing") {
      const rem = remainingSeconds();

      // Win condition: reached target score for this level
      if (score >= LEVELS[levelIndex]) {
        if (levelIndex < LEVELS.length - 1) {
          // Advance to next level
          levelIndex += 1;
          score = 0;
          startTime = Date.now();
        } else {
          // Final win
          gameState = "win";
          if (!sentOnce) { sendStats("win"); sentOnce = true; }
        }
      } else if (rem <= 0) {
        // Lose condition: timer ran out
        gameState = "lose";
        if (!sentOnce) { sendStats("lose"); sentOnce = true; }
      }
    }

    draw();
    requestAnimationFrame(tick);
  }

  // Send statistics to backend
  async function sendStats(result) {
    const time_seconds = Math.min(TIME_LIMIT, Math.round((Date.now() - startTime) / 1000));
    try {
      await fetch("/add_stat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          age,
          game_name: "Άσκηση 2",
          score,
          time_seconds,
          // Note: you currently send Greek strings even in English mode
          result: (result === "win" ? "Νίκη" : "Ήττα")
        })
      });
    } catch (e) {
      console.warn("sendStats failed", e);
    }
  }

  // ==============================
  // MediaPipe Hands setup
  // ==============================
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
    minDetectionConfidence: 0.5,
    minTrackingConfidence: 0.5,
  });

  // Distance helper (for pinch detection)
  function dist(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  // Called for each processed frame
  hands.onResults((res) => {
    const lms = res.multiHandLandmarks;
    if (!lms || lms.length === 0) {
      pinch = false;
      return;
    }

    const lm = lms[0];

    // Fingertip landmark indexes: thumb, index, middle, ring, pinky
    const tips = [4, 8, 12, 16, 20];

    // Mirror X because the camera background is mirrored on canvas
    const pts = tips.map(i => ({
      x: (1 - lm[i].x) * W,
      y: lm[i].y * H
    }));

    // Use average fingertip position as a simple "hand pointer"
    avgX = pts.reduce((s, p) => s + p.x, 0) / pts.length;
    avgY = pts.reduce((s, p) => s + p.y, 0) / pts.length;

    // Pinch gesture: thumb tip (pts[0]) close to index tip (pts[1])
    pinch = dist(pts[0], pts[1]) < 35;

    // On pinch start, pick up a shape if the pointer is inside one
    if (gameState === "playing" && pinch && holdingIndex === null) {
      for (let i = 0; i < shapes.length; i++) {
        if (isInsideShape(avgX, avgY, shapes[i])) {
          holdingIndex = i;
          break;
        }
      }
    }

    // Release shape when pinch is released
    if (!pinch) holdingIndex = null;

    // If holding a shape, move it with the hand pointer
    if (gameState === "playing" && holdingIndex !== null) {
      const shp = shapes[holdingIndex];

      // Center the shape under the pointer depending on its geometry
      if (shp.type === "cube") { shp.x = avgX - cubeSize / 2; shp.y = avgY - cubeSize / 2; }
      if (shp.type === "rectangle") { shp.x = avgX - rectW / 2; shp.y = avgY - rectH / 2; }
      if (shp.type === "circle") { shp.x = avgX - circleR; shp.y = avgY - circleR; }
      if (shp.type === "triangle") { shp.x = avgX - triSize / 2; shp.y = avgY - triSize / 2; }

      // Successful placement: inside target zone
      if (isInsideTarget(shp)) {
        score += 1;
        highlightStart = Date.now(); // start target highlight animation

        // Replace placed shape with a new random one
        shapes.splice(holdingIndex, 1);
        shapes.push(createRandomShape());
        holdingIndex = null;
      }
    }
  });

  // ==============================
  // Camera handling
  // ==============================
  let stream = null;

  async function startCamera() {
    statusEl.textContent = "📷 Ζητάω άδεια κάμερας...";
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" },
      audio: false
    });

    video.srcObject = stream;
    await video.play();

    console.log("video dims:", video.videoWidth, video.videoHeight);

    statusEl.textContent = "🎥 Κάμερα OK — πιάσε σχήμα (pinch) και βάλε στο πράσινο τετράγωνο";

    // Start MediaPipe processing loop
    processFrame();
  }

  async function processFrame() {
    if (!running) return;
    try {
      await hands.send({ image: video });
    } catch (e) {
      console.error(e);
      statusEl.textContent = "❌ MediaPipe error (δες Console)";
      running = false;
      return;
    }
    requestAnimationFrame(processFrame);
  }

  function stopCamera() {
    // Stop camera tracks and release the webcam
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
    video.srcObject = null;
  }

  // ==============================
  // Canvas click handling (end screen buttons)
  // ==============================
  function inRect(mx, my, r) {
    return (r.x <= mx && mx <= r.x + r.w && r.y <= my && my <= r.y + r.h);
  }

  canvas.addEventListener("click", (ev) => {
    const rect = canvas.getBoundingClientRect();

    // Convert screen coords → canvas coords
    const mx = (ev.clientX - rect.left) * (W / rect.width);
    const my = (ev.clientY - rect.top) * (H / rect.height);

    // Only clickable when game is not playing (win/lose)
    if (gameState === "playing") return;

    if (inRect(mx, my, restartBtnRect)) {
      resetGame();
      return;
    }
    if (inRect(mx, my, exitBtnRect)) {
      running = false;
      stopCamera();
      statusEl.textContent = "Έξοδος";
    }
  });

  // ==============================
  // Buttons
  // ==============================
  startBtn.onclick = async () => {
    resetGame();
    running = true;

    startBtn.disabled = true;
    restartBtn.disabled = true;
    stopBtn.disabled = false;

    await startCamera();
    requestAnimationFrame(tick);
  };

  // Restart button repeats Start behavior
  restartBtn.onclick = () => startBtn.onclick();

  stopBtn.onclick = () => {
    running = false;
    stopCamera();

    startBtn.disabled = false;
    restartBtn.disabled = false;
    stopBtn.disabled = true;

    statusEl.textContent = "⏹️ Σταμάτησε";
  };

  // Initial state
  resetGame();
})();
