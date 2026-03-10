/**
 * Health Engine — Coverage & Assessment Scoring Engine (Client-side)
 *
 * Ports engine/scoring/engine.py → JavaScript.
 * Full NHANES percentile scoring + fallback cutoff tables.
 */

import { getPercentile } from './nhanes.js';

// Stub device functions (override these if device-db is available)
function getDeviceCapabilities() { return null; }
function getHrvType() { return 'rmssd'; }

// ---------------------------------------------------------------------------
// Standings
// ---------------------------------------------------------------------------

const Standing = {
  OPTIMAL: 'Optimal',
  GOOD: 'Healthy',
  AVERAGE: 'Borderline',
  BELOW_AVG: 'Elevated Risk',
  CONCERNING: 'At Risk',
  UNKNOWN: 'No Data',
};

// ---------------------------------------------------------------------------
// Age bucket helper
// ---------------------------------------------------------------------------

function ageBucket(age) {
  if (age < 30) return '20-29';
  if (age < 40) return '30-39';
  if (age < 50) return '40-49';
  if (age < 60) return '50-59';
  if (age < 70) return '60-69';
  return '70+';
}

// ---------------------------------------------------------------------------
// Percentile → Standing
// ---------------------------------------------------------------------------

function percentileToStanding(pct) {
  if (pct >= 85) return Standing.OPTIMAL;
  if (pct >= 65) return Standing.GOOD;
  if (pct >= 35) return Standing.AVERAGE;
  if (pct >= 15) return Standing.BELOW_AVG;
  return Standing.CONCERNING;
}

// ---------------------------------------------------------------------------
// NHANES key mapping
// ---------------------------------------------------------------------------

const NHANES_KEY_MAP = {
  bp_systolic: 'bp_systolic',
  bp_diastolic: 'bp_diastolic',
  rhr: 'rhr',
  ldl_c: 'ldl_c',
  hdl_c: 'hdl_c',
  triglycerides: 'triglycerides',
  fasting_glucose: 'fasting_glucose',
  hba1c: 'hba1c',
  fasting_insulin: 'fasting_insulin',
  waist: 'waist',
  hscrp: 'hscrp',
  alt: 'alt',
  ggt: 'ggt',
  ferritin: 'ferritin',
  hemoglobin: 'hemoglobin',
  apob: 'apob',
  vitamin_d: 'vitamin_d',
  tsh: 'tsh',
  lpa: 'lpa',
};

// ---------------------------------------------------------------------------
// Fallback cutoff tables (from score.py)
// ---------------------------------------------------------------------------

const CUTOFF_TABLES = {
  bp_systolic: {
    lower_is_better: true,
    cutoffs: {
      '30-39|M': [110, 120, 130, 140], '30-39|F': [110, 120, 130, 140],
      '40-49|M': [115, 125, 135, 145], '50-59|M': [120, 130, 140, 150],
    },
  },
  bp_diastolic: {
    lower_is_better: true,
    cutoffs: { '30-39|M': [70, 80, 85, 90], '30-39|F': [70, 80, 85, 90] },
  },
  ldl_c: {
    lower_is_better: true,
    cutoffs: { '30-39|M': [80, 100, 130, 160], '30-39|F': [80, 100, 130, 160] },
  },
  hdl_c: {
    lower_is_better: false,
    cutoffs: { '30-39|M': [35, 40, 50, 60], '30-39|F': [40, 50, 60, 70] },
  },
  apob: {
    lower_is_better: true,
    cutoffs: { universal: [70, 90, 110, 130] },
  },
  triglycerides: {
    lower_is_better: true,
    cutoffs: { '30-39|M': [75, 100, 150, 200], '30-39|F': [75, 100, 150, 200] },
  },
  fasting_glucose: {
    lower_is_better: true,
    cutoffs: { '30-39|M': [88, 95, 100, 113], '30-39|F': [88, 95, 100, 113] },
  },
  hba1c: {
    lower_is_better: true,
    cutoffs: { '30-39|M': [5.0, 5.2, 5.6, 6.0], '30-39|F': [5.0, 5.2, 5.6, 6.0] },
  },
  fasting_insulin: {
    lower_is_better: true,
    cutoffs: { '30-39|M': [5.0, 8.0, 12.0, 19.0], '30-39|F': [5.0, 8.0, 12.0, 19.0] },
  },
  rhr: {
    lower_is_better: true,
    cutoffs: { '30-39|M': [58, 65, 74, 85], '30-39|F': [60, 68, 76, 88] },
  },
  daily_steps: {
    lower_is_better: false,
    cutoffs: { universal: [4000, 6000, 8000, 10000] },
  },
  waist: {
    lower_is_better: true,
    cutoffs: { '30-39|M': [33, 35, 38, 41], '30-39|F': [28, 31, 35, 38] },
  },
  lpa: {
    lower_is_better: true,
    cutoffs: { universal: [30, 75, 125, 200] },
  },
  sleep_duration: {
    lower_is_better: false,
    cutoffs: { universal: [6.0, 7.0, 8.0, 9.5] },
  },
  sleep_regularity: {
    lower_is_better: true,
    cutoffs: { universal: [15, 30, 45, 60] },
  },
  hscrp: {
    lower_is_better: true,
    cutoffs: { '30-39|M': [0.5, 1.0, 2.0, 5.0], '30-39|F': [0.5, 1.0, 2.0, 5.0] },
  },
  alt: {
    lower_is_better: true,
    cutoffs: { '30-39|M': [20, 30, 44, 60], '30-39|F': [15, 25, 35, 50] },
  },
  ggt: {
    lower_is_better: true,
    cutoffs: { '30-39|M': [20, 30, 50, 80], '30-39|F': [15, 25, 40, 65] },
  },
  tsh: {
    lower_is_better: true,
    cutoffs: { universal: [2.5, 4.0, 6.0, 10.0] },
  },
  vitamin_d: {
    lower_is_better: false,
    cutoffs: { universal: [15, 20, 30, 40] },
  },
  ferritin: {
    lower_is_better: false,
    cutoffs: { '30-39|M': [20, 40, 80, 150], '30-39|F': [10, 20, 40, 80] },
  },
  hemoglobin: {
    lower_is_better: false,
    cutoffs: { '30-39|M': [12.0, 13.5, 14.5, 15.5], '30-39|F': [10.5, 12.0, 13.0, 14.0] },
  },
  vo2_max: {
    lower_is_better: false,
    cutoffs: {
      '20-29|M': [35, 40, 46, 52], '30-39|M': [33, 38, 44, 50],
      '40-49|M': [31, 36, 42, 48], '50-59|M': [28, 33, 39, 45],
      '60-69|M': [24, 29, 35, 41], '70+|M': [20, 25, 31, 37],
      '20-29|F': [30, 35, 40, 46], '30-39|F': [28, 33, 38, 44],
      '40-49|F': [25, 30, 35, 41], '50-59|F': [22, 27, 32, 38],
      '60-69|F': [19, 24, 29, 35], '70+|F': [16, 21, 26, 32],
    },
  },
  hrv_rmssd: {
    lower_is_better: false,
    cutoffs: {
      '20-29|M': [18, 25, 40, 60], '30-39|M': [15, 22, 35, 55],
      '40-49|M': [12, 18, 28, 45], '50-59|M': [10, 15, 22, 38],
      '60-69|M': [8, 12, 18, 30], '70+|M': [6, 10, 15, 25],
      '20-29|F': [18, 25, 40, 60], '30-39|F': [15, 22, 35, 55],
      '40-49|F': [12, 18, 28, 45], '50-59|F': [10, 15, 22, 38],
      '60-69|F': [8, 12, 18, 30], '70+|F': [6, 10, 15, 25],
    },
  },
  hrv_sdnn: {
    lower_is_better: false,
    cutoffs: {
      '20-29|M': [25, 38, 55, 75], '30-39|M': [22, 33, 48, 65],
      '40-49|M': [18, 28, 40, 55], '50-59|M': [15, 23, 33, 48],
      '60-69|M': [12, 18, 27, 40], '70+|M': [10, 15, 22, 35],
      '20-29|F': [22, 35, 50, 70], '30-39|F': [20, 30, 44, 60],
      '40-49|F': [16, 25, 36, 50], '50-59|F': [13, 20, 30, 43],
      '60-69|F': [10, 16, 24, 36], '70+|F': [8, 13, 20, 32],
    },
  },
};

// ---------------------------------------------------------------------------
// Standing → Health Score (0-100)
// ---------------------------------------------------------------------------

function standingToHealthScore(standing) {
  switch (standing) {
    case Standing.OPTIMAL: return 95;
    case Standing.GOOD: return 80;
    case Standing.AVERAGE: return 55;
    case Standing.BELOW_AVG: return 30;
    case Standing.CONCERNING: return 10;
    default: return null;
  }
}

// ---------------------------------------------------------------------------
// Assess function — Clinical thresholds first, NHANES percentile as context
// ---------------------------------------------------------------------------

function assess(value, tableKey, demo, nhanesKey) {
  if (value == null) return { standing: Standing.UNKNOWN, healthScore: null, populationPercentile: null };

  // Always compute NHANES percentile as population context (when available)
  let populationPercentile = null;
  if (nhanesKey && NHANES_KEY_MAP[nhanesKey]) {
    const bucket = ageBucket(demo.age);
    const pct = getPercentile(NHANES_KEY_MAP[nhanesKey], value, bucket, demo.sex);
    if (pct != null) populationPercentile = Math.round(pct);
  }

  // Primary: clinical cutoff tables
  const table = CUTOFF_TABLES[tableKey];
  if (table) {
    const bucket = ageBucket(demo.age);
    const key = `${bucket}|${demo.sex}`;
    const cutoffs = table.cutoffs[key] || table.cutoffs['universal'];
    if (cutoffs) {
      let standing;
      const lib = table.lower_is_better;
      if (lib) {
        if (value <= cutoffs[0]) standing = Standing.OPTIMAL;
        else if (value <= cutoffs[1]) standing = Standing.GOOD;
        else if (value <= cutoffs[2]) standing = Standing.AVERAGE;
        else if (value <= cutoffs[3]) standing = Standing.BELOW_AVG;
        else standing = Standing.CONCERNING;
      } else {
        if (value <= cutoffs[0]) standing = Standing.CONCERNING;
        else if (value <= cutoffs[1]) standing = Standing.BELOW_AVG;
        else if (value <= cutoffs[2]) standing = Standing.AVERAGE;
        else if (value <= cutoffs[3]) standing = Standing.GOOD;
        else standing = Standing.OPTIMAL;
      }
      return { standing, healthScore: standingToHealthScore(standing), populationPercentile };
    }
  }

  // Fallback: derive standing from NHANES percentile when no cutoff table matches
  if (populationPercentile != null) {
    const standing = percentileToStanding(populationPercentile);
    return { standing, healthScore: standingToHealthScore(standing), populationPercentile };
  }

  return { standing: Standing.UNKNOWN, healthScore: null, populationPercentile: null };
}

// ---------------------------------------------------------------------------
// Coverage weights — mirrors score.py exactly
// ---------------------------------------------------------------------------

const TIER1_WEIGHTS = {
  blood_pressure: 8,
  lipid_apob: 8,
  metabolic: 8,
  family_history: 6,
  sleep_duration: 3,
  sleep_regularity: 2,
  steps: 4,
  resting_hr: 4,
  waist: 5,
  medications: 4,
  lpa: 8,
};

const TIER2_WEIGHTS = {
  vo2_max: 5,
  hrv: 2,
  hscrp: 3,
  liver: 2,
  cbc: 2,
  thyroid: 2,
  vitamin_d_ferritin: 3,
  weight_trends: 2,
  phq9: 2,
  zone2: 2,
};

// ---------------------------------------------------------------------------
// Device-aware costToClose helper
// ---------------------------------------------------------------------------

function deviceAwareCost(metricKey, defaultCost, deviceCaps, modelName, hasData) {
  if (!deviceCaps) return defaultCost;

  switch (metricKey) {
    case 'sleep_duration':
      if (deviceCaps.sleep_duration) return hasData ? `Covered by your ${modelName}` : `Available from your ${modelName}`;
      return `Not available from ${modelName} — try a different export method`;

    case 'sleep_regularity':
      if (deviceCaps.sleep_stages) return `Computable from your ${modelName} sleep data — needs multi-night export`;
      return `Not available from ${modelName} — requires raw sleep stage timestamps`;

    case 'hrv':
      if (deviceCaps.hrv) return hasData ? `Covered by your ${modelName}` : `Available from your ${modelName}`;
      return `${modelName} doesn't support HRV export. Consider a model with HRV support.`;

    case 'vo2max':
      if (deviceCaps.vo2max) return hasData ? `Covered by your ${modelName}` : `Available from your ${modelName}`;
      return `Not available from ${modelName}. Requires GPS-enabled outdoor workouts on a compatible device.`;

    case 'steps':
      if (deviceCaps.steps) return hasData ? `Covered by your ${modelName}` : `Available from your ${modelName}`;
      return defaultCost;

    case 'resting_hr':
      if (deviceCaps.resting_hr) return hasData ? `Covered by your ${modelName}` : `Available from your ${modelName}`;
      return defaultCost;

    case 'zone2':
      if (deviceCaps.resting_hr) return hasData ? `Covered by your ${modelName}` : `Available from your ${modelName} with HR zones`;
      return defaultCost;

    default:
      return defaultCost;
  }
}

// ---------------------------------------------------------------------------
// Score a profile — full port of score_profile()
// ---------------------------------------------------------------------------

function scoreProfile(profile) {
  const demo = profile.demographics;
  const results = [];

  // Read selected device for device-aware gap card recommendations
  const selectedDevice = typeof window !== 'undefined' && window.__selectedDevice;
  const deviceCaps = selectedDevice
    ? getDeviceCapabilities(selectedDevice.brand, selectedDevice.model)
    : null;
  const modelName = selectedDevice
    ? (selectedDevice.model || { apple: 'Apple Watch', garmin: 'Garmin', oura: 'Oura', fitbit: 'Fitbit', polar: 'Polar', whoop: 'Whoop', samsung: 'Samsung' }[selectedDevice.brand] || 'your device')
    : null;

  // --- Blood Pressure ---
  const bpHas = profile.systolic != null;
  const bp = assess(profile.systolic, 'bp_systolic', demo, 'bp_systolic');
  results.push({
    name: 'Blood Pressure', tier: 1, rank: 1, hasData: bpHas,
    value: profile.systolic,
    unit: 'mmHg' + (profile.diastolic != null ? `/${Math.round(profile.diastolic)}` : ''),
    standing: bp.standing, healthScore: bp.healthScore, populationPercentile: bp.populationPercentile,
    weight: TIER1_WEIGHTS.blood_pressure,
    costToClose: '$40 one-time (Omron cuff)',
    note: !bpHas ? 'Each 20 mmHg >115 SBP doubles CVD mortality' : '',
  });

  // --- Lipid Panel + ApoB ---
  const lipidHas = [profile.ldl_c, profile.hdl_c, profile.triglycerides].some(v => v != null);
  const apobHas = profile.apob != null;
  let lip;
  if (apobHas) {
    lip = assess(profile.apob, 'apob', demo, 'apob');
    lip.value = profile.apob; lip.unit = 'mg/dL (ApoB)';
  } else if (profile.ldl_c != null) {
    lip = assess(profile.ldl_c, 'ldl_c', demo, 'ldl_c');
    lip.value = profile.ldl_c; lip.unit = 'mg/dL (LDL-C)';
  } else {
    lip = { standing: Standing.UNKNOWN, healthScore: null, populationPercentile: null, value: null, unit: '' };
  }
  // Sub-metric breakdown for composite panels
  const lipidSubs = [];
  if (profile.apob != null) { const a = assess(profile.apob, 'apob', demo, 'apob'); lipidSubs.push({ name: 'ApoB', value: profile.apob, unit: 'mg/dL', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  if (profile.ldl_c != null) { const a = assess(profile.ldl_c, 'ldl_c', demo, 'ldl_c'); lipidSubs.push({ name: 'LDL-C', value: profile.ldl_c, unit: 'mg/dL', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  if (profile.hdl_c != null) { const a = assess(profile.hdl_c, 'hdl_c', demo, 'hdl_c'); lipidSubs.push({ name: 'HDL-C', value: profile.hdl_c, unit: 'mg/dL', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  if (profile.triglycerides != null) { const a = assess(profile.triglycerides, 'triglycerides', demo, 'triglycerides'); lipidSubs.push({ name: 'Triglycerides', value: profile.triglycerides, unit: 'mg/dL', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  results.push({
    name: 'Lipid Panel + ApoB', tier: 1, rank: 2, hasData: lipidHas || apobHas,
    value: lip.value, unit: lip.unit, standing: lip.standing, healthScore: lip.healthScore, populationPercentile: lip.populationPercentile,
    weight: TIER1_WEIGHTS.lipid_apob,
    costToClose: '$30-50/yr (Quest lipid + ApoB add-on)',
    note: !apobHas && lipidHas ? 'ApoB > LDL-C for risk prediction' : '',
    subMetrics: lipidSubs.length > 1 ? lipidSubs : null,
  });

  // --- Metabolic Panel ---
  const metHas = [profile.fasting_glucose, profile.hba1c, profile.fasting_insulin].some(v => v != null);
  let met;
  if (profile.fasting_insulin != null) {
    met = assess(profile.fasting_insulin, 'fasting_insulin', demo, 'fasting_insulin');
    met.value = profile.fasting_insulin; met.unit = 'µIU/mL (fasting insulin)';
  } else if (profile.hba1c != null) {
    met = assess(profile.hba1c, 'hba1c', demo, 'hba1c');
    met.value = profile.hba1c; met.unit = '% (HbA1c)';
  } else if (profile.fasting_glucose != null) {
    met = assess(profile.fasting_glucose, 'fasting_glucose', demo, 'fasting_glucose');
    met.value = profile.fasting_glucose; met.unit = 'mg/dL (glucose)';
  } else {
    met = { standing: Standing.UNKNOWN, healthScore: null, populationPercentile: null, value: null, unit: '' };
  }
  const metSubs = [];
  if (profile.fasting_glucose != null) { const a = assess(profile.fasting_glucose, 'fasting_glucose', demo, 'fasting_glucose'); metSubs.push({ name: 'Fasting Glucose', value: profile.fasting_glucose, unit: 'mg/dL', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  if (profile.hba1c != null) { const a = assess(profile.hba1c, 'hba1c', demo, 'hba1c'); metSubs.push({ name: 'HbA1c', value: profile.hba1c, unit: '%', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  if (profile.fasting_insulin != null) { const a = assess(profile.fasting_insulin, 'fasting_insulin', demo, 'fasting_insulin'); metSubs.push({ name: 'Fasting Insulin', value: profile.fasting_insulin, unit: 'µIU/mL', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  results.push({
    name: 'Metabolic Panel', tier: 1, rank: 3, hasData: metHas,
    value: met.value, unit: met.unit, standing: met.standing, healthScore: met.healthScore, populationPercentile: met.populationPercentile,
    weight: TIER1_WEIGHTS.metabolic,
    costToClose: '$40-60/yr (glucose + HbA1c + insulin)',
    note: profile.fasting_insulin == null && metHas ? 'Fasting insulin catches IR 10-15 yrs before diagnosis' : '',
    subMetrics: metSubs.length > 1 ? metSubs : null,
  });

  // --- Family History ---
  const fhHas = profile.has_family_history != null;
  results.push({
    name: 'Family History', tier: 1, rank: 4, hasData: fhHas,
    value: null, unit: '', standing: fhHas ? Standing.GOOD : Standing.UNKNOWN, healthScore: null, populationPercentile: null,
    weight: TIER1_WEIGHTS.family_history,
    costToClose: 'Free — 10 min conversation',
    note: !fhHas ? 'One-time. Parental CVD <60 doubles risk.' : '',
  });

  // --- Sleep Duration ---
  const sleepDurHas = profile.sleep_duration_avg != null;
  const sleepDur = assess(profile.sleep_duration_avg, 'sleep_duration', demo, null);
  results.push({
    name: 'Sleep Duration', tier: 1, rank: 5, hasData: sleepDurHas,
    value: profile.sleep_duration_avg, unit: 'hrs/night',
    standing: sleepDur.standing, healthScore: sleepDur.healthScore, populationPercentile: sleepDur.populationPercentile,
    weight: TIER1_WEIGHTS.sleep_duration,
    costToClose: deviceAwareCost('sleep_duration', 'Free with any wearable', deviceCaps, modelName, sleepDurHas),
    note: !sleepDurHas ? 'Average nightly sleep hours' : '',
  });

  // --- Sleep Regularity ---
  const sleepRegHas = profile.sleep_regularity_stddev != null;
  const sleepReg = assess(profile.sleep_regularity_stddev, 'sleep_regularity', demo, null);
  results.push({
    name: 'Sleep Regularity', tier: 1, rank: 6, hasData: sleepRegHas,
    value: profile.sleep_regularity_stddev, unit: 'min std dev',
    standing: sleepReg.standing, healthScore: sleepReg.healthScore, populationPercentile: sleepReg.populationPercentile,
    weight: TIER1_WEIGHTS.sleep_regularity,
    costToClose: deviceAwareCost('sleep_regularity', 'Computed from 7-14 nights of raw sleep data', deviceCaps, modelName, sleepRegHas),
    note: !sleepRegHas ? 'Regularity predicts mortality > duration' : '',
  });

  // --- Daily Steps ---
  const stepsHas = profile.daily_steps_avg != null;
  const steps = assess(profile.daily_steps_avg, 'daily_steps', demo, null);
  results.push({
    name: 'Daily Steps', tier: 1, rank: 7, hasData: stepsHas,
    value: profile.daily_steps_avg, unit: 'steps/day',
    standing: steps.standing, healthScore: steps.healthScore, populationPercentile: steps.populationPercentile,
    weight: TIER1_WEIGHTS.steps,
    costToClose: deviceAwareCost('steps', 'Free with phone', deviceCaps, modelName, stepsHas),
    note: !stepsHas ? 'Each +1K steps = ~15% lower mortality' : '',
  });

  // --- Resting Heart Rate ---
  const rhrHas = profile.resting_hr != null;
  const rhr = assess(profile.resting_hr, 'rhr', demo, 'rhr');
  results.push({
    name: 'Resting Heart Rate', tier: 1, rank: 8, hasData: rhrHas,
    value: profile.resting_hr, unit: 'bpm',
    standing: rhr.standing, healthScore: rhr.healthScore, populationPercentile: rhr.populationPercentile,
    weight: TIER1_WEIGHTS.resting_hr,
    costToClose: deviceAwareCost('resting_hr', 'Free with wearable', deviceCaps, modelName, rhrHas),
    note: '',
  });

  // --- Waist Circumference ---
  const waistHas = profile.waist_circumference != null;
  const waist = assess(profile.waist_circumference, 'waist', demo, 'waist');
  results.push({
    name: 'Waist Circumference', tier: 1, rank: 9, hasData: waistHas,
    value: profile.waist_circumference, unit: 'inches',
    standing: waist.standing, healthScore: waist.healthScore, populationPercentile: waist.populationPercentile,
    weight: TIER1_WEIGHTS.waist,
    costToClose: '$3 tape measure',
    note: '',
  });

  // --- Medication List ---
  const medsHas = profile.has_medication_list != null;
  results.push({
    name: 'Medication List', tier: 1, rank: 10, hasData: medsHas,
    value: null, unit: '', standing: medsHas ? Standing.GOOD : Standing.UNKNOWN, healthScore: null, populationPercentile: null,
    weight: TIER1_WEIGHTS.medications,
    costToClose: 'Free — 5 min entry',
    note: !medsHas ? 'Context for interpreting all other data' : '',
  });

  // --- Lp(a) ---
  const lpaHas = profile.lpa != null;
  const lpa = assess(profile.lpa, 'lpa', demo, 'lpa');
  results.push({
    name: 'Lp(a)', tier: 1, rank: 11, hasData: lpaHas,
    value: profile.lpa, unit: 'nmol/L',
    standing: lpa.standing, healthScore: lpa.healthScore, populationPercentile: lpa.populationPercentile,
    weight: TIER1_WEIGHTS.lpa,
    costToClose: '$30 — once in your lifetime',
    note: !lpaHas ? '20% of people have elevated Lp(a), invisible on standard panels' : '',
  });

  // --- Tier 2: VO2 Max ---
  const vo2Has = profile.vo2_max != null;
  const vo2 = assess(profile.vo2_max, 'vo2_max', demo, null);
  results.push({
    name: 'VO2 Max', tier: 2, rank: 12, hasData: vo2Has,
    value: profile.vo2_max, unit: 'mL/kg/min',
    standing: vo2.standing, healthScore: vo2.healthScore, populationPercentile: vo2.populationPercentile,
    weight: TIER2_WEIGHTS.vo2_max,
    costToClose: deviceAwareCost('vo2max', 'Free with Garmin or Apple Watch (estimate)', deviceCaps, modelName, vo2Has),
    note: !vo2Has ? 'Strongest modifiable predictor of all-cause mortality' : '',
  });

  // --- Tier 2: HRV ---
  const hrvHas = profile.hrv_rmssd_avg != null;
  const hrvType = getHrvType(selectedDevice?.brand, selectedDevice?.model) || 'rmssd';
  const hrvTableKey = hrvType === 'sdnn' ? 'hrv_sdnn' : 'hrv_rmssd';
  const hrv = assess(profile.hrv_rmssd_avg, hrvTableKey, demo, null);
  const hrvTypeSuffix = hrvType === 'sdnn' ? 'SDNN' : 'RMSSD';
  results.push({
    name: `HRV ${hrvTypeSuffix} (7-day avg)`, tier: 2, rank: 13, hasData: hrvHas,
    value: profile.hrv_rmssd_avg, unit: `ms ${hrvTypeSuffix}`,
    standing: hrv.standing, healthScore: hrv.healthScore, populationPercentile: hrv.populationPercentile,
    weight: TIER2_WEIGHTS.hrv,
    costToClose: deviceAwareCost('hrv', 'Free with most wearables', deviceCaps, modelName, hrvHas),
    note: !hrvHas ? 'Use 7-day rolling avg, not single readings' : '',
  });

  // --- Tier 2: hs-CRP ---
  const crpHas = profile.hscrp != null;
  const crp = assess(profile.hscrp, 'hscrp', demo, 'hscrp');
  results.push({
    name: 'hs-CRP', tier: 2, rank: 14, hasData: crpHas,
    value: profile.hscrp, unit: 'mg/L',
    standing: crp.standing, healthScore: crp.healthScore, populationPercentile: crp.populationPercentile,
    weight: TIER2_WEIGHTS.hscrp,
    costToClose: '$20/year (add to lab order)',
    note: !crpHas ? 'Adds CVD risk stratification beyond lipids' : '',
  });

  // --- Tier 2: Liver Enzymes ---
  const liverHas = [profile.alt, profile.ggt].some(v => v != null);
  let liver;
  if (profile.ggt != null) {
    liver = assess(profile.ggt, 'ggt', demo, 'ggt');
    liver.value = profile.ggt; liver.unit = 'U/L (GGT)';
  } else if (profile.alt != null) {
    liver = assess(profile.alt, 'alt', demo, 'alt');
    liver.value = profile.alt; liver.unit = 'U/L (ALT)';
  } else {
    liver = { standing: Standing.UNKNOWN, healthScore: null, populationPercentile: null, value: null, unit: '' };
  }
  const liverSubs = [];
  if (profile.alt != null) { const a = assess(profile.alt, 'alt', demo, 'alt'); liverSubs.push({ name: 'ALT', value: profile.alt, unit: 'U/L', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  if (profile.ggt != null) { const a = assess(profile.ggt, 'ggt', demo, 'ggt'); liverSubs.push({ name: 'GGT', value: profile.ggt, unit: 'U/L', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  results.push({
    name: 'Liver Enzymes', tier: 2, rank: 15, hasData: liverHas,
    value: liver.value, unit: liver.unit, standing: liver.standing, healthScore: liver.healthScore, populationPercentile: liver.populationPercentile,
    weight: TIER2_WEIGHTS.liver,
    costToClose: 'Usually included in standard panels',
    note: !liverHas ? 'GGT independently predicts CV mortality + diabetes' : '',
    subMetrics: liverSubs.length > 1 ? liverSubs : null,
  });

  // --- Tier 2: CBC ---
  const cbcHas = [profile.hemoglobin, profile.wbc, profile.platelets].some(v => v != null);
  let cbc;
  if (profile.hemoglobin != null) {
    cbc = assess(profile.hemoglobin, 'hemoglobin', demo, 'hemoglobin');
    cbc.value = profile.hemoglobin; cbc.unit = 'g/dL (Hgb)';
  } else {
    cbc = { standing: Standing.UNKNOWN, healthScore: null, populationPercentile: null, value: null, unit: '' };
  }
  const cbcSubs = [];
  if (profile.hemoglobin != null) { const a = assess(profile.hemoglobin, 'hemoglobin', demo, 'hemoglobin'); cbcSubs.push({ name: 'Hemoglobin', value: profile.hemoglobin, unit: 'g/dL', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  if (profile.wbc != null) { const a = assess(profile.wbc, 'wbc', demo, 'wbc'); cbcSubs.push({ name: 'WBC', value: profile.wbc, unit: 'K/µL', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  if (profile.platelets != null) { const a = assess(profile.platelets, 'platelets', demo, 'platelets'); cbcSubs.push({ name: 'Platelets', value: profile.platelets, unit: 'K/µL', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  results.push({
    name: 'CBC', tier: 2, rank: 16, hasData: cbcHas,
    value: cbc.value, unit: cbc.unit, standing: cbc.standing, healthScore: cbc.healthScore, populationPercentile: cbc.populationPercentile,
    weight: TIER2_WEIGHTS.cbc,
    costToClose: 'Usually included in standard panels',
    note: !cbcHas ? 'Safety net screening — RDW predicts all-cause mortality' : '',
    subMetrics: cbcSubs.length > 1 ? cbcSubs : null,
  });

  // --- Tier 2: Thyroid (TSH) ---
  const thyroidHas = profile.tsh != null;
  let thyroid;
  if (profile.tsh != null && profile.tsh < 0.4) {
    thyroid = { standing: Standing.CONCERNING, healthScore: 10, populationPercentile: null };
  } else if (profile.tsh != null && profile.tsh <= 2.5) {
    thyroid = { standing: Standing.OPTIMAL, healthScore: 95, populationPercentile: null };
  } else {
    thyroid = assess(profile.tsh, 'tsh', demo, 'tsh');
  }
  results.push({
    name: 'Thyroid (TSH)', tier: 2, rank: 17, hasData: thyroidHas,
    value: profile.tsh, unit: 'mIU/L',
    standing: thyroid.standing, healthScore: thyroid.healthScore, populationPercentile: thyroid.populationPercentile,
    weight: TIER2_WEIGHTS.thyroid,
    costToClose: '$20/year',
    note: !thyroidHas ? '12% lifetime prevalence. Highly treatable.' : '',
  });

  // --- Tier 2: Vitamin D + Ferritin ---
  const vdFerHas = [profile.vitamin_d, profile.ferritin].some(v => v != null);
  let vdFer;
  if (profile.vitamin_d != null) {
    vdFer = assess(profile.vitamin_d, 'vitamin_d', demo, 'vitamin_d');
    vdFer.value = profile.vitamin_d; vdFer.unit = 'ng/mL (Vit D)';
  } else if (profile.ferritin != null) {
    vdFer = assess(profile.ferritin, 'ferritin', demo, 'ferritin');
    vdFer.value = profile.ferritin; vdFer.unit = 'ng/mL (Ferritin)';
  } else {
    vdFer = { standing: Standing.UNKNOWN, healthScore: null, populationPercentile: null, value: null, unit: '' };
  }
  const vdFerSubs = [];
  if (profile.vitamin_d != null) { const a = assess(profile.vitamin_d, 'vitamin_d', demo, 'vitamin_d'); vdFerSubs.push({ name: 'Vitamin D', value: profile.vitamin_d, unit: 'ng/mL', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  if (profile.ferritin != null) { const a = assess(profile.ferritin, 'ferritin', demo, 'ferritin'); vdFerSubs.push({ name: 'Ferritin', value: profile.ferritin, unit: 'ng/mL', standing: a.standing, healthScore: a.healthScore, populationPercentile: a.populationPercentile }); }
  results.push({
    name: 'Vitamin D + Ferritin', tier: 2, rank: 18, hasData: vdFerHas,
    value: vdFer.value, unit: vdFer.unit, standing: vdFer.standing, healthScore: vdFer.healthScore, populationPercentile: vdFer.populationPercentile,
    weight: TIER2_WEIGHTS.vitamin_d_ferritin,
    costToClose: '$40-60 baseline lab add-on',
    note: !vdFerHas ? '42% of US adults Vit D deficient. Cheap to fix.' : '',
    subMetrics: vdFerSubs.length > 1 ? vdFerSubs : null,
  });

  // --- Tier 2: Weight Trends ---
  const weightHas = profile.weight_lbs != null;
  results.push({
    name: 'Weight Trends', tier: 2, rank: 19, hasData: weightHas,
    value: null, unit: '', standing: weightHas ? Standing.GOOD : Standing.UNKNOWN, healthScore: null, populationPercentile: null,
    weight: TIER2_WEIGHTS.weight_trends,
    costToClose: '$20-50 (smart scale)',
    note: !weightHas ? 'Progressive drift is the signal, not absolute weight' : '',
  });

  // --- Tier 2: PHQ-9 ---
  const phq9Has = profile.phq9_score != null;
  let phq9Standing = Standing.UNKNOWN;
  let phq9HealthScore = null;
  if (phq9Has) {
    const s = profile.phq9_score;
    if (s <= 4)       { phq9Standing = Standing.OPTIMAL;    phq9HealthScore = 95; }
    else if (s <= 9)  { phq9Standing = Standing.GOOD;       phq9HealthScore = 80; }
    else if (s <= 14) { phq9Standing = Standing.AVERAGE;    phq9HealthScore = 55; }
    else if (s <= 19) { phq9Standing = Standing.BELOW_AVG;  phq9HealthScore = 30; }
    else              { phq9Standing = Standing.CONCERNING;  phq9HealthScore = 10; }
  }
  results.push({
    name: 'PHQ-9 (Depression)', tier: 2, rank: 20, hasData: phq9Has,
    value: phq9Has ? profile.phq9_score : null, unit: '/27',
    standing: phq9Standing, healthScore: phq9HealthScore, populationPercentile: null,
    weight: TIER2_WEIGHTS.phq9,
    costToClose: 'Free — 3 min questionnaire',
    note: !phq9Has ? 'Depression independently raises CVD risk 80%' : '',
  });

  // --- Tier 2: Zone 2 Cardio ---
  const z2Has = profile.zone2_min_per_week != null;
  results.push({
    name: 'Zone 2 Cardio', tier: 2, rank: 21, hasData: z2Has,
    value: null, unit: '', standing: z2Has ? Standing.GOOD : Standing.UNKNOWN, healthScore: null, populationPercentile: null,
    weight: TIER2_WEIGHTS.zone2,
    costToClose: deviceAwareCost('zone2', 'Free with HR wearable', deviceCaps, modelName, z2Has),
    note: !z2Has ? '150-300 min/week = largest mortality reduction' : '',
  });

  // --- Compute scores ---
  const t1Total = Object.values(TIER1_WEIGHTS).reduce((a, b) => a + b, 0);
  const t2Total = Object.values(TIER2_WEIGHTS).reduce((a, b) => a + b, 0);
  const totalWeight = t1Total + t2Total;

  const coveredWeight = results.filter(r => r.hasData).reduce((sum, r) => sum + r.weight, 0);
  const coveragePct = Math.round(coveredWeight / totalWeight * 100);

  const tier1Results = results.filter(r => r.tier === 1);
  const tier2Results = results.filter(r => r.tier === 2);
  const t1Covered = tier1Results.filter(r => r.hasData).reduce((sum, r) => sum + r.weight, 0);
  const t2Covered = tier2Results.filter(r => r.hasData).reduce((sum, r) => sum + r.weight, 0);
  const t1Pct = Math.round(t1Covered / t1Total * 100);
  const t2Pct = Math.round(t2Covered / t2Total * 100);

  const assessed = results.filter(r => r.healthScore != null);
  const avgHealthScore = assessed.length > 0
    ? Math.round(assessed.reduce((s, r) => s + r.healthScore, 0) / assessed.length)
    : null;

  const gaps = results.filter(r => !r.hasData).sort((a, b) => b.weight - a.weight);

  return {
    coverageScore: coveragePct,
    coverageFraction: `${results.filter(r => r.hasData).length}/${results.length}`,
    tier1Pct: t1Pct,
    tier1Fraction: `${tier1Results.filter(r => r.hasData).length}/${tier1Results.length}`,
    tier1Weight: `${t1Covered}/${t1Total}`,
    tier2Pct: t2Pct,
    tier2Fraction: `${tier2Results.filter(r => r.hasData).length}/${tier2Results.length}`,
    tier2Weight: `${t2Covered}/${t2Total}`,
    avgHealthScore,
    results,
    gaps,
  };
}

// ---------------------------------------------------------------------------
// Freshness — plateau + linear decay per metric
// ---------------------------------------------------------------------------

const FRESHNESS_WINDOWS = {
  // Labs: fresh (months), stale (months)
  apob:                { fresh: 6, stale: 12 },
  ldl_c:               { fresh: 6, stale: 12 },
  hdl_c:               { fresh: 6, stale: 12 },
  triglycerides:        { fresh: 3, stale: 9 },
  fasting_glucose:      { fresh: 3, stale: 9 },
  fasting_insulin:      { fresh: 3, stale: 9 },
  hba1c:               { fresh: 6, stale: 12 },
  lpa:                 { fresh: 120, stale: 240 },  // lifetime
  hscrp:               { fresh: 6, stale: 12 },
  tsh:                 { fresh: 6, stale: 12 },
  vitamin_d:           { fresh: 4, stale: 10 },
  ferritin:            { fresh: 6, stale: 12 },
  hemoglobin:          { fresh: 12, stale: 24 },
  alt:                 { fresh: 6, stale: 12 },
  ggt:                 { fresh: 6, stale: 12 },
  wbc:                 { fresh: 12, stale: 24 },
  platelets:           { fresh: 12, stale: 24 },
  systolic:            { fresh: 3, stale: 6 },
  diastolic:           { fresh: 3, stale: 6 },
  // Wearable: measured in months but much shorter windows
  resting_hr:          { fresh: 0.5, stale: 1 },
  sleep_duration_avg:  { fresh: 0.5, stale: 1 },
  sleep_regularity_stddev: { fresh: 0.5, stale: 1 },
  daily_steps_avg:     { fresh: 1, stale: 2 },
  vo2_max:             { fresh: 1, stale: 3 },
  hrv_rmssd_avg:       { fresh: 0.5, stale: 1 },
  // Manual / static
  has_family_history:  { fresh: 120, stale: 240 },
  has_medication_list: { fresh: 3, stale: 6 },
  waist_circumference: { fresh: 3, stale: 6 },
  weight_lbs:          { fresh: 1, stale: 3 },
  zone2_min_per_week:  { fresh: 1, stale: 3 },
  phq9_score:          { fresh: 3, stale: 6 },
  smoking_status:      { fresh: 6, stale: 12 },
};

function monthsBetween(d1, d2) {
  return (d2.getFullYear() - d1.getFullYear()) * 12 + (d2.getMonth() - d1.getMonth())
    + (d2.getDate() - d1.getDate()) / 30;
}

function getFreshness(metric, drawDate, now) {
  if (!drawDate) return 0.5; // legacy data with no date: half credit

  const monthsAgo = monthsBetween(new Date(drawDate), now || new Date());
  const windows = FRESHNESS_WINDOWS[metric];
  if (!windows) return 1.0; // unknown metric = full credit

  if (monthsAgo <= windows.fresh) return 1.0;
  if (monthsAgo >= windows.stale) return 0.0;
  return 1.0 - (monthsAgo - windows.fresh) / (windows.stale - windows.fresh);
}

// ---------------------------------------------------------------------------
// Reliability — measurement quality multiplier
// ---------------------------------------------------------------------------

function getReliability(metric, observations, imports) {
  // hs-CRP: single reading = 60% reliability (CVI is 42%)
  if (metric === 'hscrp') {
    return observations.length >= 2 ? 1.0 : 0.6;
  }

  // Fasting-sensitive metrics: check if the import was fasting
  if (['triglycerides', 'fasting_glucose', 'fasting_insulin'].includes(metric)) {
    const latest = observations[0];
    if (latest?.import_id && imports) {
      const imp = imports.find(i => i.id === latest.import_id);
      if (imp?.fasting === false) return 0.7;
    }
  }

  return 1.0;
}

// ---------------------------------------------------------------------------
// Trend Detection — using Reference Change Values (RCV)
// ---------------------------------------------------------------------------

// RCV thresholds (%) — minimum change that exceeds biological + analytical variation
// RCV = 2.77 × sqrt(CVI² + CVA²)
const RCV_THRESHOLDS = {
  apob: 15,
  ldl_c: 23,
  hdl_c: 20,
  triglycerides: 35,
  fasting_glucose: 14,
  fasting_insulin: 40,
  hba1c: 9,
  hscrp: 120,  // extremely variable
  tsh: 30,
  vitamin_d: 25,
  ferritin: 30,
  hemoglobin: 8,
  alt: 35,
  ggt: 28,
  resting_hr: 12,
  weight_lbs: 5,
};

function detectTrend(metric, observations) {
  if (observations.length < 2) return null;

  const newest = observations[0];
  const oldest = observations[observations.length - 1];

  if (newest.value == null || oldest.value == null) return null;
  if (!newest.date || !oldest.date) return null;

  const pctChange = ((newest.value - oldest.value) / oldest.value) * 100;
  const spanMonths = monthsBetween(new Date(oldest.date), new Date(newest.date));

  const rcv = RCV_THRESHOLDS[metric];
  const significant = rcv ? Math.abs(pctChange) >= rcv : Math.abs(pctChange) >= 20;

  // All points chronological (oldest → newest) for sparkline rendering
  const points = observations
    .filter(o => o.value != null && o.date)
    .sort((a, b) => new Date(a.date) - new Date(b.date))
    .map(o => ({ value: o.value, date: o.date }));

  return {
    direction: Math.abs(pctChange) < 2 ? 'stable' : pctChange > 0 ? 'rising' : 'falling',
    pctChange: Math.round(pctChange * 10) / 10,
    significant,
    spanMonths: Math.round(spanMonths),
    dataPoints: observations.length,
    newest: { value: newest.value, date: newest.date },
    oldest: { value: oldest.value, date: oldest.date },
    points,
  };
}

// ---------------------------------------------------------------------------
// Score a time-series profile (v2)
// ---------------------------------------------------------------------------

// Maps metric field names to the scoring category they belong to
const METRIC_TO_CATEGORY = {
  systolic: 'blood_pressure', diastolic: 'blood_pressure',
  apob: 'lipid_apob', ldl_c: 'lipid_apob', hdl_c: 'lipid_apob', triglycerides: 'lipid_apob',
  fasting_glucose: 'metabolic', hba1c: 'metabolic', fasting_insulin: 'metabolic',
  has_family_history: 'family_history',
  sleep_duration_avg: 'sleep_duration', sleep_regularity_stddev: 'sleep_regularity',
  daily_steps_avg: 'steps',
  resting_hr: 'resting_hr',
  waist_circumference: 'waist',
  has_medication_list: 'medications',
  lpa: 'lpa',
  vo2_max: 'vo2_max',
  hrv_rmssd_avg: 'hrv',
  hscrp: 'hscrp',
  alt: 'liver', ggt: 'liver',
  hemoglobin: 'cbc', wbc: 'cbc', platelets: 'cbc',
  tsh: 'thyroid',
  vitamin_d: 'vitamin_d_ferritin', ferritin: 'vitamin_d_ferritin',
  weight_lbs: 'weight_trends',
  phq9_score: 'phq9',
  zone2_min_per_week: 'zone2',
};

/**
 * Score a v2 time-series profile.
 * Input: { demographics, observations: { metric: [...] }, imports: [...] }
 * Adapts observations to the flat format scoreProfile() expects,
 * then enriches results with freshness, reliability, and trends.
 */
function scoreTimeSeriesProfile(tsProfile) {
  const now = new Date();
  const obs = tsProfile.observations || {};
  const imports = tsProfile.imports || [];

  // Build a flat profile for backward-compatible scoring
  const flat = { demographics: tsProfile.demographics };

  // Helper: get latest value for a metric
  function latest(metric) {
    const arr = obs[metric];
    if (!arr || arr.length === 0) return null;
    return arr[0]?.value ?? null;
  }

  // Map all metrics to flat profile
  flat.systolic = latest('systolic');
  flat.diastolic = latest('diastolic');
  flat.apob = latest('apob');
  flat.ldl_c = latest('ldl_c');
  flat.hdl_c = latest('hdl_c');
  flat.triglycerides = latest('triglycerides');
  flat.fasting_glucose = latest('fasting_glucose');
  flat.hba1c = latest('hba1c');
  flat.fasting_insulin = latest('fasting_insulin');
  flat.has_family_history = latest('has_family_history');
  flat.sleep_regularity_stddev = latest('sleep_regularity_stddev');
  flat.sleep_duration_avg = latest('sleep_duration_avg');
  flat.daily_steps_avg = latest('daily_steps_avg');
  flat.resting_hr = latest('resting_hr');
  flat.waist_circumference = latest('waist_circumference');
  flat.has_medication_list = latest('has_medication_list');
  flat.lpa = latest('lpa');
  flat.vo2_max = latest('vo2_max');
  flat.hrv_rmssd_avg = latest('hrv_rmssd_avg');
  flat.hscrp = latest('hscrp');
  flat.alt = latest('alt');
  flat.ggt = latest('ggt');
  flat.hemoglobin = latest('hemoglobin');
  flat.wbc = latest('wbc');
  flat.platelets = latest('platelets');
  flat.tsh = latest('tsh');
  flat.vitamin_d = latest('vitamin_d');
  flat.ferritin = latest('ferritin');
  flat.weight_lbs = latest('weight_lbs');
  flat.phq9_score = latest('phq9_score');
  flat.zone2_min_per_week = latest('zone2_min_per_week');
  flat.smoking_status = latest('smoking_status');

  // Run base scoring
  const baseResult = scoreProfile(flat);

  // Enrich each result with freshness, reliability, and trends
  const metricFreshness = {};
  const metricTrends = {};

  for (const [metric, metricObs] of Object.entries(obs)) {
    if (metricObs.length === 0) continue;

    const latestObs = metricObs[0];
    const freshness = getFreshness(metric, latestObs.date, now);
    const reliability = getReliability(metric, metricObs, imports);
    const trend = detectTrend(metric, metricObs);

    const cat = METRIC_TO_CATEGORY[metric];
    if (cat) {
      // Store the worst freshness for this category (if multiple metrics map to same category)
      if (metricFreshness[cat] == null || freshness < metricFreshness[cat].freshness) {
        metricFreshness[cat] = { freshness, reliability, metric };
      }
      if (trend && trend.significant) {
        if (!metricTrends[cat]) metricTrends[cat] = [];
        metricTrends[cat].push({ metric, ...trend });
      }
    }
  }

  // Apply freshness to results
  for (const result of baseResult.results) {
    const catKey = Object.entries({ ...TIER1_WEIGHTS, ...TIER2_WEIGHTS })
      .find(([, w]) => w === result.weight && result.name);

    // Match result to category by name
    const catMap = {
      'Blood Pressure': 'blood_pressure',
      'Lipid Panel + ApoB': 'lipid_apob',
      'Metabolic Panel': 'metabolic',
      'Family History': 'family_history',
      'Sleep Duration': 'sleep_duration',
      'Sleep Regularity': 'sleep_regularity',
      'Daily Steps': 'steps',
      'Resting Heart Rate': 'resting_hr',
      'Waist Circumference': 'waist',
      'Medication List': 'medications',
      'Lp(a)': 'lpa',
      'VO2 Max': 'vo2_max',
      'HRV (7-day avg)': 'hrv',
      'hs-CRP': 'hscrp',
      'Liver Enzymes': 'liver',
      'CBC': 'cbc',
      'Thyroid (TSH)': 'thyroid',
      'Vitamin D + Ferritin': 'vitamin_d_ferritin',
      'Weight Trends': 'weight_trends',
      'PHQ-9 (Depression)': 'phq9',
      'Zone 2 Cardio': 'zone2',
    };

    const cat = catMap[result.name];
    if (cat && metricFreshness[cat]) {
      result.freshness = metricFreshness[cat].freshness;
      result.reliability = metricFreshness[cat].reliability;
      result.freshnessMetric = metricFreshness[cat].metric; // for UI window lookup
      result.effectiveWeight = result.weight * result.freshness * result.reliability;
    } else {
      result.freshness = result.hasData ? 1.0 : 0;
      result.reliability = 1.0;
      result.effectiveWeight = result.hasData ? result.weight : 0;
    }

    result.trends = metricTrends[cat] || [];
  }

  // Recompute coverage using effective weights (freshness-adjusted)
  const allWeights = { ...TIER1_WEIGHTS, ...TIER2_WEIGHTS };
  const totalWeight = Object.values(allWeights).reduce((a, b) => a + b, 0);

  const effectiveCoveredWeight = baseResult.results
    .reduce((sum, r) => sum + (r.effectiveWeight || 0), 0);
  const freshnessAdjustedCoverage = Math.round(effectiveCoveredWeight / totalWeight * 100);

  return {
    ...baseResult,
    freshnessAdjustedCoverage,
    rawCoverage: baseResult.coverageScore,
    coverageScore: freshnessAdjustedCoverage,
    importCount: imports.length,
    observationMetrics: Object.keys(obs).filter(m => obs[m].length > 0),
  };
}

export {
  scoreProfile,
  scoreTimeSeriesProfile,
  Standing,
  ageBucket,
  TIER1_WEIGHTS,
  TIER2_WEIGHTS,
  FRESHNESS_WINDOWS,
  getFreshness,
  getReliability,
  detectTrend,
  RCV_THRESHOLDS,
};
