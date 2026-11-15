// Map geometry for Cameroon, drawn by hand (no external boundary files: NASA-only data rule).
// - OUTLINE: approximate national border, [lon, lat] points (schematic, not an official boundary)
// - SEEDS: towns of each region (public knowledge); every map pixel takes the region of the
//   nearest town -> approximate regional zones.
// - Each region is ANALYSED at the NASA POWER point of its capital (first seed).
window.CMR = {
  bounds: { lonMin: 8.2, lonMax: 16.6, latMin: 1.4, latMax: 13.3 },
  outline: [
    [14.17, 13.08], [14.55, 12.85], [14.65, 12.2], [15.05, 12.1], [15.1, 11.6], [15.05, 11.0],
    [15.25, 10.55], [15.65, 10.05], [15.2, 9.98], [14.75, 9.95], [14.0, 9.62], [14.35, 9.15],
    [15.0, 8.6], [15.45, 7.7], [15.15, 7.45], [14.8, 6.4], [14.45, 5.95], [14.6, 5.3],
    [14.55, 4.6], [15.1, 4.0], [15.3, 3.6], [15.95, 3.1], [16.2, 2.2], [16.05, 1.65],
    [15.5, 1.95], [14.6, 2.15], [13.3, 2.17], [11.35, 2.17], [9.8, 2.35], [9.9, 2.95],
    [9.75, 3.55], [9.6, 3.85], [9.2, 4.0], [8.95, 4.1], [8.6, 4.5], [8.55, 4.75], [8.85, 5.2],
    [8.85, 5.85], [9.45, 6.45], [10.15, 6.95], [10.65, 6.95], [11.1, 6.45], [11.55, 6.95],
    [11.85, 7.6], [12.05, 8.2], [12.25, 8.45], [12.75, 8.75], [12.95, 9.4], [13.25, 10.05],
    [13.55, 10.75], [13.8, 11.05], [14.1, 11.55], [14.2, 12.2], [14.15, 12.8],
  ],
  // [lat, lon]; first entry = regional capital = NASA POWER analysis point
  seeds: {
    extreme_nord: [[10.59, 14.32], [12.08, 15.03], [10.74, 13.8], [10.34, 15.23], [11.05, 14.14], [10.1, 14.45]],
    nord: [[9.3, 13.4], [9.93, 13.95], [8.48, 13.24], [8.4, 14.17], [7.77, 15.36], [8.67, 14.18]],
    adamaoua: [[7.32, 13.58], [6.47, 12.63], [6.52, 14.29], [6.75, 11.82], [7.37, 12.65]],
    nord_ouest: [[5.96, 10.15], [6.38, 10.07], [6.63, 10.67], [6.2, 10.68], [6.0, 10.42]],
    ouest: [[5.48, 10.42], [5.45, 10.05], [5.73, 10.9], [5.15, 10.52], [5.63, 10.25]],
    sud_ouest: [[4.16, 9.24], [4.64, 9.45], [5.76, 9.31], [4.02, 9.21], [4.95, 8.87]],
    littoral: [[4.05, 9.7], [3.8, 10.13], [4.95, 9.94], [4.46, 9.97]],
    centre: [[3.87, 11.52], [4.75, 11.23], [4.68, 12.37], [3.52, 11.5], [5.53, 12.32], [4.45, 11.63]],
    est: [[4.58, 13.68], [4.43, 14.36], [3.51, 15.05], [3.98, 13.18], [5.88, 14.55], [2.03, 15.21], [3.16, 13.62]],
    sud: [[2.9, 11.15], [2.94, 9.91], [2.93, 11.98], [2.38, 11.27], [2.67, 12.67], [2.37, 9.82]],
  },
  neighbours: [
    { fr: "NIGERIA", en: "NIGERIA", lat: 9.0, lon: 10.2 },
    { fr: "TCHAD", en: "CHAD", lat: 11.2, lon: 16.0 },
    { fr: "RCA", en: "CAR", lat: 6.6, lon: 16.0 },
    { fr: "GABON", en: "GABON", lat: 1.7, lon: 12.2 },
    { fr: "CONGO", en: "CONGO", lat: 1.6, lon: 15.2 },
    { fr: "GUINÉE ÉQ.", en: "EQ. GUINEA", lat: 1.7, lon: 10.4 },
    { fr: "Océan Atlantique", en: "Atlantic Ocean", lat: 3.0, lon: 8.75, italic: true },
    { fr: "Lac Tchad", en: "Lake Chad", lat: 13.2, lon: 14.75, italic: true },
  ],
};

CMR.inside = function inside(lon, lat) {
  const poly = CMR.outline;
  let isIn = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) isIn = !isIn;
  }
  return isIn;
};

// Raster of region indexes (-1 = outside Cameroon), computed once.
CMR.raster = function raster(step = 0.04) {
  const { lonMin, lonMax, latMin, latMax } = CMR.bounds;
  const ids = Object.keys(CMR.seeds);
  const seeds = ids.flatMap((id, k) => CMR.seeds[id].map(([lat, lon]) => ({ k, lat, lon })));
  const cols = Math.ceil((lonMax - lonMin) / step), rows = Math.ceil((latMax - latMin) / step);
  const grid = new Int8Array(cols * rows).fill(-1);
  for (let r = 0; r < rows; r++) {
    const lat = latMax - (r + 0.5) * step;
    for (let c = 0; c < cols; c++) {
      const lon = lonMin + (c + 0.5) * step;
      if (!CMR.inside(lon, lat)) continue;
      let best = 0, bestD = Infinity;
      for (const s of seeds) {
        const d = (s.lat - lat) ** 2 + (s.lon - lon) ** 2;
        if (d < bestD) { bestD = d; best = s.k; }
      }
      grid[r * cols + c] = best;
    }
  }
  // label point of each region = average of its pixels
  const sums = ids.map(() => ({ lat: 0, lon: 0, n: 0 }));
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const k = grid[r * cols + c];
    if (k < 0) continue;
    sums[k].lat += latMax - (r + 0.5) * step; sums[k].lon += lonMin + (c + 0.5) * step; sums[k].n++;
  }
  const labels = Object.fromEntries(ids.map((id, k) => [id, { lat: sums[k].lat / sums[k].n, lon: sums[k].lon / sums[k].n }]));
  return { step, cols, rows, grid, ids, labels };
};
