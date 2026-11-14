import { demoCsv, parseCsv, summarize, parsePowerAnnual, MAX_FILE_BYTES } from './analysis.js';

const $ = (id) => document.getElementById(id);
let zones = parseCsv(demoCsv());
let datasetMode = 'synthetic';
let source = 'Scenario synthetique reproductible';
let indicator = 'Temperature de surface illustrative';
const svgNS = 'http://www.w3.org/2000/svg';
const format = (value) => new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 3 }).format(value);

function svgElement(parent, tag, attributes = {}, text) {
  const element = document.createElementNS(svgNS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (text !== undefined) element.textContent = text;
  parent.append(element);
  return element;
}

function showError(message) {
  $('error').textContent = message;
  $('error').hidden = !message;
}

function options(element, values) {
  element.replaceChildren(...values.map(([value, label]) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    return option;
  }));
}

function setYears() {
  const years = [...new Set(zones.flatMap((zone) => zone.observations.map((item) => item.year)))].sort((a, b) => a - b);
  const values = years.map((year) => [String(year), String(year)]);
  options($('start'), values);
  options($('end'), values);
  $('start').value = values[0][0];
  $('end').value = values.at(-1)[0];
}

function selectedObservations(zone) {
  const start = Number($('start').value);
  const end = Number($('end').value);
  return zone.observations.filter((item) => item.year >= start && item.year <= end);
}

function renderComparison() {
  const comparison = $('comparison');
  comparison.replaceChildren();
  $('comparison-period').textContent = `${$('start').value}–${$('end').value}`;
  zones.forEach((zone, index) => {
    const observations = selectedObservations(zone);
    const stats = observations.length >= 3 ? summarize(observations) : null;
    const row = document.createElement('tr');
    const cells = [
      zone.name,
      stats ? `${format(stats.slope * 10)} ${zone.unit}/10 ans` : 'Donnees insuffisantes',
      stats ? `${format(stats.change)} ${zone.unit}` : '—',
      stats ? String(stats.count) : `${observations.length} (minimum : 3)`,
      stats ? String(stats.missingYears) : '—',
    ];
    for (const [cellIndex, text] of cells.entries()) {
      const cell = document.createElement('td');
      cell.textContent = text;
      if (cellIndex === 0) cell.className = 'zone-name';
      row.append(cell);
    }
    const actionCell = document.createElement('td');
    const action = document.createElement('button');
    action.type = 'button';
    action.className = 'table-action secondary';
    action.textContent = index === Number($('zone').value) ? 'Selectionnee' : 'Explorer';
    action.setAttribute('aria-label', `Explorer la serie de ${zone.name}`);
    action.disabled = index === Number($('zone').value);
    action.addEventListener('click', () => {
      $('zone').value = String(index);
      render();
    });
    actionCell.append(action);
    row.append(actionCell);
    comparison.append(row);
  });
}

function renderMap() {
  const map = $('map');
  map.replaceChildren();
  const latitudes = zones.map((zone) => zone.latitude);
  const longitudes = zones.map((zone) => zone.longitude);
  const latMin = Math.min(...latitudes), lonMin = Math.min(...longitudes);
  const latRange = Math.max(...latitudes) - latMin || 0.1;
  const lonRange = Math.max(...longitudes) - lonMin || 0.1;
  for (let x = 30; x < 600; x += 60) svgElement(map, 'line', { x1: x, x2: x, y1: 0, y2: 320, stroke: '#e1eae2' });
  for (let y = 20; y < 320; y += 50) svgElement(map, 'line', { x1: 0, x2: 600, y1: y, y2: y, stroke: '#e1eae2' });
  svgElement(map, 'text', { x: 22, y: 25 }, 'N ↑ · Emplacements declares, non verifies');
  zones.forEach((zone, index) => {
    const x = zones.length === 1 ? 300 : 70 + (zone.longitude - lonMin) / lonRange * 440;
    const y = zones.length === 1 ? 160 : 270 - (zone.latitude - latMin) / latRange * 205;
    const observations = selectedObservations(zone);
    const stats = observations.length >= 3 ? summarize(observations) : null;
    const color = !stats || Math.abs(stats.slope) < 1e-10 ? '#7c8982' : stats.slope > 0 ? '#b98038' : '#407a9c';
    const group = svgElement(map, 'g', { class: `map-point ${index === Number($('zone').value) ? 'selected' : ''}`, role: 'button', tabindex: 0, 'aria-label': `Explorer ${zone.name}` });
    svgElement(group, 'title', {}, `${zone.name} (${zone.latitude}, ${zone.longitude})`);
    svgElement(group, 'circle', { cx: x, cy: y, r: 16, fill: color });
    svgElement(group, 'text', { x, y: y + 35, 'text-anchor': 'middle' }, zone.name.length > 26 ? zone.name.slice(0, 24) + '…' : zone.name);
    const select = () => { $('zone').value = String(index); render(); };
    group.addEventListener('click', select);
    group.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(); }
    });
  });
}

function renderChart(observations, stats, unit) {
  const chart = $('chart');
  chart.replaceChildren();
  if (!stats) { svgElement(chart, 'text', { x: 45, y: 150 }, 'Selectionner au moins trois annees observees.'); return; }
  const values = observations.map((item) => item.value);
  const min = Math.min(...values), max = Math.max(...values);
  const padding = (max - min) * 0.15 || 1;
  const x = (year) => 70 + (year - stats.firstYear) / (stats.lastYear - stats.firstYear) * 485;
  const y = (value) => 260 - (value - (min - padding)) / (max - min + padding * 2) * 215;
  svgElement(chart, 'title', {}, `${indicator}, ${stats.firstYear} a ${stats.lastYear}, ${unit}`);
  for (let i = 0; i <= 4; i++) {
    const value = min - padding + (max - min + padding * 2) * i / 4;
    svgElement(chart, 'line', { x1: 70, x2: 555, y1: y(value), y2: y(value), stroke: '#dce6df' });
    svgElement(chart, 'text', { x: 62, y: y(value) + 4, 'text-anchor': 'end' }, format(value));
  }
  svgElement(chart, 'text', { x: 20, y: 23 }, unit);
  svgElement(chart, 'text', { x: 70, y: 295 }, String(stats.firstYear));
  svgElement(chart, 'text', { x: 555, y: 295, 'text-anchor': 'end' }, String(stats.lastYear));
  svgElement(chart, 'line', { x1: x(stats.firstYear), x2: x(stats.lastYear), y1: y(stats.fitted(stats.firstYear)), y2: y(stats.fitted(stats.lastYear)), stroke: '#bc7f32', 'stroke-width': 2, 'stroke-dasharray': '7 5' });
  observations.forEach((item, index) => {
    const previous = observations[index - 1];
    if (previous && previous.year + 1 === item.year) svgElement(chart, 'line', { x1: x(previous.year), x2: x(item.year), y1: y(previous.value), y2: y(item.value), stroke: '#245e4d', 'stroke-width': 2 });
    const point = svgElement(chart, 'circle', { cx: x(item.year), cy: y(item.value), r: 4, fill: '#245e4d' });
    svgElement(point, 'title', {}, `${item.year} : ${format(item.value)} ${unit}`);
  });
}

function renderMethodPrudence(zone, stats) {
  const methodPrudence = $('method-prudence');
  if (!stats || !zone) {
    methodPrudence.textContent = 'La periode active est insuffisante pour une lecture inferentielle. Le prototype garde une interpretation descriptive et n’affiche pas de p-value.';
    return;
  }
  const length = stats.count;
  const detail = datasetMode === 'nasa'
    ? 'La serie NASA POWER est une tendance de grille MERRA-2, pas une mesure locale in situ.'
    : datasetMode === 'csv'
      ? 'La serie importee est traitee comme un signal descriptif et n’a pas ete valitee statistically.'
      : 'Le scenario de demonstration reste une base illustrative et un support de discussion, sans preuve locale de risque.';
  methodPrudence.textContent = `Pente descriptive sur ${length} observations : ${format(stats.slope * 10)} ${zone.unit}/10 ans. ${detail} Le prototype n’affiche ni p-value ni conclusion de significativite statistique tant qu’un protocole valide n’a pas ete confirme.`;
}

function renderSkills() {
  $('skills').replaceChildren();
  if (datasetMode !== 'synthetic') {
    const note = document.createElement('p');
    note.textContent = 'Donnees importees : correspondances avec les metiers non configurees. Une validation humaine et scientifique est necessaire.';
    $('skills').append(note);
    return;
  }
  for (const [title, description] of [
    ['Couverture et isolation', 'Piste illustrative : ameliorer le confort thermique des batiments, apres diagnostic local.'],
    ['Menuiserie et amenagement', 'Piste illustrative : ombrage, ventilation et protections adaptees au contexte.'],
    ['Maconnerie', 'Piste illustrative : renovation et choix de materiaux, avec expertise du batiment.'],
  ]) {
    const card = document.createElement('article');
    card.className = 'skill';
    const heading = document.createElement('strong');
    heading.textContent = title;
    const paragraph = document.createElement('p');
    paragraph.className = 'small';
    paragraph.textContent = description;
    card.append(heading, paragraph);
    $('skills').append(card);
  }
}

function render() {
  const zone = zones[Number($('zone').value)];
  const start = Number($('start').value);
  const end = Number($('end').value);
  const validPeriod = Number.isInteger(start) && Number.isInteger(end) && start <= end;
  const observations = selectedObservations(zone);
  const stats = validPeriod && observations.length >= 3 ? summarize(observations) : null;
  showError(stats ? '' : 'Periode invalide ou insuffisante : selectionnez au moins trois annees observees.');
  $('provenance').textContent = datasetMode === 'synthetic'
    ? 'DONNEES FICTIVES — Scenario de demonstration genere mathematiquement, sans observations NASA ni diagnostic reel de Yaounde.'
    : datasetMode === 'nasa'
      ? 'DONNEES NASA POWER — T2M annuel, source MERRA-2, point 3.87°N / 11.52°E. Resolution de grille native, pas une mesure de quartier. Serie indicative, sans validation locale.'
      : `DONNEES IMPORTEES, NON VERIFIEES — Source declaree : ${source}. Indicateur : ${indicator}. Aucune certification NASA ni validation scientifique.`;
  $('slope').textContent = stats ? `${format(stats.slope * 10)} ${zone.unit}/10 ans` : '—';
  $('change').textContent = stats ? `${format(stats.change)} ${zone.unit}` : '—';
  $('coverage').textContent = stats ? `${stats.count} observations` : '—';
  $('missing').textContent = stats ? `${stats.firstYear}–${stats.lastYear} · ${stats.missingYears} annee(s) absente(s)` : 'Analyse non disponible';
  $('chart-caption').textContent = `${indicator} · ${zone.name} · ${zone.unit}`;
  renderMethodPrudence(zone, stats);
  renderComparison();
  renderMap();
  renderChart(observations, stats, zone.unit);
  renderSkills();
}

function initialize() {
  options($('zone'), zones.map((zone, index) => [String(index), zone.name]));
  setYears();
  render();
}

$('zone').addEventListener('change', render);
$('start').addEventListener('change', render);
$('end').addEventListener('change', render);
$('nasa-load').addEventListener('click', async () => {
  const button = $('nasa-load');
  button.disabled = true;
  showError('');
  try {
    const response = await fetch('/api/nasa/power');
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.error ?? `Chargement NASA impossible (HTTP ${response.status}).`);
    }
    const loaded = parsePowerAnnual(await response.json());
    for (const zone of loaded) summarize(zone.observations);
    zones = loaded;
    datasetMode = 'nasa';
    source = 'NASA POWER · MERRA-2';
    indicator = 'Temperature annuelle a 2 m (T2M)';
    initialize();
  } catch (error) {
    showError(error instanceof Error ? error.message : 'Chargement NASA impossible.');
  } finally {
    button.disabled = false;
  }
});
$('demo-reset').addEventListener('click', () => {
  zones = parseCsv(demoCsv()); datasetMode = 'synthetic';
  source = 'Scenario synthetique reproductible'; indicator = 'Temperature de surface illustrative';
  $('import-form').reset(); initialize();
});
$('template').addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([demoCsv()], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url; link.download = 'DEMONSTRATION-FICTIVE.csv'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$('import-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = $('csv').files[0];
  const declaredSource = $('source').value.trim();
  const declaredIndicator = $('indicator').value.trim();
  const button = $('import-form').querySelector('button[type="submit"]');
  try {
    if (!declaredSource || !declaredIndicator) throw new Error('Renseignez la source et le nom de l’indicateur.');
    if (!file) throw new Error('Selectionnez un fichier CSV.');
    if (file.size > MAX_FILE_BYTES) throw new Error('CSV trop volumineux : maximum 1 Mo.');
    button.disabled = true;
    const parsed = parseCsv(await file.text());
    for (const zone of parsed) summarize(zone.observations);
    zones = parsed; datasetMode = 'csv'; source = declaredSource; indicator = declaredIndicator;
    initialize();
  } catch (error) {
    showError(error instanceof Error ? error.message : 'Import impossible.');
  } finally {
    button.disabled = false;
  }
});
initialize();
