// ===== Snake Game Logic =====

const canvas = document.getElementById('game-canvas');
const ctx = canvas.getContext('2d');

// Grid configuration
const GRID_SIZE = 20;          // 20x20 cells
const CELL_SIZE = canvas.width / GRID_SIZE; // 20px per cell

// Game state
let snake = [];
let direction = { x: 1, y: 0 };
let nextDirection = { x: 1, y: 0 };
let food = null;
let score = 0;
let highScore = parseInt(localStorage.getItem('snakeHighScore')) || 0;
let gameRunning = false;
let gamePaused = false;
let gameOver = false;
let gameInterval = null;
const GAME_SPEED = 120; // ms per tick

// DOM elements
const scoreEl = document.getElementById('score');
const highScoreEl = document.getElementById('high-score');
const finalScoreEl = document.getElementById('final-score');
const gameOverEl = document.getElementById('game-over');
const restartBtn = document.getElementById('restart-btn');
const soundBtn = document.getElementById('sound-btn');
const musicBtn = document.getElementById('music-btn');

// Initialize high score display
highScoreEl.textContent = highScore;

// ===== Audio Engine (Web Audio API, no external files needed) =====

let soundEnabled = localStorage.getItem('snakeSoundEnabled') !== 'false'; // default true
let musicEnabled = localStorage.getItem('snakeMusicEnabled') === 'true'; // default false
let audioCtx = null;
let musicTimer = null;
let musicStep = 0;

// Simple looping melody (note frequencies in Hz, null = rest)
const MUSIC_NOTES = [
  392.00, null, 440.00, null, 523.25, null, 440.00, null,
  392.00, null, 349.23, null, 392.00, null, null, null
];
const MUSIC_NOTE_DURATION = 220; // ms per step

function getAudioContext() {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContextClass();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

function playTone(freq, duration, type = 'sine', volume = 0.15, startDelay = 0) {
  if (!soundEnabled && type !== '__music__') return;
  const ctxA = getAudioContext();
  const osc = ctxA.createOscillator();
  const gain = ctxA.createGain();
  osc.type = type === '__music__' ? 'triangle' : type;
  osc.frequency.value = freq;
  const startTime = ctxA.currentTime + startDelay;
  gain.gain.setValueAtTime(volume, startTime);
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
  osc.connect(gain);
  gain.connect(ctxA.destination);
  osc.start(startTime);
  osc.stop(startTime + duration);
}

function playEatSound() {
  if (!soundEnabled) return;
  playTone(523.25, 0.08, 'square', 0.12);
  playTone(659.25, 0.1, 'square', 0.1, 0.05);
}

function playGameOverSound() {
  if (!soundEnabled) return;
  playTone(392.00, 0.15, 'sawtooth', 0.12, 0);
  playTone(329.63, 0.15, 'sawtooth', 0.12, 0.15);
  playTone(261.63, 0.3, 'sawtooth', 0.12, 0.3);
}

function musicTick() {
  const note = MUSIC_NOTES[musicStep % MUSIC_NOTES.length];
  if (note) {
    playTone(note, MUSIC_NOTE_DURATION / 1000 * 0.9, '__music__', 0.05);
  }
  musicStep++;
}

function startMusic() {
  if (!musicEnabled || musicTimer) return;
  getAudioContext();
  musicStep = 0;
  musicTick();
  musicTimer = setInterval(musicTick, MUSIC_NOTE_DURATION);
}

function stopMusic() {
  if (musicTimer) {
    clearInterval(musicTimer);
    musicTimer = null;
  }
}

function updateAudioButtons() {
  soundBtn.classList.toggle('active', soundEnabled);
  soundBtn.textContent = soundEnabled ? '🔊 SFX' : '🔇 SFX';
  musicBtn.classList.toggle('active', musicEnabled);
  musicBtn.textContent = musicEnabled ? '🎵 Music' : '🎵 Music Off';
}

soundBtn.addEventListener('click', () => {
  soundEnabled = !soundEnabled;
  localStorage.setItem('snakeSoundEnabled', soundEnabled);
  updateAudioButtons();
  if (soundEnabled) {
    getAudioContext();
    playTone(523.25, 0.08, 'square', 0.1);
  }
});

musicBtn.addEventListener('click', () => {
  musicEnabled = !musicEnabled;
  localStorage.setItem('snakeMusicEnabled', musicEnabled);
  updateAudioButtons();
  if (musicEnabled && gameRunning && !gamePaused && !gameOver) {
    startMusic();
  } else {
    stopMusic();
  }
});

updateAudioButtons();

// ===== Helper Functions =====

function resetGame() {
  // Start snake in the middle, moving right
  const startX = Math.floor(GRID_SIZE / 2);
  const startY = Math.floor(GRID_SIZE / 2);
  snake = [
    { x: startX, y: startY },
    { x: startX - 1, y: startY },
    { x: startX - 2, y: startY }
  ];
  direction = { x: 1, y: 0 };
  nextDirection = { x: 1, y: 0 };
  score = 0;
  gameOver = false;
  gamePaused = false;
  scoreEl.textContent = score;
  gameOverEl.classList.add('hidden');
  spawnFood();
  draw();
}

function spawnFood() {
  // Find a random empty cell not occupied by the snake
  let newFood;
  do {
    newFood = {
      x: Math.floor(Math.random() * GRID_SIZE),
      y: Math.floor(Math.random() * GRID_SIZE)
    };
  } while (snake.some(segment => segment.x === newFood.x && segment.y === newFood.y));
  food = newFood;
}

function startGame() {
  if (gameInterval) {
    clearInterval(gameInterval);
  }
  resetGame();
  gameRunning = true;
  gameInterval = setInterval(gameTick, GAME_SPEED);
  if (musicEnabled) {
    startMusic();
  }
}

function gameTick() {
  if (gamePaused || gameOver) return;

  // Apply the queued direction (prevents double-turn in one tick)
  direction = { ...nextDirection };

  // Calculate new head position
  const head = snake[0];
  const newHead = {
    x: head.x + direction.x,
    y: head.y + direction.y
  };

  // Check wall collision
  if (
    newHead.x < 0 || newHead.x >= GRID_SIZE ||
    newHead.y < 0 || newHead.y >= GRID_SIZE
  ) {
    endGame();
    return;
  }

  // Check self collision (excluding the tail which will move)
  const willEat = food && newHead.x === food.x && newHead.y === food.y;
  const bodyToCheck = willEat ? snake : snake.slice(0, -1);
  if (bodyToCheck.some(segment => segment.x === newHead.x && segment.y === newHead.y)) {
    endGame();
    return;
  }

  // Move snake
  snake.unshift(newHead);

  if (willEat) {
    // Grow: don't remove the tail
    score += 10;
    scoreEl.textContent = score;
    spawnFood();
    playEatSound();
  } else {
    // Normal move: remove the tail
    snake.pop();
  }

  draw();
}

function endGame() {
  gameOver = true;
  gameRunning = false;
  clearInterval(gameInterval);
  gameInterval = null;
  stopMusic();
  playGameOverSound();

  // Update high score
  if (score > highScore) {
    highScore = score;
    localStorage.setItem('snakeHighScore', highScore);
    highScoreEl.textContent = highScore;
  }

  finalScoreEl.textContent = score;
  gameOverEl.classList.remove('hidden');
}

// ===== Rendering =====

function draw() {
  // Clear canvas
  ctx.fillStyle = '#0a0a1a';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Draw subtle grid lines
  ctx.strokeStyle = 'rgba(78, 204, 163, 0.08)';
  ctx.lineWidth = 1;
  for (let i = 1; i < GRID_SIZE; i++) {
    ctx.beginPath();
    ctx.moveTo(i * CELL_SIZE, 0);
    ctx.lineTo(i * CELL_SIZE, canvas.height);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, i * CELL_SIZE);
    ctx.lineTo(canvas.width, i * CELL_SIZE);
    ctx.stroke();
  }

  // Draw food
  if (food) {
    const fx = food.x * CELL_SIZE;
    const fy = food.y * CELL_SIZE;
    ctx.fillStyle = '#e94560';
    ctx.beginPath();
    ctx.arc(fx + CELL_SIZE / 2, fy + CELL_SIZE / 2, CELL_SIZE / 2 - 2, 0, Math.PI * 2);
    ctx.fill();
    // Food glow
    ctx.shadowColor = '#e94560';
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(fx + CELL_SIZE / 2, fy + CELL_SIZE / 2, CELL_SIZE / 2 - 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
  }

  // Draw snake
  snake.forEach((segment, index) => {
    const x = segment.x * CELL_SIZE;
    const y = segment.y * CELL_SIZE;
    const padding = index === 0 ? 1 : 2;

    if (index === 0) {
      // Head
      ctx.fillStyle = '#4ecca3';
      ctx.shadowColor = '#4ecca3';
      ctx.shadowBlur = 8;
      ctx.fillRect(x + padding, y + padding, CELL_SIZE - padding * 2, CELL_SIZE - padding * 2);
      ctx.shadowBlur = 0;

      // Eyes
      ctx.fillStyle = '#0a0a1a';
      const eyeSize = 3;
      const eyeOffset = 5;
      if (direction.x === 1) {
        ctx.fillRect(x + CELL_SIZE - eyeOffset - eyeSize, y + eyeOffset, eyeSize, eyeSize);
        ctx.fillRect(x + CELL_SIZE - eyeOffset - eyeSize, y + CELL_SIZE - eyeOffset - eyeSize, eyeSize, eyeSize);
      } else if (direction.x === -1) {
        ctx.fillRect(x + eyeOffset, y + eyeOffset, eyeSize, eyeSize);
        ctx.fillRect(x + eyeOffset, y + CELL_SIZE - eyeOffset - eyeSize, eyeSize, eyeSize);
      } else if (direction.y === 1) {
        ctx.fillRect(x + eyeOffset, y + CELL_SIZE - eyeOffset - eyeSize, eyeSize, eyeSize);
        ctx.fillRect(x + CELL_SIZE - eyeOffset - eyeSize, y + CELL_SIZE - eyeOffset - eyeSize, eyeSize, eyeSize);
      } else {
        ctx.fillRect(x + eyeOffset, y + eyeOffset, eyeSize, eyeSize);
        ctx.fillRect(x + CELL_SIZE - eyeOffset - eyeSize, y + eyeOffset, eyeSize, eyeSize);
      }
    } else {
      // Body — gradient from head to tail
      const ratio = index / snake.length;
      const r = Math.round(78 + (30 - 78) * ratio);
      const g = Math.round(204 + (150 - 204) * ratio);
      const b = Math.round(163 + (120 - 163) * ratio);
      ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
      ctx.fillRect(x + padding, y + padding, CELL_SIZE - padding * 2, CELL_SIZE - padding * 2);
    }
  });
}

// ===== Input Handling =====

const directionMap = {
  ArrowUp: { x: 0, y: -1 },
  ArrowDown: { x: 0, y: 1 },
  ArrowLeft: { x: -1, y: 0 },
  ArrowRight: { x: 1, y: 0 },
  w: { x: 0, y: -1 },
  s: { x: 0, y: 1 },
  a: { x: -1, y: 0 },
  d: { x: 1, y: 0 },
  W: { x: 0, y: -1 },
  S: { x: 0, y: 1 },
  A: { x: -1, y: 0 },
  D: { x: 1, y: 0 }
};

document.addEventListener('keydown', (e) => {
  // Prevent arrow keys / space from scrolling the page
  if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) {
    e.preventDefault();
  }

  // Space toggles pause
  if (e.key === ' ') {
    if (gameRunning && !gameOver) {
      gamePaused = !gamePaused;
      if (gamePaused) {
        stopMusic();
      } else if (musicEnabled) {
        startMusic();
      }
    }
    return;
  }

  // Direction change
  const newDir = directionMap[e.key];
  if (newDir) {
    // Prevent reversing direction (can't go directly backwards)
    if (newDir.x === -direction.x && newDir.y === -direction.y) {
      return;
    }
    // Queue the direction; applied on next tick
    nextDirection = newDir;
  }
});

// ===== Restart Button =====

restartBtn.addEventListener('click', () => {
  startGame();
});

// ===== Start the game =====

startGame();