import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CSV_HEADER, demoCsv, parseCsv, summarize, parsePowerAnnual } from '../public/analysis.js';

test('demo is deterministic, synthetic and contains three twenty-year series', () => {
  assert.equal(demoCsv(), demoCsv());
  const zones = parseCsv(demoCsv());
  assert.equal(zones.length, 3);
  for (const zone of zones) assert.equal(zone.observations.length, 20);
  assert.ok(summarize(zones[0].observations).slope > 0);
  assert.ok(summarize(zones[2].observations).slope < 0);
});

test('regression uses actual years, does not interpolate gaps or mutate input', () => {
  const input = [{ year: 2020, value: 40 }, { year: 2000, value: 0 }, { year: 2010, value: 20 }];
  const result = summarize(input);
  assert.equal(result.slope, 2);
  assert.equal(result.change, 40);
  assert.equal(result.missingYears, 18);
  assert.equal(result.fitted(2015), 30);
  assert.equal(input[0].year, 2020);
  assert.equal(result.pValue, undefined);
});

test('constant and declining series work', () => {
  assert.equal(summarize([2000, 2001, 2002].map((year) => ({ year, value: 5 }))).slope, 0);
  assert.equal(summarize([2000, 2001, 2002].map((year) => ({ year, value: 2002 - year }))).slope, -1);
});

test('NASA POWER annual parser accepts MERRA-2 annual records and skips monthly values', () => {
  const zones = parsePowerAnnual({
    geometry: { coordinates: [11.52, 3.87, 588.63] },
    properties: { parameter: { T2M: { 202201: 24.25, 202213: 23.73, 202301: 23.89, 202313: 24.19, 202413: 24.1 } } },
    parameters: { T2M: { units: 'C' } },
    header: { sources: ['MERRA2'] },
  });
  assert.equal(zones.length, 1);
  assert.deepEqual(zones[0].observations, [
    { year: 2022, value: 23.73 },
    { year: 2023, value: 24.19 },
    { year: 2024, value: 24.1 },
  ]);
  assert.equal(zones[0].latitude, 3.87);
  assert.equal(zones[0].unit, 'C');
});

test('NASA POWER annual parser rejects unexpected sources and missing annual data', () => {
  const response = {
    geometry: { coordinates: [11.52, 3.87] },
    properties: { parameter: { T2M: { 202201: 24.25, 202213: 23.73 } } },
    parameters: { T2M: { units: 'C' } },
    header: { sources: ['MERRA2'] },
  };
  assert.throws(() => parsePowerAnnual({ ...response, header: { sources: ['OTHER'] } }), /attendues/);
  assert.throws(() => parsePowerAnnual(response), /moins de trois annees/);
});

const valid = (zone = 'A') => `${CSV_HEADER}\n${zone},2000,1,3,11,degC\n${zone},2001,2,3,11,degC\n${zone},2002,3,3,11,degC\n`;
test('CSV supports BOM, CRLF, quoted commas and escaped quotes', () => {
  const zones = parseCsv('\uFEFF' + valid('"Zone, ""A"""').replaceAll('\n', '\r\n'));
  assert.equal(zones[0].name, 'Zone, "A"');
});

test('invalid CSV inputs fail explicitly', () => {
  for (const content of [
    '', 'zone,value\nA,1', valid().replace(',2000,1,', ',2000,,'),
    valid().replace(',2000,1,', ',2000,NaN,'),
    valid().replace(',2000,1,', ',2000,Infinity,'),
    valid().replace(',2000,1,', ',2000,0x12,'),
    valid().replace(',2000,1,', ',2000,1e999,'),
    valid().replace(',2002,', ',2001,'),
    valid().replace(',2000,', ',2000.5,'),
    valid().replace(',3,11,', ',91,11,'),
    valid().replace(',3,11,', ',3,181,'),
    valid().replace(',2002,3,3,11,degC', ',2002,3,4,11,degC'),
    valid().replace(',2002,3,3,11,degC', ',2002,3,3,11,mm'),
    valid().split('\n').slice(0, 3).join('\n'),
    valid().replace('A,2000', '"A,2000'),
    valid().replace('A,2000', '"A"x,2000'),
    valid().replace('A,2000', 'A",2000'),
    'x'.repeat(1_000_001),
  ]) assert.throws(() => parseCsv(content));
});

test('multiple units across zones and oversized observation sets are rejected', () => {
  assert.throws(() => parseCsv(valid() + valid('B').split('\n').slice(1).join('\n').replaceAll('degC', 'mm')));
  assert.throws(() => parseCsv(CSV_HEADER + '\n' + 'A,2000,1,3,11,degC\n'.repeat(5001)));
});

test('insufficient, duplicate and non-finite analysis is rejected', () => {
  assert.throws(() => summarize([]));
  assert.throws(() => summarize([{ year: 2000, value: 1 }, { year: 2000, value: 2 }, { year: 2001, value: 3 }]));
  assert.throws(() => summarize([2000, 2001, 2002].map((year) => ({ year, value: Infinity }))));
});
