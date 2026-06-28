/* OPC UA 3D Scene — three.js viewer driven by Python over QWebChannel.
 *
 * Python -> JS : bridge.toScene(jsonString)
 *    { type: "scene", design: bool, objects: [cfg, ...] }
 *    { type: "mode",  design: bool }
 *    { type: "values", values: { id: value, ... } }   // run mode
 *    { type: "select", id: "..." }
 * JS -> Python :
 *    bridge.onReady()
 *    bridge.onObjectSelected(id)   // design-mode click
 *    bridge.onObjectClicked(id)    // run-mode click (call/write)
 */
(function () {
  "use strict";

  var canvas = document.getElementById("c");
  var hintEl = document.getElementById("hint");
  var badgeEl = document.getElementById("badge");

  var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);

  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0f19);

  var camera = new THREE.PerspectiveCamera(55, 1, 0.1, 1000);
  camera.position.set(6, 6, 9);

  var controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.target.set(0, 0.5, 0);

  scene.add(new THREE.AmbientLight(0xffffff, 0.65));
  var dir = new THREE.DirectionalLight(0xffffff, 0.9);
  dir.position.set(5, 10, 7);
  scene.add(dir);

  var grid = new THREE.GridHelper(40, 40, 0x374151, 0x1f2937);
  scene.add(grid);

  // ── state ────────────────────────────────────────────────────────────
  var configs = {};   // id -> config
  var meshes = {};    // id -> THREE.Mesh
  var design = true;
  var selectedId = null;
  var bridge = null;
  var lastCount = -1; // object count at last build (to auto-fit on add/load)
  var anchorPos = {}; // anchor key -> {x,y,z} world position
  var anchorTubes = {}; // sourceId -> { key -> {g, sig} }
  var gridMap = {};   // region key -> {x,z,w,d,baseY}
  var rackTrays = {}; // sourceId -> [meshes] (region racks)
  var rackSig = {};   // sourceId -> last data signature (skip rebuilds)
  var tagMeshes = {}; // tag -> [meshes] (for colour sources)

  // ── mesh helpers ─────────────────────────────────────────────────────
  function makeGeometry(shape, size) {
    var s = size || 1;
    switch (shape) {
      case "cylinder": return new THREE.CylinderGeometry(0.5 * s, 0.5 * s, s, 32);
      case "sphere":   return new THREE.SphereGeometry(0.6 * s, 32, 24);
      case "cone":     return new THREE.ConeGeometry(0.6 * s, s, 32);
      default:         return new THREE.BoxGeometry(s, s, s);
    }
  }

  function disposeMesh(mesh) {
    scene.remove(mesh);
    if (mesh.geometry) mesh.geometry.dispose();
    if (mesh.material) mesh.material.dispose();
  }

  var labelSprites = [];
  function makeTextSprite(text) {
    var cv = document.createElement("canvas");
    var ctx = cv.getContext("2d");
    var font = "bold 46px system-ui, Segoe UI, sans-serif";
    ctx.font = font;
    var pad = 22;
    var w = Math.ceil(ctx.measureText(text).width + pad * 2);
    var h = 70;
    cv.width = w; cv.height = h;
    ctx.font = font;
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    // No background box — just the text with a dark outline so it stays
    // readable against any colour behind it.
    ctx.lineJoin = "round";
    ctx.lineWidth = 7;
    ctx.strokeStyle = "rgba(9,12,10,0.85)";
    ctx.strokeText(text, w / 2, h / 2 + 2);
    ctx.fillStyle = "#f3f7e8";
    ctx.fillText(text, w / 2, h / 2 + 2);
    var tex = new THREE.CanvasTexture(cv);
    tex.minFilter = THREE.LinearFilter;
    var mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
    var sp = new THREE.Sprite(mat);
    var s = 0.011;
    sp.scale.set(w * s, h * s, 1);
    sp.renderOrder = 999;
    return sp;
  }
  function addLabel(text, x, y, z) {
    var sp = makeTextSprite(text);
    sp.position.set(x, y, z);
    scene.add(sp);
    labelSprites.push(sp);
  }
  function clearLabels() {
    labelSprites.forEach(function (sp) {
      scene.remove(sp);
      if (sp.material) { if (sp.material.map) sp.material.map.dispose(); sp.material.dispose(); }
    });
    labelSprites = [];
  }

  function buildScene(objects) {
    Object.keys(meshes).forEach(function (id) { disposeMesh(meshes[id]); });
    meshes = {};
    configs = {};
    anchorPos = {};
    tagMeshes = {};
    clearLabels();
    (objects || []).forEach(function (cfg) {
      configs[cfg.id] = cfg;
      if (cfg.shape === "text") {
        if (cfg.label) addLabel(cfg.label, cfg.x, cfg.y, cfg.z);
        return;
      }
      var mat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(cfg.color || "#6366f1"),
        metalness: 0.1, roughness: 0.6,
      });
      var mesh = new THREE.Mesh(makeGeometry(cfg.shape, cfg.size), mat);
      mesh.position.set(cfg.x, cfg.y, cfg.z);
      mesh.scale.set(cfg.sx || 1, cfg.sy || 1, cfg.sz || 1);
      if (cfg.rx || cfg.ry || cfg.rz) {
        var D = Math.PI / 180;
        mesh.rotation.set((cfg.rx || 0) * D, (cfg.ry || 0) * D, (cfg.rz || 0) * D);
      }
      mesh.userData.id = cfg.id;
      mesh.userData.baseColor = cfg.color || "#6366f1";
      scene.add(mesh);
      meshes[cfg.id] = mesh;
      if (cfg.anchor) {
        anchorPos[cfg.anchor] = { x: cfg.x, y: cfg.y, z: cfg.z };
      }
      if (cfg.tag) {
        (tagMeshes[cfg.tag] = tagMeshes[cfg.tag] || []).push(mesh);
      }
      if (cfg.label) {
        addLabel(cfg.label, cfg.x, cfg.y + (cfg.sy || 1) * 0.55 + 0.45, cfg.z);
      }
    });
    highlight(selectedId);
  }

  function applyColors(colors) {
    Object.keys(colors || {}).forEach(function (tag) {
      var col = colors[tag];
      (tagMeshes[tag] || []).forEach(function (m) {
        if (m.material && m.material.color) m.material.color.set(col);
      });
    });
  }

  function updatePanel(rows) {
    var el = document.getElementById("panel");
    if (!el) return;
    if (!rows || !rows.length) { el.style.display = "none"; return; }
    el.style.display = "block";
    var html = '<div class="panel-title">SYSTEM STATE</div>';
    rows.forEach(function (r) {
      html += '<div class="panel-row">' +
        '<span class="dot" style="background:' + r.color + '"></span>' +
        '<span class="pl">' + r.label + '</span>' +
        '<span class="pv">' + r.text + ' (' + r.value + ')</span></div>';
    });
    el.innerHTML = html;
  }

  function fitView() {
    var ids = Object.keys(meshes);
    if (!ids.length) return;
    var bbox = new THREE.Box3();
    ids.forEach(function (id) { bbox.expandByObject(meshes[id]); });
    if (bbox.isEmpty()) return;
    var center = bbox.getCenter(new THREE.Vector3());
    var size = bbox.getSize(new THREE.Vector3());
    var maxDim = Math.max(size.x, size.y, size.z, 1);
    var dist = maxDim * 1.7;
    controls.target.copy(center);
    camera.position.set(center.x + dist * 0.8, center.y + dist * 0.7, center.z + dist);
    camera.near = Math.max(0.1, maxDim / 100);
    camera.far = maxDim * 50;
    camera.updateProjectionMatrix();
    controls.update();
  }

  function highlight(id) {
    Object.keys(meshes).forEach(function (k) {
      var m = meshes[k];
      if (!m.material.emissive) return;
      m.material.emissive.setHex(k === id && design ? 0x334155 : 0x000000);
    });
  }

  // ── value mapping (run mode) ─────────────────────────────────────────
  function norm(cfg, v) {
    var lo = cfg.min_value, hi = cfg.max_value;
    if (hi <= lo) return 0;
    var t = (Number(v) - lo) / (hi - lo);
    return Math.max(0, Math.min(1, t));
  }

  function applyValues(values) {
    Object.keys(values || {}).forEach(function (id) {
      var cfg = configs[id], mesh = meshes[id];
      if (!cfg || !mesh) return;
      var v = values[id];
      if (cfg.binding !== "read") return;
      switch (cfg.drive) {
        case "color": {
          var t = norm(cfg, v);
          mesh.material.color.setHSL(0.66 * (1 - t), 0.85, 0.5);
          break;
        }
        case "scaleY":
          mesh.scale.y = (cfg.sy || 1) * (0.2 + norm(cfg, v) * 2.5);
          break;
        case "rotateY":
          mesh.rotation.y = norm(cfg, v) * Math.PI * 2;
          break;
        case "posX":
          mesh.position.x = cfg.x + (norm(cfg, v) - 0.5) * 12;
          break;
        case "posY":
          mesh.position.y = cfg.y + norm(cfg, v) * 3;
          break;
        case "posZ":
          mesh.position.z = cfg.z + (norm(cfg, v) - 0.5) * 8;
          break;
        case "visible":
          mesh.visible = !(v === 0 || v === false || v === null);
          break;
      }
    });
  }

  // ── picking ──────────────────────────────────────────────────────────
  var raycaster = new THREE.Raycaster();
  var pointer = new THREE.Vector2();
  var downPos = null;

  renderer.domElement.addEventListener("pointerdown", function (e) {
    downPos = { x: e.clientX, y: e.clientY };
  });
  renderer.domElement.addEventListener("pointerup", function (e) {
    if (!downPos) return;
    var moved = Math.abs(e.clientX - downPos.x) + Math.abs(e.clientY - downPos.y);
    downPos = null;
    if (moved > 5) return; // it was an orbit drag, not a click
    var rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    var hits = raycaster.intersectObjects(Object.values(meshes), false);
    if (!hits.length || !bridge) return;
    var id = hits[0].object.userData.id;
    var cfg = configs[id];
    // Action objects (buttons) fire their action in any mode.
    if (cfg && cfg.action && cfg.action.method) {
      bridge.onObjectClicked(id);
      // brief visual press feedback
      var m = meshes[id];
      if (m && m.material && m.material.emissive) {
        m.material.emissive.setHex(0x888888);
        setTimeout(function () { if (m.material && m.material.emissive) m.material.emissive.setHex(0x000000); }, 160);
      }
      return;
    }
    if (design) {
      selectedId = id;
      highlight(id);
      bridge.onObjectSelected(id);
    } else {
      bridge.onObjectClicked(id);
    }
  });

  // ── commands from Python ─────────────────────────────────────────────
  function setMode(d) {
    design = d;
    badgeEl.textContent = d ? "DESIGN" : "RUN";
    badgeEl.className = d ? "" : "run";
    hintEl.textContent = d
      ? "Design mode — click an object to select"
      : "Run mode — click bound objects to call/write";
    highlight(selectedId);
  }

  function handleCommand(jsonStr) {
    var cmd;
    try { cmd = JSON.parse(jsonStr); } catch (e) { return; }
    switch (cmd.type) {
      case "scene":
        if (typeof cmd.design === "boolean") setMode(cmd.design);
        buildScene(cmd.objects);
        var count = (cmd.objects || []).length;
        if (count !== lastCount) {
          fitView();
          lastCount = count;
        }
        break;
      case "mode":
        setMode(!!cmd.design);
        break;
      case "values":
        applyValues(cmd.values);
        break;
      case "select":
        selectedId = cmd.id || null;
        highlight(selectedId);
        break;
      case "anchors":
        applyAnchors(cmd.id, cmd.present || {}, cmd.render || "tube");
        break;
      case "grids":
        (cmd.grids || []).forEach(function (g) { gridMap[g.key] = g; });
        break;
      case "racks":
        renderRacks(cmd.id, cmd.regions || {});
        break;
      case "colors":
        applyColors(cmd.colors || {});
        break;
      case "panel":
        updatePanel(cmd.rows || []);
        break;
      case "anchors-clear":
        clearAllAnchors();
        updatePanel([]);
        break;
    }
  }

  // ── data-driven anchors / grids ──────────────────────────────────────
  function tubeMesh(diam, bodyH) {
    diam = diam || 0.13; bodyH = bodyH || 0.36;
    var capH = Math.min(0.09, bodyH * 0.32), g = new THREE.Group();
    var body = new THREE.Mesh(
      new THREE.CylinderGeometry(diam / 2, diam / 2, bodyH, 12),
      new THREE.MeshStandardMaterial({ color: new THREE.Color("#d64f45") }));
    body.position.y = bodyH / 2;
    var cap = new THREE.Mesh(
      new THREE.CylinderGeometry(diam * 0.62, diam * 0.62, capH, 12),
      new THREE.MeshStandardMaterial({ color: new THREE.Color("#2c3036") }));
    cap.position.y = bodyH + capH / 2;
    g.add(body); g.add(cap);
    return g;
  }
  function holderBox() {
    var m = new THREE.Mesh(
      new THREE.BoxGeometry(0.16, 0.12, 0.16),
      new THREE.MeshStandardMaterial({ color: new THREE.Color("#cbd8a6") }));
    m.position.y = 0.06;
    return m;
  }
  function slotDot() {
    var m = new THREE.Mesh(
      new THREE.CylinderGeometry(0.045, 0.045, 0.03, 8),
      new THREE.MeshStandardMaterial({ color: new THREE.Color("#17211b") }));
    m.position.y = 0.02;
    return m;
  }
  function disposeGroup(g) {
    if (!g) return;
    scene.remove(g);
    g.traverse(function (o) {
      if (o.geometry) o.geometry.dispose();
      if (o.material) o.material.dispose();
    });
  }

  function worldForKey(render, key) {
    var p = anchorPos[key];
    return p ? { x: p.x, y: p.y, z: p.z } : null;
  }

  function buildAnchorItem(render, state, pos) {
    var g = new THREE.Group();
    if (render === "holder") {
      g.add(holderBox());
      if (state === 2) { var t = tubeMesh(0.1, 0.26); t.position.y = 0.1; g.add(t); }
    } else {
      if (state === 2) g.add(tubeMesh());
      else return null;
    }
    g.position.set(pos.x, pos.y + 0.04, pos.z);
    return g;
  }

  function applyAnchors(sourceId, present, render) {
    if (!sourceId) return;
    var bucket = anchorTubes[sourceId] || (anchorTubes[sourceId] = {});
    Object.keys(present).forEach(function (key) {
      var state = present[key];
      var pos = worldForKey(render, key);
      if (!pos || state < 1) {
        if (bucket[key]) { disposeGroup(bucket[key].g); delete bucket[key]; }
        return;
      }
      var sig = render + ":" + state;
      if (bucket[key] && bucket[key].sig === sig) return;
      if (bucket[key]) disposeGroup(bucket[key].g);
      var g = buildAnchorItem(render, state, pos);
      if (g) { scene.add(g); bucket[key] = { g: g, sig: sig }; }
      else delete bucket[key];
    });
    Object.keys(bucket).forEach(function (key) {
      if (!(key in present)) { disposeGroup(bucket[key].g); delete bucket[key]; }
    });
  }

  // Region-based racks: a drawer region is divided among however many racks
  // exist live; racks are stacked back-to-front (along depth), each a 5-column
  // grid sized to its slot count.
  function renderRacks(sourceId, regions) {
    // Only rebuild when the data actually changed — otherwise the racks would
    // be disposed and recreated on every poll (the slow, flickery rebuild).
    var sig = JSON.stringify(regions || {});
    if (rackSig[sourceId] === sig) return;
    rackSig[sourceId] = sig;
    var prev = rackTrays[sourceId] || [];
    prev.forEach(disposeGroup);
    var meshes2 = [];
    Object.keys(regions || {}).forEach(function (regionKey) {
      var region = gridMap[regionKey];
      if (!region) return;
      var racks = regions[regionKey];
      var rackIds = Object.keys(racks).sort(function (a, b) { return (+a) - (+b); });
      var n = rackIds.length || 1;
      var subD = region.d / n;
      var cellX = (region.w * 0.86) / 5;
      var ox = region.x + region.w * 0.07;
      rackIds.forEach(function (rid, ri) {
        var rack = racks[rid];
        var total = rack.total || (rack.occ ? rack.occ.length : 0);
        var rows = Math.max(1, Math.ceil(total / 5));
        var cellZ = Math.min((subD * 0.88) / rows, cellX);
        var oz = region.z + ri * subD + subD * 0.06;
        var usedD = Math.min(subD * 0.95, rows * cellZ + cellZ * 0.4);
        // tray for this rack (full region width, one rack-depth slice)
        var tray = new THREE.Mesh(
          new THREE.BoxGeometry(region.w * 0.92, 0.06, usedD),
          new THREE.MeshStandardMaterial({ color: new THREE.Color("#9aac86") }));
        tray.position.set(region.x + region.w / 2, region.baseY - 0.03,
          oz + usedD / 2 - cellZ * 0.2);
        scene.add(tray); meshes2.push(tray);
        // tube thin enough to leave a gap between neighbours
        var tubeDiam = Math.min(cellX, cellZ) * 0.62;
        (rack.occ || []).forEach(function (slot) {
          var s = slot - 1;
          if (s < 0) return;
          var col = s % 5, row = Math.floor(s / 5);
          var x = ox + (col + 0.5) * cellX;
          var z = oz + (row + 0.5) * cellZ;
          var t = tubeMesh(tubeDiam, 0.2);
          t.position.set(x, region.baseY, z);
          scene.add(t); meshes2.push(t);
        });
      });
    });
    rackTrays[sourceId] = meshes2;
  }

  function clearAllAnchors() {
    Object.keys(anchorTubes).forEach(function (sid) {
      var b = anchorTubes[sid];
      Object.keys(b).forEach(function (k) { disposeGroup(b[k].g); });
    });
    anchorTubes = {};
    Object.keys(rackTrays).forEach(function (sid) {
      rackTrays[sid].forEach(disposeGroup);
    });
    rackTrays = {};
    rackSig = {};
  }

  // ── render loop / resize ─────────────────────────────────────────────
  function resize() {
    var w = window.innerWidth, h = window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);
  resize();

  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();

  // ── connect bridge ───────────────────────────────────────────────────
  // Exposed so an external harness (or tests) can drive the scene without the
  // Qt bridge; harmless in production.
  window.__applySceneCommand = handleCommand;

  function connect() {
    if (typeof QWebChannel === "undefined" || !window.qt || !qt.webChannelTransport) {
      return setTimeout(connect, 100);
    }
    new QWebChannel(qt.webChannelTransport, function (channel) {
      bridge = channel.objects.bridge;
      bridge.toScene.connect(handleCommand);
      bridge.onReady();
    });
  }
  connect();
})();
