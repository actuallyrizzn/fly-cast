(function () {
  const ARMS = ["fly", "scramble", "nofly", "fly_shuffled", "nofly_shuffled", "tfidf"];

  function el(id) {
    return document.getElementById(id);
  }

  function drawBars(arms) {
    const host = el("bars");
    host.innerHTML = "";
    if (!arms) return;
    ARMS.forEach(function (name) {
      const pack = arms[name];
      if (!pack || !pack.acc) return;
      const mean = pack.acc[0];
      const lo = pack.acc[1];
      const hi = pack.acc[2];
      const row = document.createElement("div");
      row.className = "arm-row";
      const label = document.createElement("div");
      label.textContent = name;
      const track = document.createElement("div");
      track.className = "arm-track";
      const fill = document.createElement("div");
      fill.className = "arm-fill";
      fill.style.left = "0";
      fill.style.width = Math.max(0, Math.min(1, mean)) * 100 + "%";
      const whisker = document.createElement("div");
      whisker.className = "arm-whisker";
      whisker.style.left = Math.max(0, Math.min(1, lo)) * 100 + "%";
      whisker.style.width = Math.max(0, (Math.min(1, hi) - Math.max(0, lo)) * 100) + "%";
      track.appendChild(fill);
      track.appendChild(whisker);
      const value = document.createElement("div");
      value.textContent = mean.toFixed(3);
      row.appendChild(label);
      row.appendChild(track);
      row.appendChild(value);
      host.appendChild(row);
    });
  }

  function drawConfusion(conf) {
    const canvas = el("confusion");
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!conf || !conf.matrix) {
      ctx.fillStyle = "#9a9690";
      ctx.fillText("no confusion yet", 20, 40);
      return;
    }
    const matrix = conf.matrix;
    const labels = conf.labels || matrix.map(function (_, i) { return String(i); });
    const n = matrix.length;
    const cell = Math.min(48, Math.floor(320 / Math.max(n, 1)));
    const ox = 80;
    const oy = 40;
    for (let r = 0; r < n; r++) {
      const rowSum = matrix[r].reduce(function (a, b) { return a + b; }, 0) || 1;
      for (let c = 0; c < n; c++) {
        const v = matrix[r][c] / rowSum;
        ctx.fillStyle = "rgba(74,144,164," + (0.15 + 0.85 * v).toFixed(2) + ")";
        ctx.fillRect(ox + c * cell, oy + r * cell, cell - 2, cell - 2);
        ctx.fillStyle = "#e8e6e3";
        ctx.font = "14px sans-serif";
        ctx.fillText(String(matrix[r][c]), ox + c * cell + 8, oy + r * cell + cell / 2);
      }
      ctx.fillStyle = "#9a9690";
      ctx.fillText(String(labels[r]), 8, oy + r * cell + cell / 2);
    }
    for (let c = 0; c < n; c++) {
      ctx.fillStyle = "#9a9690";
      ctx.fillText(String(labels[c]), ox + c * cell + 4, 24);
    }
  }

  function drawReliability(rel) {
    const canvas = el("reliability");
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    const pad = 40;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = "#444";
    ctx.beginPath();
    ctx.moveTo(pad, h - pad);
    ctx.lineTo(w - pad, h - pad);
    ctx.lineTo(w - pad, pad);
    ctx.stroke();
    ctx.strokeStyle = "#666";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(pad, h - pad);
    ctx.lineTo(w - pad, pad);
    ctx.stroke();
    ctx.setLineDash([]);
    if (!rel) return;
    const colors = { fly: "#4a90a4", nofly: "#c9a227", scramble: "#8a6", tfidf: "#a66" };
    Object.keys(rel).forEach(function (arm) {
      const bins = rel[arm];
      if (!bins || !bins.length) return;
      ctx.strokeStyle = colors[arm] || "#ccc";
      ctx.beginPath();
      bins.forEach(function (bin, i) {
        if (!bin[2]) return;
        const x = pad + bin[3] * (w - 2 * pad);
        const y = h - pad - bin[4] * (h - 2 * pad);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });
  }

  function drawLatency(lat) {
    const host = el("latency");
    host.innerHTML = "";
    if (!lat) return;
    Object.keys(lat).forEach(function (name) {
      if (typeof lat[name] !== "number") return;
      const item = document.createElement("div");
      item.className = "lat-item";
      item.innerHTML = "<span>" + name + "</span><strong>" + lat[name].toFixed(2) + " ms</strong>";
      host.appendChild(item);
    });
  }

  function drawCriteria(criteria, pass) {
    const host = el("criteria");
    host.innerHTML = "";
    ["c1", "c2", "c3"].forEach(function (key) {
      const box = document.createElement("div");
      const val = criteria ? criteria[key] : null;
      box.className = "crit " + (val === true ? "true" : val === false ? "false" : "null");
      box.textContent = key.toUpperCase();
      host.appendChild(box);
    });
    const word = document.createElement("div");
    word.id = "pass-word";
    if (pass === true) word.textContent = "PASS";
    else if (pass === false) word.textContent = "FAIL";
    else word.textContent = "PENDING";
    host.appendChild(word);
  }

  function render(state) {
    el("title").textContent = "jevlab — " + (state.task || "?");
    el("phase").textContent = state.phase || "pending";
    const prog = state.progress || {};
    const done = prog.done || 0;
    const total = prog.total || 0;
    el("progress-bar").style.width = (total ? (100 * done / total) : 0) + "%";
    const now = state.now || {};
    el("elapsed").textContent = (now.arm || "") + " " + (now.step || "") +
      (now.elapsed_s != null ? (" · " + Number(now.elapsed_s).toFixed(1) + "s") : "");
    drawBars(state.arms);
    drawConfusion(state.confusion);
    drawReliability(state.reliability);
    drawLatency(state.latency_ms);
    drawCriteria(state.criteria, state.pass);
  }

  function tick() {
    fetch("./state.json", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(render)
      .catch(function () { /* keep last */ });
  }

  tick();
  setInterval(tick, 2000);
})();
