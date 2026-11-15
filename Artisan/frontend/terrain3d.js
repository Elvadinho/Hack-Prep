// 3D "risk terrain" of Cameroon for the home hero (three.js, no build step).
// Every map cell becomes a glowing column; a region's columns rise to its risk score (0-100)
// and take its risk colour. Drag to rotate, hover for the score, click to open the synthesis.
// The geometry is the app's own hand-drawn map (CMR in cameroon.js), so no external boundary data.
window.Terrain3D = (function () {
  const HEIGHT = 1.25;  // world height of a 100/100 region
  const FLOOR = 0.05;   // height of a 0/100 region, so the country is always visible
  const EMPTY = "#1a2640";

  function create(host, labelsHost, { onHover, onPick } = {}) {
    if (!window.THREE) return null;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    } catch (error) {
      return null;  // no WebGL: the page keeps working without the 3D scene
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    // colour-managed output, so the risk colours look exactly like the CSS legend
    if (THREE.ColorManagement) THREE.ColorManagement.legacyMode = false;
    renderer.outputEncoding = THREE.sRGBEncoding;
    host.appendChild(renderer.domElement);
    renderer.domElement.setAttribute("aria-hidden", "true");

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x000000, 22, 40);
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 200);

    // ------------------------------------------------ map cells -> instanced columns
    const R = CMR.raster(0.085);
    const { lonMin, lonMax, latMin, latMax } = CMR.bounds;
    const lon0 = (lonMin + lonMax) / 2, lat0 = (latMin + latMax) / 2;
    const toX = (lon) => lon - lon0, toZ = (lat) => -(lat - lat0);
    const cells = [];
    for (let r = 0; r < R.rows; r++) for (let c = 0; c < R.cols; c++) {
      const k = R.grid[r * R.cols + c];
      if (k < 0) continue;
      cells.push({ k, x: toX(lonMin + (c + 0.5) * R.step), z: toZ(latMax - (r + 0.5) * R.step) });
    }
    const box = new THREE.BoxGeometry(R.step * 0.84, 1, R.step * 0.84);
    box.translate(0, 0.5, 0);
    const material = new THREE.MeshStandardMaterial({ roughness: 0.55, metalness: 0.05 });
    const columns = new THREE.InstancedMesh(box, material, cells.length);
    columns.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    const group = new THREE.Group();
    group.add(columns);
    scene.add(group);

    const regions = R.ids.map(() => ({ height: 0, target: FLOOR, color: new THREE.Color(EMPTY) }));
    const matrix = new THREE.Matrix4(), tint = new THREE.Color(), white = new THREE.Color("#ffffff");
    let hoverK = -1;
    function writeColumns() {
      cells.forEach((cell, i) => {
        const region = regions[cell.k];
        matrix.makeScale(1, Math.max(region.height, 0.001), 1);
        matrix.setPosition(cell.x, 0, cell.z);
        columns.setMatrixAt(i, matrix);
        tint.copy(region.color);
        if (cell.k === hoverK) tint.lerp(white, 0.35);
        columns.setColorAt(i, tint);
      });
      columns.instanceMatrix.needsUpdate = true;
      if (columns.instanceColor) columns.instanceColor.needsUpdate = true;
    }

    // ------------------------------------------------ context: grid floor, border, beams, stars, scan
    const grid = new THREE.GridHelper(18, 36, 0x2e2e2e, 0x161616);
    grid.material.transparent = true;
    grid.material.opacity = 0.55;
    grid.position.y = -0.002;
    group.add(grid);

    const borderPoints = CMR.outline.map(([lon, lat]) => new THREE.Vector3(toX(lon), 0.01, toZ(lat)));
    group.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(borderPoints),
      new THREE.LineBasicMaterial({ color: 0xededed, transparent: true, opacity: 0.95 })));
    const halo = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(borderPoints),
      new THREE.LineBasicMaterial({ color: 0xededed, transparent: true, opacity: 0.18 }));
    halo.scale.set(1.015, 1, 1.015);
    group.add(halo);

    const beamMaterial = new THREE.LineBasicMaterial({ color: 0xededed, transparent: true, opacity: 0.5 });
    const dotMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const beams = R.ids.map((id) => {
      const [lat, lon] = CMR.seeds[id][0];  // regional capital = NASA analysis point
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 1, 0)]), beamMaterial);
      line.position.set(toX(lon), 0, toZ(lat));
      const dot = new THREE.Mesh(new THREE.SphereGeometry(0.045, 12, 12), dotMaterial);
      dot.position.copy(line.position);
      group.add(line, dot);
      return { line, dot };
    });

    const starCount = 1600, starPositions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount; i++) {
      const u = Math.random() * 2 - 1, t = Math.random() * Math.PI * 2, radius = 40 + Math.random() * 40;
      const s = Math.sqrt(1 - u * u);
      starPositions.set([radius * s * Math.cos(t), Math.abs(radius * u) * 0.9 + 2, radius * s * Math.sin(t)], i * 3);
    }
    const starGeometry = new THREE.BufferGeometry();
    starGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
    const stars = new THREE.Points(starGeometry, new THREE.PointsMaterial({ color: 0xffffff, size: 0.08, transparent: true, opacity: 0.55, fog: false }));
    scene.add(stars);

    // satellite orbit: a red dashed ellipse around the country with a satellite moving along it
    const orbitCurve = new THREE.EllipseCurve(0, 0, 5.3, 3.5, 0, Math.PI * 2, false, 0.35);
    const orbitPoints = orbitCurve.getPoints(220).map((p) => new THREE.Vector3(p.x, 0.02, p.y));
    const orbitLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints(orbitPoints),
      new THREE.LineDashedMaterial({ color: 0xe5432f, dashSize: 0.18, gapSize: 0.12, transparent: true, opacity: 0.85 }));
    orbitLine.computeLineDistances();
    const orbit = new THREE.Group();
    orbit.add(orbitLine);
    orbit.rotation.set(0.38, 0, 0.12);  // tilted plane, like an orbit drawn on a technical chart
    orbit.position.y = 0.9;
    const satellite = new THREE.Mesh(new THREE.SphereGeometry(0.075, 14, 14), new THREE.MeshBasicMaterial({ color: 0xe5432f }));
    orbit.add(satellite);
    group.add(orbit);
    const satLabel = document.createElement("div");
    satLabel.className = "scene-label sat";
    satLabel.textContent = "NASA POWER";
    labelsHost.appendChild(satLabel);
    const satWorld = new THREE.Vector3();

    scene.add(new THREE.HemisphereLight(0xffffff, 0x202020, 1.15));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(-5, 9, 6);
    const rim = new THREE.DirectionalLight(0xffffff, 0.25);
    rim.position.set(6, 3, -8);
    scene.add(sun, rim);

    // ------------------------------------------------ labels (DOM, projected every frame)
    const labels = R.ids.map((id) => {
      const node = document.createElement("div");
      node.className = "scene-label";
      labelsHost.appendChild(node);
      const p = R.labels[id];
      return { node, position: new THREE.Vector3(toX(p.lon), 0, toZ(p.lat)) };
    });

    // ------------------------------------------------ camera, interaction
    const view = { yaw: -0.3, pitch: 0.7, radius: 21 };
    let dragging = false, moved = 0, lastX = 0, lastY = 0, lastInteraction = -1e9, time = 0, last = 0;
    const canvas = renderer.domElement, ray = new THREE.Raycaster(), pointer = new THREE.Vector2();

    function regionUnder(event) {
      const rect = canvas.getBoundingClientRect();
      pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
      ray.setFromCamera(pointer, camera);
      const hit = ray.intersectObject(columns)[0];
      return hit ? cells[hit.instanceId].k : -1;
    }
    canvas.addEventListener("pointerdown", (event) => {
      dragging = true; moved = 0; lastX = event.clientX; lastY = event.clientY;
      canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", (event) => {
      if (dragging) {
        const dx = event.clientX - lastX, dy = event.clientY - lastY;
        moved += Math.abs(dx) + Math.abs(dy);
        view.yaw -= dx * 0.006;
        view.pitch = Math.min(1.3, Math.max(0.4, view.pitch - dy * 0.004));
        lastX = event.clientX; lastY = event.clientY; lastInteraction = time;
        return;
      }
      const k = regionUnder(event);
      if (k !== hoverK) { hoverK = k; writeColumns(); }
      onHover?.(k >= 0 ? R.ids[k] : null, event);
    });
    canvas.addEventListener("pointerup", (event) => {
      dragging = false;
      if (moved < 6) {
        const k = regionUnder(event);
        if (k >= 0) onPick?.(R.ids[k]);
      }
    });
    canvas.addEventListener("pointerleave", () => {
      if (hoverK !== -1) { hoverK = -1; writeColumns(); }
      onHover?.(null);
    });

    function resize() {
      const w = host.clientWidth, h = host.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      // wide screens: the hero text sits on the left, so the map is drawn in the right half
      camera.setViewOffset(w, h, w > 960 ? -w * 0.2 : 0, 0, w, h);
      view.radius = w > 960 ? 21 : 25;
      camera.updateProjectionMatrix();
    }
    new ResizeObserver(resize).observe(host);
    resize();

    // ------------------------------------------------ animation loop
    const projected = new THREE.Vector3();
    let running = true;
    function frame(now) {
      if (!running) return;
      requestAnimationFrame(frame);
      if (document.hidden || !host.offsetParent) { last = now; return; }  // home not shown: no work
      const dt = Math.min(0.05, (now - (last || now)) / 1000);
      last = now;
      time += dt;

      let changed = false;
      for (const region of regions) {
        const gap = region.target - region.height;
        if (Math.abs(gap) > 0.0005) { region.height += reduced ? gap : gap * Math.min(1, dt * 3.2); changed = true; }
      }
      if (changed) writeColumns();
      beams.forEach((beam, k) => {
        const top = regions[k].height + 0.75;
        beam.line.scale.y = top;
        beam.dot.position.y = top;
      });

      if (!reduced) {
        if (!dragging && time - lastInteraction > 4) view.yaw += dt * 0.07;  // slow idle orbit
        stars.rotation.y = time * 0.004;
      }
      camera.position.set(
        view.radius * Math.sin(view.pitch) * Math.sin(view.yaw),
        view.radius * Math.cos(view.pitch),
        view.radius * Math.sin(view.pitch) * Math.cos(view.yaw));
      camera.lookAt(0, 0.5, 0.9);

      const point = orbitCurve.getPoint(reduced ? 0.12 : (time * 0.025) % 1);  // reduced motion: satellite stays still
      satellite.position.set(point.x, 0.02, point.y);
      satellite.getWorldPosition(satWorld);
      const w = host.clientWidth, h = host.clientHeight;
      satWorld.project(camera);
      satLabel.style.transform = `translate(${((satWorld.x + 1) / 2) * w + 10}px, ${((1 - satWorld.y) / 2) * h}px) translate(0, -50%)`;
      labels.forEach((label, k) => {
        projected.copy(label.position);
        projected.y = regions[k].height + 0.12;
        projected.project(camera);
        label.node.style.opacity = projected.z < 1 ? "1" : "0";
        const x = ((projected.x + 1) / 2) * w, y = ((1 - projected.y) / 2) * h;
        label.node.style.transform = `translate(${x}px, ${y}px) translate(-50%, -100%)`;
      });
      renderer.render(scene, camera);
    }
    requestAnimationFrame(frame);
    writeColumns();

    return {
      // rows: { regionId: { score, level, name } }
      update(rows) {
        R.ids.forEach((id, k) => {
          const row = rows[id];
          regions[k].target = row ? FLOOR + (row.score / 100) * HEIGHT : FLOOR;
          regions[k].color = new THREE.Color(row ? LEVEL_COLORS[row.level] : EMPTY);
          const score = document.createElement("b");
          score.textContent = row ? String(row.score) : "…";
          labels[k].node.replaceChildren(document.createTextNode(row?.name || id), score);
        });
        writeColumns();
      },
      destroy() { running = false; renderer.dispose(); },
    };
  }

  return { create };
})();
