const DEFAULTS = {
  years: Array.from({ length: 20 }, (_, index) => 2005 + index),
  reps: 3000,
  bootstrapReps: 499,
  seed: 8899001122,
  alpha: 0.05,
  rhoGrid: [-0.5, 0, 0.3, 0.6, 0.8],
  slopesPerDecade: [0, 0.5, 1.0],
};

function makeRng(seed) {
  let state = seed >>> 0;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function normal01(rng) {
  let u = 0;
  let v = 0;
  while (u === 0) u = rng();
  while (v === 0) v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function mean(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function variance(values) {
  const m = mean(values);
  return values.reduce((sum, value) => sum + (value - m) ** 2, 0) / values.length;
}

function percentile(sortedValues, q) {
  const index = clamp(Math.ceil(q * sortedValues.length) - 1, 0, sortedValues.length - 1);
  return sortedValues[index];
}

function linearModel(years, values) {
  const xMean = mean(years);
  const yMean = mean(values);
  const sxx = years.reduce((sum, year) => sum + (year - xMean) ** 2, 0);
  const sxy = years.reduce((sum, year, index) => sum + (year - xMean) * (values[index] - yMean), 0);
  const slope = sxx > 0 ? sxy / sxx : 0;
  const intercept = yMean - slope * xMean;
  const fitted = years.map((year) => intercept + slope * year);
  const residuals = values.map((value, index) => value - fitted[index]);
  const sigma2 = variance(residuals);
  const dof = Math.max(values.length - 2, 1);
  const seSlope = Math.sqrt((sigma2 * sxx) / (dof * sxx * sxx) || 0);
  const tStatistic = sxx > 0 ? slope / Math.max(seSlope, Number.MIN_VALUE) : 0;
  return { slope, intercept, fitted, residuals, tStatistic };
}

function estimateAr1(residuals) {
  if (residuals.length < 2) return 0;
  const centered = residuals.map((value) => value - mean(residuals));
  const numerator = centered.slice(1).reduce((sum, value, index) => sum + value * centered[index], 0);
  const denominator = centered.slice(0, -1).reduce((sum, value) => sum + value ** 2, 0);
  if (denominator === 0) return 0;
  return clamp(numerator / denominator, -0.98, 0.98);
}

function generateSeries({ rho, slopePerDecade, years, rng, intercept = 23.7, sigma = 1.1 }) {
  const values = new Array(years.length);
  let previousError = 0;
  const trendPerYear = slopePerDecade / 10;
  for (let index = 0; index < years.length; index += 1) {
    const year = years[index];
    const epsilon = sigma * normal01(rng);
    const error = rho * previousError + epsilon;
    previousError = error;
    const trend = intercept + trendPerYear * (year - years[0]);
    values[index] = trend + error;
  }
  return values;
}

function parametricBootstrapPValue(values, years, bootstrapReps, rng) {
  const fit = linearModel(years, values);
  const rhoEstimate = estimateAr1(fit.residuals);
  const sigma = Math.sqrt(variance(fit.residuals));
  const nullMean = mean(values);
  const nullTStats = [];

  for (let iteration = 0; iteration < bootstrapReps; iteration += 1) {
    let previousError = 0;
    const synthetic = years.map(() => {
      const epsilon = sigma * normal01(rng);
      const error = rhoEstimate * previousError + epsilon;
      previousError = error;
      return nullMean + error;
    });
    const syntheticFit = linearModel(years, synthetic);
    nullTStats.push(syntheticFit.tStatistic);
  }

  const absObserved = Math.abs(fit.tStatistic);
  const count = nullTStats.filter((value) => Math.abs(value) >= absObserved).length;
  return {
    pValue: (count + 1) / (bootstrapReps + 1),
    rhoEstimate,
    slope: fit.slope,
    tStatistic: fit.tStatistic,
  };
}

function runSimulation({ rho, slopePerDecade, reps, bootstrapReps, seed }) {
  const results = [];
  const rng = makeRng(seed);

  for (let iteration = 0; iteration < reps; iteration += 1) {
    const values = generateSeries({
      rho,
      slopePerDecade,
      years: DEFAULTS.years,
      rng: makeRng(seed + iteration * 17 + 1),
    });
    const result = parametricBootstrapPValue(values, DEFAULTS.years, bootstrapReps, makeRng(seed + iteration * 31 + 2));
    results.push(result.pValue);
  }

  const sorted = [...results].sort((left, right) => left - right);
  return {
    rho,
    slopePerDecade,
    rejectionRate: results.filter((pValue) => pValue <= DEFAULTS.alpha).length / reps,
    medianP: percentile(sorted, 0.5),
    p90: percentile(sorted, 0.9),
    p95: percentile(sorted, 0.95),
    reps,
    bootstrapReps,
  };
}

function printHeader() {
  console.log('Final Monte Carlo validation for AR(1) + parametric bootstrap slope test');
  console.log(`Settings: reps=${DEFAULTS.reps}, bootstrap=${DEFAULTS.bootstrapReps}, alpha=${DEFAULTS.alpha}`);
  console.log('rho    | slope/dec | reject rate | median p | p90   | p95');
  console.log('------ | --------- | ----------- | -------- | ----- | -----');
}

function printSummary(summary) {
  console.log(`${String(summary.rho).padStart(5, ' ')} | ${String(summary.slopePerDecade).padStart(9, ' ')} | ${((summary.rejectionRate * 100)).toFixed(1).padStart(9, ' ')}% | ${summary.medianP.toFixed(3).padStart(8, ' ')} | ${summary.p90.toFixed(3).padStart(5, ' ')} | ${summary.p95.toFixed(3).padStart(5, ' ')}`);
}

function main() {
  printHeader();
  for (const rho of DEFAULTS.rhoGrid) {
    for (const slopePerDecade of DEFAULTS.slopesPerDecade) {
      const summary = runSimulation({
        rho,
        slopePerDecade,
        reps: DEFAULTS.reps,
        bootstrapReps: DEFAULTS.bootstrapReps,
        seed: DEFAULTS.seed + Math.round((rho + 1) * 1000) + Math.round(slopePerDecade * 100),
      });
      printSummary(summary);
    }
  }

  console.log('\nDecision rule:');
  console.log('- A method is valid only if type-I error remains close to 5% under the null, across rho values near 0 and 0.3.');
  console.log('- If type-I error is materially above 5% on these 20-year annual series, do not show a p-value in the UI.');
  console.log('- Power should be reported alongside size, but it is not a substitute for a well-calibrated test.');
}

main();
