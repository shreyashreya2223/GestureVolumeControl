document.addEventListener("DOMContentLoaded", () => {

  /* ================= THEME TOGGLE ================= */

  const body = document.body;
  const themeToggle = document.getElementById("themeToggle");

  const savedTheme = localStorage.getItem("theme") || "dark";
  body.className = savedTheme;
  themeToggle.checked = savedTheme === "dark";

  themeToggle.addEventListener("change", () => {
    if (themeToggle.checked) {
      body.className = "dark";
      localStorage.setItem("theme", "dark");
    } else {
      body.className = "light";
      localStorage.setItem("theme", "light");
    }
  });

  /* ================= DETECTION TOGGLE ================= */

  const detectToggle = document.getElementById("detectToggle");

  detectToggle.addEventListener("change", async () => {
    const res = await fetch("/toggle_detection", { method: "POST" });
    const data = await res.json();
    detectToggle.checked = data.enabled;
  });

  /* ================= GRAPH ================= */

  const canvas = document.getElementById("volumeChart");
  const ctx = canvas.getContext("2d");

  let history = [];
  const MAX_POINTS = 60;

  function drawGraph() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Grid
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = (i / 5) * canvas.height;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    // Volume line
    ctx.beginPath();
    ctx.strokeStyle = "#22c55e";
    ctx.lineWidth = 2;

    history.forEach((v, i) => {
      const x = (i / (MAX_POINTS - 1)) * canvas.width;
      const y = canvas.height - (v / 100) * canvas.height;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.stroke();
  }

  /* ================= UPDATE LOOP ================= */

  async function update() {
    const res = await fetch("/status");
    const data = await res.json();

    // Volume + bar
    document.getElementById("vol").innerText =
      `Volume: ${data.volume}%`;

    document.getElementById("fill").style.width =
      data.volume + "%";

    // Status text
    const statusEl = document.getElementById("status");

    if (!data.enabled) {
      statusEl.innerText = "Status: Detection Paused";
      statusEl.className = "waiting";
      return; // 🔴 stop graph update when paused
    }

    statusEl.innerText = `Status: ${data.status}`;
    statusEl.className =
      data.status === "Hand Detected" ? "detected" : "waiting";

    // FPS
    document.getElementById("fps").innerText =
      `FPS: ${data.fps}`;

    // Graph update only if detection ON
    history.push(data.volume);
    if (history.length > MAX_POINTS) history.shift();
    drawGraph();
  }

  /* ================= CALIBRATION ================= */

  async function calibrateMin() {
    if (!detectToggle.checked) {
      alert("Enable detection first");
      return;
    }
    await fetch("/calibrate/min", { method: "POST" });
    alert("MIN calibration set");
  }

  async function calibrateMax() {
    if (!detectToggle.checked) {
      alert("Enable detection first");
      return;
    }
    await fetch("/calibrate/max", { method: "POST" });
    alert("MAX calibration set");
  }

  // Expose to HTML buttons
  window.calibrateMin = calibrateMin;
  window.calibrateMax = calibrateMax;

  /* ================= START ================= */

  setInterval(update, 200);

});
