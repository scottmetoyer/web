/* 360° panorama room viewer.
 *
 * A room is an HTML file that links pano.css and this script, sets its image
 * on <body data-pano="...">, and lists its exits as <a class="hotspot"> links
 * with data-yaw / data-pitch. Everything else — canvas, chrome, projection —
 * is built here.
 *
 * The panorama is raycast in a fragment shader across a fullscreen triangle,
 * which keeps perspective rectilinear at any zoom or pitch. Hotspots are real
 * DOM links, projected to screen coordinates every frame.
 */
(() => {
  "use strict";

  // ---------------------------------------------------------------------
  // Config: query string wins over the room's data attributes, so any view
  // stays linkable and testable — ?img=…&yaw=90&pitch=-10&fov=60&dither=1
  // ---------------------------------------------------------------------
  const q = new URLSearchParams(location.search);
  const data = document.body.dataset;

  const num = (key, dflt) => {
    const fromQuery = parseFloat(q.get(key));
    if (Number.isFinite(fromQuery)) return fromQuery;
    const fromRoom = parseFloat(data[key]);
    return Number.isFinite(fromRoom) ? fromRoom : dflt;
  };
  const flag = (key, dflt) => {
    const v = q.get(key) ?? data[key];
    return v == null ? dflt : v !== "0" && v !== "false";
  };

  const SRC        = q.get("img") || data.pano || "images/pano-hub.png";
  const FOV_MIN    = 25, FOV_MAX = 110;
  const PITCH_MAX  = 85 * Math.PI / 180;   // never quite reach the poles
  const DRIFT_RATE = 0.9 * Math.PI / 180;  // idle auto-rotate, degrees/sec
  const IDLE_AFTER = 5000;                 // ms of stillness before drifting
  const FRICTION   = 0.90;                 // per-frame inertia decay
  const DEG        = 180 / Math.PI;

  const view = {
    yaw:   num("yaw", 0) / DEG,
    pitch: num("pitch", 0) / DEG,
    fov:   Math.min(FOV_MAX, Math.max(FOV_MIN, num("fov", 78))) / DEG,
    vYaw: 0, vPitch: 0,
    dither: flag("dither", false),
    drift:  flag("drift", true),
  };

  // ---------------------------------------------------------------------
  // Chrome. Rooms only supply their hotspot links; the rest is built here so
  // a new room stays a handful of lines.
  // ---------------------------------------------------------------------
  const el = (tag, props = {}, html = "") => {
    const n = Object.assign(document.createElement(tag), props);
    if (html) n.innerHTML = html;
    return n;
  };

  const stage = el("div", { id: "stage" });
  const canvas = el("canvas", { id: "gl" });
  stage.append(canvas);

  // Authored in the room's markup so the links survive without JavaScript.
  const nav = document.getElementById("hotspots");
  if (nav) stage.append(nav);
  document.body.prepend(stage);

  const statusEl = el("div", { className: "overlay", id: "status" },
                      '<div id="statusText">loading…</div>');
  const readout = el("div", { className: "overlay", id: "readout", hidden: true });
  const titleEl = el("div", { className: "overlay", id: "title" });
  const hint = el("div", { className: "overlay", id: "hint" },
    "<span><b>drag</b> to look</span>" +
    '<span class="desktop-only"><b>scroll</b> to zoom</span>' +
    '<span class="desktop-only"><b>f</b> fullscreen</span>' +
    '<span class="desktop-only"><b>d</b> dither</span>' +
    '<span class="desktop-only"><b>r</b> reset</span>');
  const dropEl = el("div", { className: "overlay", id: "drop" },
                    "<span>drop a 360° photo</span>");

  titleEl.textContent = data.room || "";
  document.body.append(statusEl, readout, titleEl, hint, dropEl);
  const statusText = document.getElementById("statusText");

  const fail = (msg) => {
    statusEl.classList.remove("hidden");
    statusText.innerHTML = '<div class="err">' + msg + "</div>";
  };

  // ---------------------------------------------------------------------
  // GL setup. WebGL2 when available purely because it allows REPEAT wrapping
  // on non-power-of-two textures; WebGL1 gets the image rescaled instead.
  // ---------------------------------------------------------------------
  const glOpts = { antialias: false, alpha: false, depth: false,
                   powerPreference: "high-performance" };
  const gl = canvas.getContext("webgl2", glOpts) || canvas.getContext("webgl", glOpts);
  if (!gl) { fail("This browser can’t do WebGL, so the 360° view can’t render."); return; }
  const isGL2 = typeof WebGL2RenderingContext !== "undefined" &&
                gl instanceof WebGL2RenderingContext;

  // GLSL ES 1.00 — accepted by both WebGL1 and WebGL2.
  const VERT = `
    attribute vec2 aPos;
    varying vec2 vNdc;
    void main() { vNdc = aPos; gl_Position = vec4(aPos, 0.0, 1.0); }
  `;

  const FRAG = `
    precision highp float;
    varying vec2 vNdc;
    uniform sampler2D uTex;
    uniform vec2  uRes;
    uniform float uTanHalfFov;
    uniform float uYaw;
    uniform float uPitch;
    uniform float uDither;

    const float PI = 3.14159265359;

    // 4x4 Bayer matrix, for the optional 1-bit look.
    float bayer(vec2 p) {
      vec2 c = mod(floor(p), 4.0);
      float i = c.y * 4.0 + c.x;
      float m[16];
      m[0]=0.0;  m[1]=8.0;  m[2]=2.0;  m[3]=10.0;
      m[4]=12.0; m[5]=4.0;  m[6]=14.0; m[7]=6.0;
      m[8]=3.0;  m[9]=11.0; m[10]=1.0; m[11]=9.0;
      m[12]=15.0;m[13]=7.0; m[14]=13.0;m[15]=5.0;
      for (int k = 0; k < 16; k++) {
        if (float(k) == i) return (m[k] + 0.5) / 16.0;
      }
      return 0.5;
    }

    void main() {
      // Ray through this pixel in view space, then rotate by pitch and yaw.
      float aspect = uRes.x / uRes.y;
      vec3 d = normalize(vec3(vNdc.x * aspect * uTanHalfFov,
                              vNdc.y * uTanHalfFov,
                              -1.0));

      float cp = cos(uPitch), sp = sin(uPitch);
      d = vec3(d.x, d.y * cp - d.z * sp, d.y * sp + d.z * cp);

      float cy = cos(uYaw), sy = sin(uYaw);
      d = vec3(d.x * cy - d.z * sy, d.y, d.x * sy + d.z * cy);

      // Direction -> equirectangular texel.
      vec2 uv = vec2(atan(d.x, -d.z) / (2.0 * PI) + 0.5,
                     0.5 - asin(clamp(d.y, -1.0, 1.0)) / PI);

      vec3 col = texture2D(uTex, uv).rgb;

      if (uDither > 0.5) {
        float l = dot(col, vec3(0.299, 0.587, 0.114));
        l = pow(l, 0.85);
        col = vec3(step(bayer(gl_FragCoord.xy), l));
      }

      gl_FragColor = vec4(col, 1.0);
    }
  `;

  function compile(type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      throw new Error(gl.getShaderInfoLog(s) || "shader compile failed");
    }
    return s;
  }

  let prog;
  try {
    prog = gl.createProgram();
    gl.attachShader(prog, compile(gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(prog) || "program link failed");
    }
  } catch (e) {
    fail("Shader error: " + e.message);
    return;
  }
  gl.useProgram(prog);

  // Fullscreen triangle — cheaper than a quad and needs no index buffer.
  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const aPos = gl.getAttribLocation(prog, "aPos");
  gl.enableVertexAttribArray(aPos);
  gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

  const U = {
    res:    gl.getUniformLocation(prog, "uRes"),
    tan:    gl.getUniformLocation(prog, "uTanHalfFov"),
    yaw:    gl.getUniformLocation(prog, "uYaw"),
    pitch:  gl.getUniformLocation(prog, "uPitch"),
    dither: gl.getUniformLocation(prog, "uDither"),
  };

  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
  // 1x1 placeholder so the first frames render something rather than erroring.
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, 1, 1, 0, gl.RGB, gl.UNSIGNED_BYTE,
                new Uint8Array([12, 14, 22]));

  let haveImage = false;

  // Panoramas are routinely wider than the GPU allows, and WebGL1 additionally
  // needs power-of-two dimensions to wrap horizontally. Rescale when needed.
  function fitForGPU(img) {
    const max = gl.getParameter(gl.MAX_TEXTURE_SIZE);
    const pot = (n) => Math.pow(2, Math.round(Math.log2(n)));
    const w = img.naturalWidth || img.width;
    const h = img.naturalHeight || img.height;

    let tw = Math.min(w, max);
    let th = Math.min(h, max);
    if (!isGL2) { tw = Math.min(pot(tw), max); th = Math.min(pot(th), max); }
    if (tw === w && th === h) return img;

    const c = document.createElement("canvas");
    c.width = tw; c.height = th;
    const ctx = c.getContext("2d");
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, 0, 0, tw, th);
    return c;
  }

  function upload(img) {
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, fitForGPU(img));
    haveImage = true;
    statusEl.classList.add("hidden");
    readout.hidden = false;
    document.body.classList.add("ready");
    scheduleHintFade();
  }

  function load(src, label) {
    statusEl.classList.remove("hidden");
    statusText.textContent = "loading…";
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => upload(img);
    img.onerror = () => {
      if (location.protocol === "file:") {
        fail("Couldn’t load <b>" + label + "</b>.<br><br>Browsers block WebGL " +
             "textures on <code>file://</code> — serve the folder instead:<br>" +
             "<code>python3 -m http.server</code>");
      } else {
        fail("Couldn’t load <b>" + label + "</b>.");
      }
    };
    img.src = src;
  }

  // ---------------------------------------------------------------------
  // Hotspots
  // ---------------------------------------------------------------------
  // A room writes <a class="hotspot" data-yaw data-pitch>Label</a>; the ring
  // and label markup is built here so room files stay a single line per exit.
  const hotspots = [...document.querySelectorAll(".hotspot")].map((node) => {
    const label = node.textContent.trim();
    node.textContent = "";
    const inner = el("span", { className: "inner" });
    inner.append(el("span", { className: "ring" }), el("span", { className: "label" }, label));
    node.append(inner);
    node.setAttribute("draggable", "false");
    return {
      node,
      lonDeg: parseFloat(node.dataset.yaw) || 0,
      lon: (parseFloat(node.dataset.yaw) || 0) / DEG,
      lat: (parseFloat(node.dataset.pitch) || 0) / DEG,
      edge: null,
    };
  });

  // Project each hotspot's world direction back into view space and onto the
  // screen — the exact inverse of the rotation the shader applies. Exits that
  // fall outside the frame are pinned to the edge they lie beyond, dimmed,
  // rather than hidden: otherwise you can arrive in a room facing away from
  // every exit and have no idea there is anywhere to go.
  function placeHotspots(w, h) {
    if (!hotspots.length) return;
    const cy = Math.cos(view.yaw), sy = Math.sin(view.yaw);
    const cp = Math.cos(view.pitch), sp = Math.sin(view.pitch);
    const t = Math.tan(view.fov / 2);
    const aspect = w / h;
    const yawDeg = view.yaw * DEG;

    for (const spot of hotspots) {
      const cl = Math.cos(spot.lat);
      const wx = cl * Math.sin(spot.lon);
      const wy = Math.sin(spot.lat);
      const wz = -cl * Math.cos(spot.lon);

      // Undo yaw, then undo pitch.
      const x = wx * cy + wz * sy;
      const zy = -wx * sy + wz * cy;
      const y = wy * cp + zy * sp;
      const z = -wy * sp + zy * cp;

      let px, py, side, inFrame = false;
      if (z < -1e-3) {
        // In front of the camera: use the true projected position. When it
        // falls outside the frame it gets clamped below rather than parked at
        // a fixed spot, so the marker slides continuously along the edge and
        // hands off to its real position without a jump.
        const ndcX = (x / -z) / (aspect * t);
        const ndcY = (y / -z) / t;
        px = (ndcX * 0.5 + 0.5) * w;
        py = (0.5 - ndcY * 0.5) * h;
        side = ndcX >= 0 ? "right" : "left";
        inFrame = Math.abs(ndcX) < 0.94 && Math.abs(ndcY) < 0.9;
      } else {
        // Behind the camera, where the projection is meaningless. Approximate
        // the height by angle so it does not jump as it swings into view.
        const rel = ((spot.lonDeg - yawDeg + 540) % 360) - 180;
        side = rel >= 0 ? "right" : "left";
        px = side === "right" ? Infinity : -Infinity;
        py = h / 2 - (spot.lat - view.pitch) * (h / view.fov);
      }

      if (!inFrame) {
        if (spot.edge !== side) {
          spot.edge = side;
          spot.node.classList.add("edge");
          spot.node.dataset.side = side;
          // Measured once per transition, so a long label can't hang off screen.
          spot.halfW = spot.node.offsetWidth / 2;
        }
        px = Math.min(Math.max(px, spot.halfW + 8), w - spot.halfW - 8);
        py = Math.min(Math.max(py, 56), h - 56);
      } else if (spot.edge !== null) {
        spot.edge = null;
        spot.node.classList.remove("edge");
        delete spot.node.dataset.side;
      }

      spot.node.style.visibility = "visible";
      spot.node.style.transform =
        `translate(-50%, -50%) translate(${px.toFixed(1)}px, ${py.toFixed(1)}px)`;
    }
  }

  // Leaving a room fades out rather than cutting, so the rooms feel connected.
  document.addEventListener("click", (e) => {
    const link = e.target.closest("a.hotspot");
    if (!link) return;
    // A drag that happens to start on a hotspot is a look, not a click.
    if (dragDist > 6) { e.preventDefault(); return; }
    // Leave modified clicks (new tab, download, …) to the browser.
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    document.body.classList.add("leaving");
    const go = () => { location.href = link.href; };
    stage.addEventListener("transitionend", go, { once: true });
    setTimeout(go, 400);   // in case the transition never fires
  });

  // ---------------------------------------------------------------------
  // Interaction
  // ---------------------------------------------------------------------
  let lastInput = performance.now();
  const touched = () => { lastInput = performance.now(); };

  const pointers = new Map();
  let pinchDist = 0;
  let lastMove = 0;
  let dragDist = 0;

  // pointerdown is bound to the stage so drags can start on a hotspot too;
  // move/up go on window so the drag survives leaving the element. Pointer
  // capture is deliberately not used — it interferes with link clicks.
  stage.addEventListener("pointerdown", (e) => {
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    stage.classList.add("dragging");
    view.vYaw = view.vPitch = 0;
    dragDist = 0;
    touched();
    hint.classList.add("hidden");
  });

  addEventListener("pointermove", (e) => {
    const p = pointers.get(e.pointerId);
    if (!p) return;

    const dx = e.clientX - p.x;
    const dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    dragDist += Math.abs(dx) + Math.abs(dy);

    if (pointers.size >= 2) {
      // Two fingers down: treat the pinch span as zoom.
      const pts = [...pointers.values()];
      const d = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      if (pinchDist > 0 && d > 0) zoom(Math.log(pinchDist / d) * 1.4);
      pinchDist = d;
      touched();
      return;
    }

    // Scale by FOV so the drag tracks the image at any zoom level. Both signs
    // are "grab the photo and pull": drag right and the scene follows right,
    // drag down and the sky comes into view.
    const perPx = view.fov / stage.clientHeight;
    const stepYaw = -dx * perPx;
    const stepPitch = dy * perPx;
    view.yaw += stepYaw;
    view.pitch = clampPitch(view.pitch + stepPitch);

    // Smooth the throw velocity: a single stuttered frame shouldn't decide
    // how far the view coasts after release.
    view.vYaw = view.vYaw * 0.4 + stepYaw * 0.6;
    view.vPitch = view.vPitch * 0.4 + stepPitch * 0.6;
    lastMove = performance.now();
    touched();
  });

  const release = (e) => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinchDist = 0;
    if (pointers.size === 0) {
      stage.classList.remove("dragging");
      // Holding still before letting go means "stop here", not "fling".
      if (performance.now() - lastMove > 80) view.vYaw = view.vPitch = 0;
    }
    touched();
  };
  addEventListener("pointerup", release);
  addEventListener("pointercancel", release);
  addEventListener("blur", () => { pointers.clear(); stage.classList.remove("dragging"); });

  stage.addEventListener("wheel", (e) => {
    e.preventDefault();
    zoom(e.deltaY * (e.deltaMode === 1 ? 0.03 : 0.0012));
    touched();
  }, { passive: false });

  function zoom(delta) {
    const f = view.fov * Math.exp(delta);
    view.fov = Math.min(FOV_MAX / DEG, Math.max(FOV_MIN / DEG, f));
  }

  function clampPitch(p) { return Math.max(-PITCH_MAX, Math.min(PITCH_MAX, p)); }

  addEventListener("keydown", (e) => {
    // Don't hijack keys while a hotspot is focused and being activated.
    if (e.target.closest && e.target.closest("a") && (e.key === "Enter" || e.key === " ")) return;
    const step = view.fov * 0.08;
    switch (e.key) {
      case "ArrowLeft":  view.yaw -= step; break;
      case "ArrowRight": view.yaw += step; break;
      case "ArrowUp":    view.pitch = clampPitch(view.pitch + step); break;
      case "ArrowDown":  view.pitch = clampPitch(view.pitch - step); break;
      case "+": case "=": zoom(-0.15); break;
      case "-": case "_": zoom(0.15); break;
      case "d": case "D": view.dither = !view.dither; break;
      case "r": case "R":
        view.yaw = num("yaw", 0) / DEG;
        view.pitch = num("pitch", 0) / DEG;
        view.fov = Math.min(FOV_MAX, Math.max(FOV_MIN, num("fov", 78))) / DEG;
        break;
      case " ": view.drift = !view.drift; break;
      case "f": case "F":
        if (document.fullscreenElement) document.exitFullscreen();
        else document.documentElement.requestFullscreen?.();
        break;
      default: return;
    }
    e.preventDefault();
    touched();
  });

  // Drop any equirectangular photo onto the page to view it.
  addEventListener("dragover", (e) => { e.preventDefault(); dropEl.classList.add("on"); });
  addEventListener("dragleave", (e) => {
    if (e.relatedTarget === null) dropEl.classList.remove("on");
  });
  addEventListener("drop", (e) => {
    e.preventDefault();
    dropEl.classList.remove("on");
    const file = e.dataTransfer?.files?.[0];
    if (file && file.type.startsWith("image/")) load(URL.createObjectURL(file), file.name);
  });

  let hintTimer = 0;
  function scheduleHintFade() {
    clearTimeout(hintTimer);
    hintTimer = setTimeout(() => hint.classList.add("hidden"), 7000);
  }

  // ---------------------------------------------------------------------
  // Render loop
  // ---------------------------------------------------------------------
  let vw = 0, vh = 0;
  function resize() {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.round(canvas.clientWidth * dpr));
    const h = Math.max(1, Math.round(canvas.clientHeight * dpr));
    if (w === vw && h === vh) return;
    vw = canvas.width = w;
    vh = canvas.height = h;
    gl.viewport(0, 0, w, h);
  }

  const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  let lastReadout = "";
  let prev = performance.now();

  function frame(now) {
    const dt = Math.min((now - prev) / 1000, 0.1);
    prev = now;
    resize();

    if (pointers.size === 0) {
      // Inertia, then a slow drift once things have been still for a while.
      view.yaw += view.vYaw;
      view.pitch = clampPitch(view.pitch + view.vPitch);
      const decay = Math.pow(FRICTION, dt * 60);
      view.vYaw *= decay;
      view.vPitch *= decay;
      if (Math.abs(view.vYaw) < 1e-5) view.vYaw = 0;
      if (Math.abs(view.vPitch) < 1e-5) view.vPitch = 0;

      if (view.drift && view.vYaw === 0 && now - lastInput > IDLE_AFTER) {
        view.yaw += DRIFT_RATE * dt;
      }
    }

    gl.uniform2f(U.res, vw, vh);
    gl.uniform1f(U.tan, Math.tan(view.fov / 2));
    gl.uniform1f(U.yaw, view.yaw);
    gl.uniform1f(U.pitch, view.pitch);
    gl.uniform1f(U.dither, view.dither ? 1 : 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);

    placeHotspots(stage.clientWidth, stage.clientHeight);

    if (haveImage) {
      const deg = ((view.yaw * DEG) % 360 + 360) % 360;
      const txt = COMPASS[Math.round(deg / 45) % 8].padEnd(2) + " " +
                  deg.toFixed(0).padStart(3) + "°  ·  " +
                  (view.fov * DEG).toFixed(0) + "° fov";
      if (txt !== lastReadout) { readout.textContent = txt; lastReadout = txt; }
    }

    requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
  load(SRC, SRC);
})();
