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

  // User/session data passed from Flask
  const username = document.body.dataset.username || "Guest";
  const age = parseInt(document.body.dataset.age || "0", 10);

  // ==============================
  // i18n (translations injected via HTML)
  // ==============================
  const i18nEl = document.getElementById("i18n");
  const TT = i18nEl ? JSON.parse(i18nEl.textContent || "{}") : {};

  // Translation helper with variable replacement
  const tr = (key, vars = {}) => {
    let s = TT[key] || key;
    for (const [k, v] of Object.entries(vars)) {
      s = s.replaceAll(`{${k}}`, String(v));
    }
    return s;
  };

  // ==============================
  // Canvas & grid geometry
  // ==============================
  const W = canvas.width;
  const H = canvas.height;

  const GAME_SIZE = 4;        // 4x4 sliding puzzle
  const TILESIZE = 100;       // tile size in pixels

  const gridW = GAME_SIZE * TILESIZE;
  const gridH = GAME_SIZE * TILESIZE;

  // Center grid inside canvas
  const offsetX = Math.floor((W - gridW) / 2);
  const offsetY = Math.floor((H - gridH) / 4);

  // Score targets per level
  const LEVEL_GOALS = [5, 10, 15];

  // ==============================
  // Game state
  // ==============================
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

  // instructions | playing | between | done
  let gameState = "instructions";

  // ==============================
  // Hand / gesture state
  // ==============================
  let pinch = false;
  let prevPinch = false;   // edge-trigger detection
  let fingerX = 0;
  let fingerY = 0;
  let lastMoveAt = 0;      // debounce timer

  // ==============================
  // Sound (played on successful move)
  // ==============================
  const successAudio = new Audio("/assets/third_game/success.wav");
  successAudio.preload = "auto";

  // ==============================
  // Utility helpers
  // ==============================
  function nowSec() {
    return (Date.now() - startTime) / 1000;
  }

  function clone2D(a) {
    return a.map(r => r.slice());
  }

  // ==============================
  // Board creation & logic
  // ==============================
  function makeSolvedBoard() {
    const b = [];
    let v = 1;
    for (let r = 0; r < GAME_SIZE; r++) {
      b.push([]);
      for (let c = 0; c < GAME_SIZE; c++) {
        b[r][c] = (r === GAME_SIZE - 1 && c === GAME_SIZE - 1) ? 0 : v++;
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

  // Adjacent positions (up/down/left/right)
  function neighbors(pos) {
    const out = [];
    const { r, c } = pos;
    if (c > 0) out.push({ r, c: c - 1 });
    if (c < GAME_SIZE - 1) out.push({ r, c: c + 1 });
    if (r > 0) out.push({ r: r - 1, c });
    if (r < GAME_SIZE - 1) out.push({ r: r + 1, c });
    return out;
  }

  // Shuffle using valid moves only (always solvable)
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

  // Pick a random tile adjacent to empty as the target
  function pickNewTarget() {
    const empty = findEmpty();
    const opts = neighbors(empty).filter(p => board[p.r][p.c] !== 0);
    targetPos = opts.length ? opts[Math.floor(Math.random() * opts.length)] : null;
  }

  // ==============================
  // Level & game resets
  // ==============================
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

  // ==============================
  // Coordinate helpers
  // ==============================
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
    moves++;
  }

  // ==============================
  // Rendering helpers
  // ==============================
  // (Camera background, grid, tiles, HUD, overlays, etc.)
  // These functions ONLY draw – no game logic inside.

  // ... (drawing functions unchanged, comments omitted for brevity)

  // ==============================
  // Game progression
  // ==============================
  function playSuccess() {
    try {
      successAudio.currentTime = 0;
      successAudio.play();
    } catch {}
  }

  function onSuccessfulMove() {
    playSuccess();
    pickNewTarget();

    score++;
    levelScore++;

    const goal = LEVEL_GOALS[level - 1];
    if (levelScore >= goal) {
      if (level < 3) {
        level++;
        gameState = "between";
      } else {
        gameState = "done";
        sendStatsCompleted();
      }
    }
  }

  // ==============================
  // Gesture-based movement
  // ==============================
  function tryMoveFromHand() {
    if (!running || gameState !== "playing" || !pinch) return;

    // Debounce moves
    const t = Date.now();
    if (t - lastMoveAt < 350) return;
    lastMoveAt = t;

    const pos = tileAtPixel(fingerX, fingerY);
    if (!pos || !targetPos) return;
    if (pos.r !== targetPos.r || pos.c !== targetPos.c) return;
    if (!isAdjacentToEmpty(pos)) return;

    swapWithEmpty(pos);
    onSuccessfulMove();
  }

  // ==============================
  // Stats submission (once)
  // ==============================
  async function sendStatsCompleted() {
    if (sentOnce) return;
    sentOnce = true;

    try {
      await fetch("/add_stat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          age,
          game_name: "Άσκηση 3",
          score,
          time_seconds: Math.round(nowSec()),
          result: "completed"
        })
      });
    } catch (e) {
      console.warn("sendStats failed", e);
    }
  }

  // ==============================
  // Main loop
  // ==============================
  function tick() {
    if (!running) return;

    // Edge-trigger pinch to continue to next level
    const pinchDown = pinch && !prevPinch;
    if (gameState === "between" && pinchDown) resetLevel();

    draw();
    prevPinch = pinch;
    requestAnimationFrame(tick);
  }

  // ==============================
  // MediaPipe Hands setup
  // ==============================
  if (typeof Hands === "undefined") {
    statusEl.textContent = "❌ MediaPipe Hands not loaded";
    return;
  }

  const hands = new Hands({
    locateFile: (file) =>
      `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1646424915/${file}`,
  });

  hands.setOptions({
    maxNumHands: 1,
    modelComplexity: 0,
    minDetectionConfidence: 0.5,
    minTrackingConfidence: 0.5,
  });

  function dist(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  // Process hand landmarks and detect pinch
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
    pinch = dist(thumb, { x: fingerX, y: fingerY }) < 35;

    tryMoveFromHand();
  });

  // ==============================
  // Camera handling
  // ==============================
  async function startCamera() {
    try {
      video.setAttribute("playsinline", "");
      video.muted = true;

      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false
      });

      video.srcObject = stream;
      await video.play();
      processFrame();
    } catch (e) {
      statusEl.textContent = "❌ Camera failed";
      running = false;
    }
  }

  async function processFrame() {
    if (!running) return;
    await hands.send({ image: video });
    requestAnimationFrame(processFrame);
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
    video.srcObject = null;
  }

  // ==============================
  // Buttons
  // ==============================
  startBtn.onclick = async () => {
    // Unlock audio on user gesture
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
    draw();
  };

  // Initial draw
  gameState = "instructions";
  draw();
})();
