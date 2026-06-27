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

  function buildScene(objects) {
    Object.keys(meshes).forEach(function (id) { disposeMesh(meshes[id]); });
    meshes = {};
    configs = {};
    (objects || []).forEach(function (cfg) {
      configs[cfg.id] = cfg;
      var mat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(cfg.color || "#6366f1"),
        metalness: 0.1, roughness: 0.6,
      });
      var mesh = new THREE.Mesh(makeGeometry(cfg.shape, cfg.size), mat);
      mesh.position.set(cfg.x, cfg.y, cfg.z);
      mesh.userData.id = cfg.id;
      mesh.userData.baseColor = cfg.color || "#6366f1";
      scene.add(mesh);
      meshes[cfg.id] = mesh;
    });
    highlight(selectedId);
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
          mesh.scale.y = 0.2 + norm(cfg, v) * 2.5;
          break;
        case "rotateY":
          mesh.rotation.y = norm(cfg, v) * Math.PI * 2;
          break;
        case "posY":
          mesh.position.y = cfg.y + norm(cfg, v) * 3;
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
    }
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
