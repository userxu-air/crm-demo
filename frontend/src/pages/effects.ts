/**
 * 登录页背景特效 —— 照搬自官网管理后台 admin.html
 * 1) initGlitchBg   字符雨 glitch 背景层
 * 2) initSwarmCursor Perlin 噪声粒子群跟随鼠标层
 * 原逻辑/参数保留，配色抽成 palette（深色=原版 / 浅色=light 适配），返回清理函数。
 */

export interface FxPalette {
  bg: string;
  charColor: string;
  charHighlight: string;
  charAlphaBase: number;
  charAlphaRange: number;
  glitchHighlightAlpha: number;
  scanlineColor: string;
  particleColor: string;
  trailColor: string;
}

/** 原版深色（admin.html） */
export const DARK_PALETTE: FxPalette = {
  bg: "#04070b",
  charColor: "#1fb6c9",
  charHighlight: "#7ffcff",
  charAlphaBase: 0.26,
  charAlphaRange: 0.25,
  glitchHighlightAlpha: 1,
  scanlineColor: "rgba(34,211,238,0.22)",
  particleColor: "rgba(150,240,255,0.7)",
  trailColor: "rgba(34,211,238,0.22)",
};

/** 浅色版：淡青蓝白底，深青粒子与水印感字符雨 */
export const LIGHT_PALETTE: FxPalette = {
  bg: "#eef5fa",
  charColor: "#38bdf8",
  charHighlight: "#0369a1",
  charAlphaBase: 0.08,
  charAlphaRange: 0.1,
  glitchHighlightAlpha: 0.45,
  scanlineColor: "rgba(14,165,233,0.1)",
  particleColor: "rgba(2,132,199,0.78)",
  trailColor: "rgba(14,165,233,0.2)",
};

export function initGlitchBg(c: HTMLCanvasElement, palette: FxPalette = DARK_PALETTE): () => void {
  const ctx = c.getContext("2d")!;
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<>[]{}/$#%&*+=?!";
  const fs = 13,
    gap = 2;
  let cols = 0,
    rows = 0,
    grid: string[] = [];

  function resize() {
    c.width = window.innerWidth;
    c.height = window.innerHeight;
    cols = Math.ceil(c.width / (fs + gap));
    rows = Math.ceil(c.height / (fs + gap));
    grid = [];
    for (let i = 0; i < cols * rows; i++)
      grid.push(chars[Math.floor(Math.random() * chars.length)]);
  }
  resize();
  window.addEventListener("resize", resize);

  function draw() {
    ctx.fillStyle = palette.bg;
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.font = fs + 'px "Courier New", monospace';
    for (let i = 0; i < cols; i++) {
      for (let j = 0; j < rows; j++) {
        const idx = j * cols + i;
        if (Math.random() < 0.015) grid[idx] = chars[Math.floor(Math.random() * chars.length)];
        const glitch = Math.random() < 0.008;
        ctx.globalAlpha = glitch
          ? palette.glitchHighlightAlpha
          : palette.charAlphaBase + Math.random() * palette.charAlphaRange;
        ctx.fillStyle = glitch ? palette.charHighlight : palette.charColor;
        ctx.fillText(grid[idx], i * (fs + gap), j * (fs + gap));
      }
    }
    ctx.globalAlpha = 1;
    if (Math.random() < 0.05) {
      const gy = Math.random() * c.height,
        gh = Math.random() * 6 + 2;
      ctx.fillStyle = palette.scanlineColor;
      ctx.fillRect(0, gy, c.width, gh);
    }
  }
  const timer = window.setInterval(draw, 70);

  return () => {
    window.clearInterval(timer);
    window.removeEventListener("resize", resize);
  };
}

export function initSwarmCursor(
  canvas: HTMLCanvasElement,
  palette: FxPalette = DARK_PALETTE
): () => void {
  const ctx = canvas.getContext("2d")!;

  const MAX = 36,
    size = 9,
    spread = 210,
    separation = 0.18;
  const speed = 2.5,
    wander = 0.3,
    trail = 0.75,
    opacity = 0.9;

  let W = 1,
    H = 1,
    dpr = 1;
  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener("resize", resize);

  // —— 3D Perlin 噪声 ——
  const perm = (() => {
    const src = new Uint8Array(256);
    for (let i = 0; i < 256; i++) src[i] = i;
    for (let j = 255; j > 0; j--) {
      const k = (Math.random() * (j + 1)) | 0;
      const t = src[j];
      src[j] = src[k];
      src[k] = t;
    }
    const p = new Uint16Array(512);
    for (let m = 0; m < 512; m++) p[m] = src[m & 255];
    return p;
  })();
  function smoothFade(t: number) {
    return t * t * t * (t * (t * 6 - 15) + 10);
  }
  function gradDot(h: number, x: number, y: number, z: number) {
    const u = h < 8 ? x : y;
    const v = h < 4 ? y : h === 12 || h === 14 ? x : z;
    return ((h & 1) === 0 ? u : -u) + ((h & 2) === 0 ? v : -v);
  }
  function noise3(x: number, y: number, z: number) {
    const fx = Math.floor(x),
      fy = Math.floor(y),
      fz = Math.floor(z);
    const X = fx & 255,
      Y = fy & 255,
      Z = fz & 255;
    const rx = x - fx,
      ry = y - fy,
      rz = z - fz;
    const u = smoothFade(rx),
      v = smoothFade(ry),
      w = smoothFade(rz);
    const A = perm[X] + Y,
      AA = perm[A & 511] + Z,
      AB = perm[(A + 1) & 511] + Z;
    const B = perm[(X + 1) & 511] + Y,
      BA = perm[B & 511] + Z,
      BB = perm[(B + 1) & 511] + Z;
    const g000 = gradDot(perm[AA & 511] & 15, rx, ry, rz);
    const g100 = gradDot(perm[BA & 511] & 15, rx - 1, ry, rz);
    const g010 = gradDot(perm[AB & 511] & 15, rx, ry - 1, rz);
    const g110 = gradDot(perm[BB & 511] & 15, rx - 1, ry - 1, rz);
    const g001 = gradDot(perm[(AA + 1) & 511] & 15, rx, ry, rz - 1);
    const g101 = gradDot(perm[(BA + 1) & 511] & 15, rx - 1, ry, rz - 1);
    const g011 = gradDot(perm[(AB + 1) & 511] & 15, rx, ry - 1, rz - 1);
    const g111 = gradDot(perm[(BB + 1) & 511] & 15, rx - 1, ry - 1, rz - 1);
    const x00 = g000 + u * (g100 - g000);
    const x10 = g010 + u * (g110 - g010);
    const x01 = g001 + u * (g101 - g001);
    const x11 = g011 + u * (g111 - g011);
    const y0 = x00 + v * (x10 - x00);
    const y1 = x01 + v * (x11 - x01);
    return y0 + w * (y1 - y0);
  }

  // —— 粒子 ——
  const px = new Float32Array(MAX),
    py = new Float32Array(MAX);
  const vx = new Float32Array(MAX),
    vy = new Float32Array(MAX);
  const scale = new Float32Array(MAX),
    agility = new Float32Array(MAX);
  const handed = new Float32Array(MAX),
    noiseX = new Float32Array(MAX),
    noiseY = new Float32Array(MAX);

  function spawn(i: number, ox: number, oy: number) {
    const a = Math.random() * Math.PI * 2;
    const r = 40 + Math.random() * 140;
    px[i] = ox + Math.cos(a) * r;
    py[i] = oy + Math.sin(a) * r;
    vx[i] = Math.cos(a) * 60;
    vy[i] = Math.sin(a) * 60;
  }
  for (let i = 0; i < MAX; i++) {
    spawn(i, W * 0.5, H * 0.5);
    scale[i] = 0.65 + Math.random() * 0.6;
    agility[i] = 0.75 + Math.random() * 0.5;
    handed[i] = Math.random() < 0.5 ? -1 : 1;
    noiseX[i] = Math.random() * 260;
    noiseY[i] = Math.random() * 260;
  }

  // —— 拖尾历史 ——
  const HISTORY = 36;
  const histX = new Float32Array(HISTORY * MAX),
    histY = new Float32Array(HISTORY * MAX);
  const histT = new Float32Array(HISTORY);
  let histHead = 0,
    histLen = 0,
    lastSample = -1;

  // —— 鼠标 ——
  const cursor = { x: W * 0.5, y: H * 0.5, has: false };
  function onMove(e: PointerEvent) {
    cursor.x = e.clientX;
    cursor.y = e.clientY;
    cursor.has = true;
  }
  function onLeave() {
    cursor.has = false;
  }
  document.addEventListener("pointermove", onMove, { passive: true });
  document.addEventListener("pointerleave", onLeave);

  // —— 预渲染发光光斑（青色）——
  const spot = document.createElement("canvas");
  spot.width = spot.height = 64;
  const sctx = spot.getContext("2d")!;
  const g = sctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, "rgba(140,245,255,1)");
  g.addColorStop(0.3, "rgba(34,211,238,0.5)");
  g.addColorStop(1, "rgba(34,211,238,0)");
  sctx.fillStyle = g;
  sctx.fillRect(0, 0, 64, 64);

  let last = performance.now();
  let raf = 0;
  function frame(now: number) {
    raf = requestAnimationFrame(frame);
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    const t = now * 0.001;

    const anchorX = cursor.has ? cursor.x : W * 0.5;
    const anchorY = cursor.has ? cursor.y : H * 0.5;

    const maxSpeed = 110 + Math.max(0.1, speed) * 165;
    const steerRate = 4.5 + Math.max(0.1, speed) * 1.15;
    const maxForce = maxSpeed * 9;
    const band = Math.max(20, spread * 0.55);
    const sepDist = Math.max(1, spread * 0.42 * (0.35 + separation));
    const flowMix = wander * 2.4;
    const eps = 0.08;
    const baseScale = 0.0016;
    const fineScale = baseScale * 3.6;

    for (let i = 0; i < MAX; i++) {
      const dx = anchorX - px[i],
        dy = anchorY - py[i];
      const dist = Math.sqrt(dx * dx + dy * dy) || 1e-4;
      const ux = dx / dist,
        uy = dy / dist;

      const orbitDrift = noise3(noiseX[i], noiseY[i], t * 0.13);
      const orbit = band * (0.34 + 1.35 * Math.max(0, Math.min(1, orbitDrift + 0.5)));
      const radial = Math.max(-1, Math.min(1, (dist - orbit) / (band * 0.85)));
      const swirl = Math.sqrt(Math.max(0, 1 - radial * radial)) * handed[i];
      let wishX = ux * radial - uy * swirl;
      let wishY = uy * radial + ux * swirl;

      if (flowMix > 0.001) {
        const bx = px[i] * baseScale,
          by = py[i] * baseScale,
          bt = t * 0.22;
        const coarseX = (noise3(bx, by + eps, bt) - noise3(bx, by - eps, bt)) / (2 * eps);
        const coarseY = -(noise3(bx + eps, by, bt) - noise3(bx - eps, by, bt)) / (2 * eps);
        const fx = px[i] * fineScale + noiseX[i],
          fy = py[i] * fineScale + noiseY[i],
          ft = t * 0.55;
        const fineX = (noise3(fx, fy + eps, ft) - noise3(fx, fy - eps, ft)) / (2 * eps);
        const fineY = -(noise3(fx + eps, fy, ft) - noise3(fx - eps, fy, ft)) / (2 * eps);
        wishX += (coarseX + fineX * 0.7) * flowMix;
        wishY += (coarseY + fineY * 0.7) * flowMix;
      }

      const wl = Math.sqrt(wishX * wishX + wishY * wishY) || 1e-4;
      wishX /= wl;
      wishY /= wl;

      const rate = steerRate * agility[i];
      let ax = (wishX * maxSpeed - vx[i]) * rate;
      let ay = (wishY * maxSpeed - vy[i]) * rate;

      for (let j = 0; j < MAX; j++) {
        if (j === i) continue;
        const sx = px[i] - px[j],
          sy = py[i] - py[j];
        const d2 = sx * sx + sy * sy;
        if (d2 > 1e-4 && d2 < sepDist * sepDist) {
          const dd = Math.sqrt(d2);
          const ff = (1 - dd / sepDist) * maxSpeed * 3.2 * separation;
          ax += (sx / dd) * ff;
          ay += (sy / dd) * ff;
        }
      }

      const al = Math.sqrt(ax * ax + ay * ay);
      if (al > maxForce) {
        ax = (ax / al) * maxForce;
        ay = (ay / al) * maxForce;
      }
      vx[i] += ax * dt;
      vy[i] += ay * dt;
      const sp = Math.sqrt(vx[i] * vx[i] + vy[i] * vy[i]);
      const hi = maxSpeed,
        lo = maxSpeed * 0.32;
      if (sp > hi) {
        vx[i] = (vx[i] / sp) * hi;
        vy[i] = (vy[i] / sp) * hi;
      } else if (sp < lo && sp > 1e-4) {
        vx[i] = (vx[i] / sp) * lo;
        vy[i] = (vy[i] / sp) * lo;
      }
      px[i] += vx[i] * dt;
      py[i] += vy[i] * dt;

      if (px[i] < -260 || px[i] > W + 260 || py[i] < -260 || py[i] > H + 260)
        spawn(i, anchorX, anchorY);
    }

    const nowSec = now * 0.001;
    if (lastSample < 0 || nowSec - lastSample >= 0.008) {
      lastSample = nowSec;
      histT[histHead] = nowSec;
      const base = histHead * MAX;
      for (let k = 0; k < MAX; k++) {
        histX[base + k] = px[k];
        histY[base + k] = py[k];
      }
      histHead = (histHead + 1) % HISTORY;
      if (histLen < HISTORY) histLen++;
    }

    // —— 渲染（细小线条拖尾 + 小点粒子头，不刺眼）——
    ctx.clearRect(0, 0, W, H);
    ctx.globalCompositeOperation = "source-over";
    ctx.lineCap = "round";
    const trailAge = trail * 0.85;
    void size;
    void opacity;
    void scale;

    for (let i = 0; i < MAX; i++) {
      if (trailAge >= 0.01 && histLen >= 2) {
        ctx.strokeStyle = palette.trailColor;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(px[i], py[i]);
        for (let jj = 0; jj < histLen; jj++) {
          const slot = (histHead - 1 - jj + HISTORY) % HISTORY;
          if (nowSec - histT[slot] > trailAge) break;
          ctx.lineTo(histX[slot * MAX + i], histY[slot * MAX + i]);
        }
        ctx.stroke();
      }
      ctx.fillStyle = palette.particleColor;
      ctx.beginPath();
      ctx.arc(px[i], py[i], 1.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  raf = requestAnimationFrame(frame);

  return () => {
    cancelAnimationFrame(raf);
    window.removeEventListener("resize", resize);
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerleave", onLeave);
  };
}

/**
 * 粒子文字（照搬 admin.html initParticleText，参考 React Bits 源码）
 * 粒子聚集成文字 + 待机漂移 + 鼠标推开 + 进场聚拢动画。
 * text 可参数化，配色跟随 FxPalette 语义（color/highlight）。
 */
export function initParticleText(
  canvas: HTMLCanvasElement,
  opts?: { text?: string; color?: string; highlightColor?: string }
): () => void {
  const ctx = canvas.getContext("2d")!;

  const text = opts?.text ?? "YUE ZHOU";
  const particleSize = 2.3,
    density = 4;
  const color = opts?.color ?? "#22d3ee",
    highlightColor = opts?.highlightColor ?? "#7ffcff";
  const scatter = 200,
    gatherDuration = 1600,
    stagger = 320;
  const pointerRepel = 70,
    repelRadius = 140,
    idleDrift = 1.1,
    glow = true;
  const baseIntensity = 0.18,
    fuzzRange = 30;

  const W = 720,
    H = 180;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  canvas.style.width = "min(720px, 92vw)";
  canvas.style.height = "180px";
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  function hexToRgb(hex: string) {
    const c = hex.replace("#", "").trim();
    if (!/^[0-9a-fA-F]{6}$/.test(c)) return null;
    return {
      r: parseInt(c.slice(0, 2), 16),
      g: parseInt(c.slice(2, 4), 16),
      b: parseInt(c.slice(4, 6), 16),
    };
  }
  function mixRgb(f: { r: number; g: number; b: number }, t: { r: number; g: number; b: number }, a: number) {
    return {
      r: Math.round(f.r + (t.r - f.r) * a),
      g: Math.round(f.g + (t.g - f.g) * a),
      b: Math.round(f.b + (t.b - f.b) * a),
    };
  }
  function rgbToCss(r: { r: number; g: number; b: number }) {
    return "rgb(" + r.r + "," + r.g + "," + r.b + ")";
  }
  function clamp(v: number, mn: number, mx: number) {
    return Math.min(Math.max(v, mn), mx);
  }
  function easeOutCubic(t: number) {
    return 1 - Math.pow(1 - t, 3);
  }
  function rowNoise(row: number, now: number) {
    const frame = Math.floor(now / 45);
    const n = Math.sin(row * 12.9898 + frame * 78.233) * 43758.5453;
    return (n - Math.floor(n)) * 2 - 1;
  }

  const off = document.createElement("canvas");
  off.width = W;
  off.height = H;
  const octx = off.getContext("2d", { willReadFrequently: true });
  if (!octx) return () => {};
  let fontSize = 124;
  let font = '800 ' + fontSize + 'px -apple-system, "Arial Black", "Segoe UI", sans-serif';
  octx.font = font;
  let metrics = octx.measureText(text);
  const maxW = W * 0.92;
  if (metrics.width > maxW) {
    fontSize = Math.max(40, fontSize * (maxW / metrics.width));
    font = '800 ' + fontSize + 'px -apple-system, "Arial Black", "Segoe UI", sans-serif';
    octx.font = font;
    metrics = octx.measureText(text);
  }
  const left = Math.ceil(metrics.actualBoundingBoxLeft || 0);
  const right = Math.ceil(metrics.actualBoundingBoxRight || metrics.width);
  const ascent = Math.ceil(metrics.actualBoundingBoxAscent || fontSize * 0.78);
  const descent = Math.ceil(metrics.actualBoundingBoxDescent || fontSize * 0.22);
  const pad = Math.max(12, Math.ceil(fontSize * 0.08));
  const tw = Math.max(1, left + right),
    th = Math.max(1, ascent + descent);
  off.width = tw + pad * 2;
  off.height = th + pad * 2;
  octx.font = font;
  octx.textAlign = "left";
  octx.textBaseline = "alphabetic";
  octx.fillStyle = "#fff";
  octx.fillText(text, pad - left, pad + ascent);
  const data = octx.getImageData(0, 0, off.width, off.height);

  const targets: { x: number; y: number; alpha: number }[] = [];
  const step = Math.max(2, Math.floor(density));
  for (let y = 0; y < off.height; y += step) {
    for (let x = 0; x < off.width; x += step) {
      const al = data.data[(y * off.width + x) * 4 + 3];
      if (al > 40) targets.push({ x: W / 2 - off.width / 2 + x, y: H / 2 - off.height / 2 + y, alpha: al / 255 });
    }
  }
  const maxParticles = Math.max(900, Math.min(5200, Math.floor((W * H) / 90)));
  const stride = Math.max(1, Math.ceil(targets.length / maxParticles));
  const baseRgb = hexToRgb(color),
    highlightRgb = hexToRgb(highlightColor);
  const selected = targets.filter((_, i) => i % stride === 0);

  const particles = selected.map((t, i) => {
    const seed = ((i * 9301 + 49297) % 233280) / 233280;
    const depth = 0.45 + (((i * 233 + 97) % 1000) / 1000) * 0.9;
    const blend = baseRgb && highlightRgb ? clamp(t.x / Math.max(1, W) + (seed - 0.5) * 0.35, 0, 1) : 0;
    const pc = baseRgb && highlightRgb ? rgbToCss(mixRgb(baseRgb, highlightRgb, blend)) : color;
    const angle = seed * Math.PI * 2;
    const dist = scatter * (0.35 + depth * 0.75);
    const sx = t.x + Math.cos(angle) * dist + (seed - 0.5) * scatter * 0.45;
    const sy = t.y + Math.sin(angle) * dist + (depth - 0.9) * scatter * 0.45;
    return {
      x: sx,
      y: sy,
      startX: sx,
      startY: sy,
      targetX: t.x,
      targetY: t.y,
      size: Math.max(0.6, particleSize * (0.75 + t.alpha * 0.45)),
      color: pc,
      seed: seed,
      depth: depth,
      delay: seed * stagger,
    };
  });

  let gathering = false,
    gatherStart = 0;
  const pointer = { active: false, x: W / 2, y: H / 2, smoothX: W / 2, smoothY: H / 2 };

  function startGather(fromScatter: boolean) {
    if (!particles.length) return;
    const now = performance.now();
    particles.forEach((p) => {
      if (fromScatter) {
        const angle = p.seed * Math.PI * 2;
        const dist = scatter * (0.35 + p.depth * 0.75);
        p.x = p.targetX + Math.cos(angle) * dist + (p.depth - 0.5) * scatter * 0.55;
        p.y = p.targetY + Math.sin(angle) * dist + (p.seed - 0.5) * scatter * 0.55;
      }
      p.startX = p.x;
      p.startY = p.y;
      p.delay = p.seed * stagger;
    });
    gatherStart = now;
    gathering = true;
  }

  function drawParticle(p: (typeof particles)[number]) {
    ctx.fillStyle = p.color;
    const s = p.size;
    if (s <= 2.1) {
      ctx.fillRect(p.x - s / 2, p.y - s / 2, s, s);
      return;
    }
    ctx.beginPath();
    ctx.arc(p.x, p.y, s / 2, 0, Math.PI * 2);
    ctx.fill();
  }

  let raf = 0;
  function render(now: number) {
    raf = requestAnimationFrame(render);
    ctx.clearRect(0, 0, W, H);
    if (glow) {
      ctx.shadowBlur = particleSize * 3;
      ctx.shadowColor = highlightColor;
    }
    pointer.smoothX += (pointer.x - pointer.smoothX) * 0.18;
    pointer.smoothY += (pointer.y - pointer.smoothY) * 0.18;
    let complete = true;
    particles.forEach((p) => {
      let bx = p.targetX,
        by = p.targetY,
        progress = 1;
      if (gathering) {
        const local = (now - gatherStart - p.delay) / Math.max(1, gatherDuration);
        progress = clamp(local, 0, 1);
        const eased = easeOutCubic(progress);
        bx = p.startX + (p.targetX - p.startX) * eased;
        by = p.startY + (p.targetY - p.startY) * eased;
        if (progress < 1) complete = false;
      } else {
        const dt = now * 0.001;
        const rn = rowNoise(Math.floor(p.targetY), now);
        bx += baseIntensity * rn * fuzzRange;
        bx += Math.sin(dt * 0.9 + p.seed * 10) * (idleDrift * 0.3) * p.depth;
        by += Math.cos(dt * 0.75 + p.depth * 10) * (idleDrift * 0.3) * p.depth;
      }
      if (pointer.active && pointerRepel > 0 && repelRadius > 0) {
        const dx = bx - pointer.smoothX,
          dy = by - pointer.smoothY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > 0 && dist < repelRadius) {
          const force = Math.pow(1 - dist / repelRadius, 2) * pointerRepel;
          bx += (dx / dist) * force;
          by += (dy / dist) * force;
        }
      }
      p.x += (bx - p.x) * 0.22;
      p.y += (by - p.y) * 0.22;
      ctx.globalAlpha = clamp(0.35 + progress * 0.65, 0, 1);
      drawParticle(p);
    });
    ctx.globalAlpha = 1;
    ctx.shadowBlur = 0;
    if (gathering && complete) gathering = false;
  }

  function toLocal(e: PointerEvent) {
    const r = canvas.getBoundingClientRect();
    return { x: (e.clientX - r.left) * (W / r.width), y: (e.clientY - r.top) * (H / r.height) };
  }
  const onEnter = (e: PointerEvent) => {
    const p = toLocal(e);
    pointer.x = p.x;
    pointer.y = p.y;
    pointer.active = true;
  };
  const onMove = (e: PointerEvent) => {
    const p = toLocal(e);
    pointer.x = p.x;
    pointer.y = p.y;
    pointer.active = true;
  };
  const onLeave = () => {
    pointer.active = false;
  };
  canvas.addEventListener("pointerenter", onEnter);
  canvas.addEventListener("pointermove", onMove);
  canvas.addEventListener("pointerleave", onLeave);

  startGather(false);
  raf = requestAnimationFrame(render);

  return () => {
    cancelAnimationFrame(raf);
    canvas.removeEventListener("pointerenter", onEnter);
    canvas.removeEventListener("pointermove", onMove);
    canvas.removeEventListener("pointerleave", onLeave);
  };
}
