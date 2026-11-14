export const CSV_HEADER = 'zone,year,value,latitude,longitude,unit';
export const MAX_FILE_BYTES = 1_000_000;

function parseRows(text) {
  const rows = [];
  let row = [], field = '', quoted = false, closed = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (quoted) {
      if (char === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (char === '"') { quoted = false; closed = true; }
      else field += char;
    } else if (char === '"' && !field && !closed) {
      quoted = true;
    } else if (char === ',' || char === '\n' || char === '\r') {
      row.push(field);
      field = '';
      closed = false;
      if (char !== ',') {
        if (char === '\r' && text[i + 1] === '\n') i++;
        rows.push(row);
        row = [];
      }
    } else {
      if (closed || char === '"') throw new Error('CSV : guillemets mal places.');
      field += char;
    }
  }
  if (quoted) throw new Error('CSV : guillemets non fermes.');
  if (field || row.length || closed) rows.push([...row, field]);
  return rows.filter((cells) => cells.some((cell) => cell.trim()));
}

function numberValue(value, field, line) {
  if (!value.trim() || !/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim())) {
    throw new Error(`Ligne ${line} : ${field} doit etre un nombre non vide (point decimal).`);
  }
  const result = Number(value);
  if (!Number.isFinite(result)) throw new Error(`Ligne ${line} : ${field} non fini.`);
  return result;
}

export function parseCsv(text) {
  if (new TextEncoder().encode(text).length > MAX_FILE_BYTES) throw new Error('CSV trop volumineux : maximum 1 Mo.');
  const rows = parseRows(text.replace(/^\uFEFF/, ''));
  if (rows.length < 2 || rows[0].map((cell) => cell.trim()).join(',') !== CSV_HEADER) {
    throw new Error(`En-tete attendu : ${CSV_HEADER}`);
  }
  if (rows.length > 5001) throw new Error('Maximum 5 000 observations.');
  const zones = new Map();
  for (const [index, cells] of rows.slice(1).entries()) {
    const line = index + 2;
    if (cells.length !== 6) throw new Error(`Ligne ${line} : 6 colonnes attendues.`);
    const [zone, yearText, valueText, latText, lonText, unit] = cells.map((cell) => cell.trim());
    if (!zone || zone.length > 100 || !unit || unit.length > 30 || /[\u0000-\u001f]/.test(zone + unit)) {
      throw new Error(`Ligne ${line} : zone et unite obligatoires, sans caracteres de controle.`);
    }
    const year = numberValue(yearText, 'year', line);
    const value = numberValue(valueText, 'value', line);
    const latitude = numberValue(latText, 'latitude', line);
    const longitude = numberValue(lonText, 'longitude', line);
    if (!Number.isInteger(year) || year < 1900 || year > 2100) throw new Error(`Ligne ${line} : annee entiere entre 1900 et 2100 requise.`);
    if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) throw new Error(`Ligne ${line} : coordonnees hors limites.`);
    if (!zones.has(zone)) zones.set(zone, { name: zone, latitude, longitude, unit, observations: [] });
    const entry = zones.get(zone);
    if (entry.unit !== unit || entry.latitude !== latitude || entry.longitude !== longitude) {
      throw new Error(`Ligne ${line} : unite ou coordonnees incoherentes pour ${zone}.`);
    }
    if (entry.observations.some((item) => item.year === year)) throw new Error(`Ligne ${line} : annee en double pour ${zone}.`);
    entry.observations.push({ year, value });
  }
  if (zones.size > 50) throw new Error('Maximum 50 zones.');
  const result = [...zones.values()];
  if (new Set(result.map((zone) => zone.unit)).size > 1) throw new Error('Un seul indicateur et une seule unite par fichier.');
  for (const zone of result) {
    if (zone.observations.length < 3) throw new Error(`${zone.name} : au moins 3 annees distinctes requises.`);
    zone.observations.sort((a, b) => a.year - b.year);
  }
  return result;
}

export function summarize(observations) {
  if (observations.length < 3 || observations.some((item) => !Number.isFinite(item.value) || !Number.isInteger(item.year))) {
    throw new Error('Analyse : au moins 3 observations annuelles valides requises.');
  }
  const sorted = [...observations].sort((a, b) => a.year - b.year);
  if (new Set(sorted.map((item) => item.year)).size !== sorted.length) throw new Error('Analyse : annees en double.');
  const first = sorted[0], last = sorted.at(-1);
  const meanYear = sorted.reduce((sum, item) => sum + item.year, 0) / sorted.length;
  const meanValue = sorted.reduce((sum, item) => sum + item.value, 0) / sorted.length;
  const denominator = sorted.reduce((sum, item) => sum + (item.year - meanYear) ** 2, 0);
  const slope = sorted.reduce((sum, item) => sum + (item.year - meanYear) * (item.value - meanValue), 0) / denominator;
  const fitted = (year) => meanValue + slope * (year - meanYear);
  if (![slope, meanValue, fitted(first.year), fitted(last.year)].every(Number.isFinite)) {
    throw new Error('Analyse : valeurs trop extremes pour un calcul fiable.');
  }
  return {
    firstYear: first.year, lastYear: last.year, count: sorted.length,
    slope, change: last.value - first.value, meanValue,
    missingYears: last.year - first.year + 1 - sorted.length,
    fitted,
  };
}

export function parsePowerAnnual(payload) {
  const parameter = payload?.properties?.parameter?.T2M;
  const units = payload?.parameters?.T2M?.units;
  const sources = payload?.header?.sources;
  const coordinates = payload?.geometry?.coordinates;
  if (!parameter || units !== 'C' || !Array.isArray(sources) || !sources.includes('MERRA2')
      || !Array.isArray(coordinates) || coordinates.length < 2
      || !Number.isFinite(coordinates[0]) || !Number.isFinite(coordinates[1])) {
    throw new Error('La reponse NASA POWER ne contient pas les donnees T2M/MERRA-2 attendues.');
  }
  const observations = Object.entries(parameter)
    .filter(([key]) => /^\d{4}13$/.test(key))
    .map(([key, value]) => ({ year: Number(key.slice(0, 4)), value }))
    .filter((item) => Number.isFinite(item.value) && item.value !== -999);
  if (observations.length < 3) throw new Error('NASA POWER a retourne moins de trois annees annuelles valides.');
  observations.sort((a, b) => a.year - b.year);
  return [{
    name: 'Yaounde · point MERRA-2',
    latitude: coordinates[1],
    longitude: coordinates[0],
    unit: units,
    observations,
  }];
}

export function demoCsv() {
  const zones = [
    { name: 'Yaounde Centre (scenario)', latitude: 3.87, longitude: 11.52, base: 29, slope: 0.09 },
    { name: 'Yaounde Nord (scenario)', latitude: 3.94, longitude: 11.51, base: 28, slope: 0.04 },
    { name: 'Yaounde Ouest (scenario)', latitude: 3.86, longitude: 11.44, base: 27, slope: -0.025 },
  ];
  const rows = [CSV_HEADER];
  for (const zone of zones) {
    for (let year = 2005; year <= 2024; year++) {
      const value = zone.base + zone.slope * (year - 2005) + Math.sin((year - 2005) * 1.7) * 0.35;
      rows.push(`${zone.name},${year},${value.toFixed(3)},${zone.latitude},${zone.longitude},degC`);
    }
  }
  return rows.join('\n') + '\n';
}
