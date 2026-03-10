/**
 * Baseline — NHANES Percentile Lookup (Client-side)
 *
 * Ports nhanes/percentile_lookup.py → JavaScript
 * Embeds nhanes_percentiles.json data inline.
 * Uses linear interpolation (replaces numpy.interp).
 */

let _nhanesData = null;

/**
 * Linear interpolation — replaces numpy.interp
 * Given x, find y by interpolating between arrays xp (ascending) and fp.
 */
function linearInterp(x, xp, fp) {
  if (x <= xp[0]) return fp[0];
  if (x >= xp[xp.length - 1]) return fp[fp.length - 1];
  for (let i = 1; i < xp.length; i++) {
    if (x <= xp[i]) {
      const t = (x - xp[i - 1]) / (xp[i] - xp[i - 1]);
      return fp[i - 1] + t * (fp[i] - fp[i - 1]);
    }
  }
  return fp[fp.length - 1];
}

/**
 * Load NHANES data (fetched once, cached).
 */
async function loadNhanes() {
  if (_nhanesData) return _nhanesData;
  const resp = await fetch('nhanes_percentiles.json');
  if (!resp.ok) throw new Error(`NHANES fetch failed: ${resp.status}`);
  const ct = resp.headers.get('content-type') || '';
  if (!ct.includes('json')) throw new Error(`NHANES fetch returned non-JSON: ${ct}`);
  _nhanesData = await resp.json();
  return _nhanesData;
}

/**
 * Set NHANES data directly (for inline embedding).
 */
function setNhanesData(data) {
  _nhanesData = data;
}

/**
 * Get population percentile for a biomarker value.
 *
 * @param {string} metricKey - Key in nhanes_percentiles.json
 * @param {number} value - The biomarker value
 * @param {string} ageBucket - e.g., "30-39"
 * @param {string} sex - "M" or "F"
 * @returns {number|null} Percentile 0-100 ("% of population you're better than") or null
 */
function getPercentile(metricKey, value, ageBucket, sex) {
  if (!_nhanesData) return null;

  const metric = _nhanesData.metrics[metricKey];
  if (!metric) return null;

  const groupKey = `${ageBucket}|${sex}`;
  const group = metric.groups[groupKey] || metric.groups['universal'];
  if (!group) return null;

  const pctPoints = _nhanesData.percentile_points; // [1, 5, 10, ..., 99]
  const pctValues = pctPoints.map(p => group.percentiles[String(p)]);

  // Interpolate: given a value, find the population percentile
  let rawPercentile = linearInterp(value, pctValues, pctPoints);

  // Clamp to 1-99
  rawPercentile = Math.max(1.0, Math.min(99.0, rawPercentile));

  if (metric.lower_is_better) {
    // Lower value = better standing, so invert
    return Math.round((100.0 - rawPercentile) * 10) / 10;
  } else {
    return Math.round(rawPercentile * 10) / 10;
  }
}

export { loadNhanes, setNhanesData, getPercentile, linearInterp };
