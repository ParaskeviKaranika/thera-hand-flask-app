 (() => {
  const statusEl = document.getElementById("status");
  const startBtn = document.getElementById("startBtn");
  const restartBtn = document.getElementById("restartBtn");
  const stopBtn = document.getElementById("stopBtn");
  const canvas = document.getElementById("gameCanvas");
  const ctx = canvas.getContext("2d");
  const video = document.getElementById("cam");

  const username = document.body.dataset.username || "Guest";
  const age = parseInt(document.body.dataset.age || "0", 10);

  // ✅ i18n from translations.py via HTML
  const i18nEl = document.getElementById("i18n");
  const TT = i18nEl ? JSON.parse(i18nEl.textContent || "{}") : {};
  const tr = (key, vars = {}) => {
    let s = TT[key] || key;
    for (const [k, v] of Object.entries(vars)) {
      s = s.replaceAll(`{${k}}`, String(v));
    }
    return s;
  };

  const W = canvas.width;
  const H = canvas.height;

  const GAME_SIZE = 4;
  const TILESIZE = 100;

  const gridW = GAME_SIZE * TILESIZE; // 400
  const gridH = GAME_SIZE * TILESIZE; // 400
  const offsetX = Math.floor((W - gridW) / 2);
  const offsetY = Math.floor((H - gridH) / 4);

  const LEVEL_GOALS = [5, 10, 15];

  let running = false;
  let stream = null;

  let board = [];
  let level = 1;
  let score = 0;
  let levelScore = 0;
  let moves = 0;
  let startTime = 0;

  let targetPos = null;
  let sentOnce = false;
  let gameState = "instructions"; // instructions | playing | between | done

  // hand
  let pinch = false;
  let prevPinch = false; // ✅ edge trigger
  let fingerX = 0;
  let fingerY = 0;
  let lastMoveAt = 0;

  // ✅ sound (Solution B)
  const successAudio = new Audio("/assets/third_game/success.wav");
  successAudio.preload = "auto";

  function nowSec() { return (Date.now() - startTime) / 1000; }
  function clone2D(a) { return a.map(r => r.slice()); }
  function fitCanvasToDisplaySize() {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;

  const newWidth = Math.round(rect.width * dpr);
  const newHeight = Math.round(rect.height * dpr);

  if (canvas.width !== newWidth || canvas.height !== newHeight) {
    canvas.width = newWidth;
    canvas.height = newHeight;
  }
}

fitCanvasToDisplaySize();
window.addEventListener('resize', () => {
  fitCanvasToDisplaySize();
  draw(); // ξανασχεδίασε
});


  function makeSolvedBoard() {
    const b = [];
    let v = 1;
    for (let r = 0; r < GAME_SIZE; r++) {
      b.push([]);
      for (let c = 0; c < GAME_SIZE; c++) {
        if (r === GAME_SIZE - 1 && c === GAME_SIZE - 1) b[r][c] = 0;
        else b[r][c] = v++;
      }
    }
    return b;
  }

  function findEmpty() {
    for (let r = 0; r < GAME_SIZE; r++) {
      for (let c = 0; c < GAME_SIZE; c++) {
        if (board[r][c] === 0) return { r, c };
      }
    }
    return null;
  }

  function neighbors(pos) {
    const out = [];
    const { r, c } = pos;
    if (c > 0) out.push({ r, c: c - 1 });
    if (c < GAME_SIZE - 1) out.push({ r, c: c + 1 });
    if (r > 0) out.push({ r: r - 1, c });
    if (r < GAME_SIZE - 1) out.push({ r: r + 1, c });
    return out;
  }

  function shuffleBoardValidMoves(times = 40) {
    board = clone2D(makeSolvedBoard());
    for (let i = 0; i < times; i++) {
      const empty = findEmpty();
      const opts = neighbors(empty);
      const pick = opts[Math.floor(Math.random() * opts.length)];
      const tmp = board[pick.r][pick.c];
      board[pick.r][pick.c] = 0;
      board[empty.r][empty.c] = tmp;
    }
  }

  function pickNewTarget() {
    const empty = findEmpty();
    const opts = neighbors(empty).filter(p => board[p.r][p.c] !== 0);
    if (opts.length === 0) { targetPos = null; return; }
    targetPos = opts[Math.floor(Math.random() * opts.length)];
  }

  function resetLevel() {
    shuffleBoardValidMoves(50);
    pickNewTarget();
    levelScore = 0;
    moves = 0;
    startTime = Date.now();
    gameState = "playing";
  }

  function resetGameAll() {
    level = 1;
    score = 0;
    sentOnce = false;
    resetLevel();
  }

  function tileAtPixel(px, py) {
    const tx = Math.floor((px - offsetX) / TILESIZE);
    const ty = Math.floor((py - offsetY) / TILESIZE);
    if (tx < 0 || tx >= GAME_SIZE || ty < 0 || ty >= GAME_SIZE) return null;
    return { r: ty, c: tx };
  }

  function isAdjacentToEmpty(pos) {
    const e = findEmpty();
    return (Math.abs(e.r - pos.r) + Math.abs(e.c - pos.c)) === 1;
  }

  function swapWithEmpty(pos) {
    const empty = findEmpty();
    const tmp = board[pos.r][pos.c];
    board[pos.r][pos.c] = 0;
    board[empty.r][empty.c] = tmp;
    moves += 1;
  }

  // ---------- Rendering ----------
  function drawCameraBackground() {
    if (running && video.videoWidth > 0 && video.videoHeight > 0) {
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

  function drawGridOverlay() {
    ctx.fillStyle = "rgba(40,40,40,0.40)";
    ctx.fillRect(offsetX, offsetY, gridW, gridH);

    ctx.strokeStyle = "rgba(230,230,230,0.7)";
    ctx.lineWidth = 2;
    for (let i = 0; i <= GAME_SIZE; i++) {
      ctx.beginPath();
      ctx.moveTo(offsetX + i * TILESIZE, offsetY);
      ctx.lineTo(offsetX + i * TILESIZE, offsetY + gridH);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(offsetX, offsetY + i * TILESIZE);
      ctx.lineTo(offsetX + gridW, offsetY + i * TILESIZE);
      ctx.stroke();
    }
  }

  function drawTiles() {
    ctx.font = "28px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    for (let r = 0; r < GAME_SIZE; r++) {
      for (let c = 0; c < GAME_SIZE; c++) {
        const val = board[r][c];
        if (val === 0) continue;

        const x = offsetX + c * TILESIZE;
        const y = offsetY + r * TILESIZE;

        const isTarget = targetPos && targetPos.r === r && targetPos.c === c;

        ctx.fillStyle = isTarget ? "rgba(255,255,0,0.85)" : "rgba(255,255,255,0.85)";
        ctx.fillRect(x + 6, y + 6, TILESIZE - 12, TILESIZE - 12);

        ctx.fillStyle = "black";
        ctx.fillText(String(val), x + TILESIZE / 2, y + TILESIZE / 2);
      }
    }
  }

  function strokeText(text, x, y, size = 22) {
  ctx.save();

  ctx.font = `${size}px Arial`;
  ctx.textAlign = "left";
  ctx.textBaseline = "top";

  // ✅ ασφαλές padding για να μην κόβεται το stroke σε καμία συσκευή
  const lineW = Math.max(6, Math.round(size * 0.28));
  ctx.lineWidth = lineW;
  ctx.lineJoin = "round";
  ctx.miterLimit = 2;

  const pad = lineW + 10;

  // ✅ clamp X μέσα στο canvas με βάση το πραγματικό πλάτος κειμένου
  const w = ctx.measureText(text).width;
  const safeX = Math.min(Math.max(x, pad), canvas.width - pad - w);

  // ✅ clamp Y (λίγο πιο κάτω γιατί μερικά fonts “βγαίνουν” προς τα πάνω)
  const safeY = Math.max(y, pad);

  ctx.strokeStyle = "rgba(0,0,0,0.75)";
  ctx.strokeText(text, safeX, safeY);

  ctx.fillStyle = "white";
  ctx.fillText(text, safeX, safeY);

  ctx.restore();
}

function drawHUD() {
  const goal = LEVEL_GOALS[level - 1];
  const targetVal = targetPos ? board[targetPos.r][targetPos.c] : "";

  // ✅ ξεκινά πιο μέσα, αλλά αν η γραμμή είναι πολύ μεγάλη θα “μαζευτεί” μόνη της
  const hudX = 44;
  const hudY = 18;

  strokeText(`Level: ${level}   Score: ${levelScore}/${goal}   Total: ${score}`, hudX, hudY, 22);
  strokeText(`${tr("moves")}: ${moves}   ${tr("time")}: ${nowSec().toFixed(1)}s`, hudX, hudY + 30, 22);
  strokeText(tr("move_tile_to_yellow", { tile: targetVal }), hudX, hudY + 60, 18);
}

  function drawHandMarker() {
    if (!running) return;
    if (!fingerX || !fingerY) return;
    ctx.fillStyle = pinch ? "lime" : "red";
    ctx.beginPath();
    ctx.arc(fingerX, fingerY, 10, 0, Math.PI * 2);
    ctx.fill();
  }

function drawInstructions() {
  // ✅ Χρήση πραγματικών διαστάσεων canvas
  const canvasWidth = canvas.width;
  const canvasHeight = canvas.height;
  
  ctx.fillStyle = "black";
  ctx.fillRect(0, 0, canvasWidth, canvasHeight);

  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  ctx.font = "24px Arial";
  ctx.fillStyle = "white";
  ctx.fillText(tr("welcome"), canvasWidth / 2, canvasHeight * 0.18);

  ctx.font = "18px Arial";
  const lines = [
    tr("instructions_title"),
    tr("inst_1"),
    tr("inst_2"),
    tr("goal_title"),
    tr("goal_desc"),
    "",
    tr("press_start")
  ];

  let y = canvasHeight * 0.28;
  const lineHeight = canvasHeight * 0.05;
  
  for (const line of lines) {
    ctx.fillText(line, canvasWidth / 2, y);
    y += lineHeight;
  }

  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
}

    let y = 170;
    for (const line of lines) {
      ctx.fillText(line, W / 2, y);
      y += 30;
    }

    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
  }

  function fitFontSize(text, maxWidth, startSize, minSize = 14, family = "Arial") {
  let size = startSize;
  while (size > minSize) {
    ctx.font = `${size}px ${family}`;
    if (ctx.measureText(text).width <= maxWidth) break;
    size -= 1;
  }
  return size;
}

function drawCenteredFit(text, cx, y, startSize, maxWidth, color = "white") {
  const size = fitFontSize(text, maxWidth, startSize);
  ctx.font = `${size}px Arial`;
  ctx.fillStyle = color;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, cx, y);
}


  function drawBetween() {
  ctx.fillStyle = "rgba(0,0,0,0.60)";
  ctx.fillRect(0, 0, W, H);

  const cx = offsetX + gridW / 2;
  const cy = offsetY + gridH / 2;

  const maxWidth = gridW - 24; // ✅ μέσα στο grid/frame

  drawCenteredFit(tr("level_passed", { level: level - 1 }), cx, cy - 20, 36, maxWidth, "white");
  drawCenteredFit(tr("pinch_continue"), cx, cy + 22, 18, maxWidth, "white");

  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
}

function drawDone() {
  ctx.fillStyle = "rgba(0,0,0,0.60)";
  ctx.fillRect(0, 0, W, H);

  const cx = offsetX + gridW / 2;
  const cy = offsetY + gridH / 2;

  const maxWidth = gridW - 24; // ✅ μέσα στο grid/frame

  drawCenteredFit(tr("exercise_done"), cx, cy - 22, 36, maxWidth, "rgb(0,255,0)");
  drawCenteredFit(tr("restart"), cx, cy + 22, 18, maxWidth, "white");

  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
}

  function draw() {
    ctx.clearRect(0, 0, W, H);

    if (gameState === "instructions") {
      drawInstructions();
      return;
    }

    drawCameraBackground();
    drawGridOverlay();
    drawTiles();
    drawHandMarker();
    drawHUD();

    if (gameState === "between") drawBetween();
    if (gameState === "done") drawDone();
  }

  // ---------- Success + levels ----------
  function playSuccess() {
    try {
      successAudio.currentTime = 0;
      successAudio.play();
    } catch {}
  }

  function onSuccessfulMove() {
    playSuccess();
    pickNewTarget();

    score += 1;
    levelScore += 1;

    const goal = LEVEL_GOALS[level - 1];
    if (levelScore >= goal) {
      if (level < 3) {
        level += 1;
        gameState = "between";
      } else {
        gameState = "done";
        sendStatsCompleted();
      }
    }
  }

  function tryMoveFromHand() {
    if (!running) return;
    if (gameState !== "playing") return;
    if (!pinch) return;

    const t = Date.now();
    if (t - lastMoveAt < 350) return;
    lastMoveAt = t;

    const pos = tileAtPixel(fingerX, fingerY);
    if (!pos) return;

    if (!targetPos) return;
    if (pos.r !== targetPos.r || pos.c !== targetPos.c) return;
    if (!isAdjacentToEmpty(pos)) return;

    swapWithEmpty(pos);
    onSuccessfulMove();
  }

  async function sendStatsCompleted() {
    if (sentOnce) return;
    sentOnce = true;

    const time_seconds = Math.round(nowSec());
    try {
      await fetch("/add_stat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          age,
          game_name: "Άσκηση 3",
          score,
          time_seconds,
          result: "completed"
        })
      });
    } catch (e) {
      console.warn("sendStats failed", e);
    }
  }

  function tick() {
    if (!running) return;

    // ✅ edge-trigger pinch to continue (release then pinch)
    const pinchDown = pinch && !prevPinch;

    if (gameState === "between" && pinchDown) {
      resetLevel();
    }

    draw();
    prevPinch = pinch;
    requestAnimationFrame(tick);
  }

  // ---------- MediaPipe ----------
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

  function dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }

  hands.onResults((res) => {
    const lms = res.multiHandLandmarks;
    if (!lms || lms.length === 0) {
      pinch = false;
      return;
    }

    const lm = lms[0];

    fingerX = (1 - lm[8].x) * W;
    fingerY = lm[8].y * H;

    const thumb = { x: (1 - lm[4].x) * W, y: lm[4].y * H };
    const index = { x: fingerX, y: fingerY };

    pinch = dist(thumb, index) < 35;

    tryMoveFromHand();
  });

  // ---------- Camera ----------
  async function startCamera() {
    try {
      statusEl.textContent = "📷 Ζητάω άδεια κάμερας...";
      video.setAttribute("playsinline", "");
      video.muted = true;
      video.setAttribute("muted", "");

      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false
      });

      video.srcObject = stream;
      await video.play();

      statusEl.textContent = "🎥 Κάμερα OK";
      processFrame();
    } catch (e) {
      console.error("startCamera failed:", e);
      statusEl.textContent = "❌ Δεν άνοιξε κάμερα (δες Console)";
      running = false;
      startBtn.disabled = false;
      restartBtn.disabled = false;
      stopBtn.disabled = true;
    }
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
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
    video.srcObject = null;
  }

  // ---------- Buttons ----------
  startBtn.onclick = async () => {
    // unlock audio
    try {
      await successAudio.play();
      successAudio.pause();
      successAudio.currentTime = 0;
    } catch {}

    resetGameAll();
    running = true;

    startBtn.disabled = true;
    restartBtn.disabled = true;
    stopBtn.disabled = false;

    await startCamera();
    requestAnimationFrame(tick);
  };

  restartBtn.onclick = () => startBtn.onclick();

  stopBtn.onclick = () => {
    running = false;
    stopCamera();

    startBtn.disabled = false;
    restartBtn.disabled = false;
    stopBtn.disabled = true;

    gameState = "instructions";
    statusEl.textContent = "⏹️ Σταμάτησε";
    draw();
  };

  // init
  gameState = "instructions";
  draw();
})(); 
