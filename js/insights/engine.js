/**
 * Health Engine — Insight Generation (Client-side)
 *
 * Generates actionable health insights from wearable + health data.
 * Ported from dashboard.js generateInsights().
 */

/**
 * Generate health insights from available data.
 *
 * @param {Object} garmin - Garmin data (hrv_rmssd_avg, resting_hr, sleep_duration_avg, etc.)
 * @param {Array} weights - Array of {weight} objects, chronologically ordered
 * @param {Array} bpReadings - Array of {sys, dia} objects
 * @param {Object} trends - {rhrPts: [{rhr}], hrvPts: [{hrv}]} arrays
 * @param {Object} thresholds - Override default thresholds
 * @returns {Array} Array of insight objects
 */
export function generateInsights(garmin, weights, bpReadings, trends, thresholds) {
  const t = Object.assign({
    hrvCritical: 50,
    hrvWarning: 55,
    hrvHealthy: 65,
    rhrElevated: 55,
    rhrExcellent: 50,
    sleepTarget: 7,
    sleepRegHigh: 60,
    zone2Target: 150,
    zone2Low: 90,
    fastLoss: 2.0,
  }, thresholds || {});

  var insights = [];
  var g = garmin || {};
  var hrv = g.hrv_rmssd_avg;
  var rhr = g.resting_hr;
  var sleepHrs = g.sleep_duration_avg;
  var sleepReg = g.sleep_regularity_stddev;
  var zone2 = g.zone2_min_per_week;

  var rhrTrend = null, hrvTrend = null;
  if (trends) {
    if (trends.rhrPts && trends.rhrPts.length >= 14) {
      var re = trends.rhrPts.slice(0, 14).reduce(function(s, d) { return s + d.rhr; }, 0) / 14;
      var rl = trends.rhrPts.slice(-14).reduce(function(s, d) { return s + d.rhr; }, 0) / 14;
      rhrTrend = { early: re, late: rl, delta: rl - re };
    }
    if (trends.hrvPts && trends.hrvPts.length >= 14) {
      var he = trends.hrvPts.slice(0, 14).reduce(function(s, d) { return s + d.hrv; }, 0) / 14;
      var hl = trends.hrvPts.slice(-14).reduce(function(s, d) { return s + d.hrv; }, 0) / 14;
      hrvTrend = { early: he, late: hl, delta: hl - he };
    }
  }

  var weeklyRate = null;
  if (weights && weights.length >= 7) {
    var recent = weights[weights.length - 1].weight;
    var weekAgo = weights[Math.max(0, weights.length - 8)].weight;
    weeklyRate = weekAgo - recent;
  }

  // HRV
  if (hrv != null) {
    var hrvTrendNote = formatTrendNote(hrvTrend, 'ms');

    if (hrv < t.hrvCritical) {
      insights.push({ severity: 'critical', category: 'hrv',
        title: 'HRV below ' + t.hrvCritical + 'ms \u2014 recovery warning',
        body: 'Sustained HRV below ' + t.hrvCritical + 'ms signals overreaching. Consider a refeed day, extra sleep, or reducing training volume.' + hrvTrendNote });
    } else if (hrv < t.hrvWarning) {
      insights.push({ severity: 'warning', category: 'hrv',
        title: 'HRV approaching warning zone (' + hrv.toFixed(1) + 'ms)',
        body: 'Getting close to the ' + t.hrvCritical + 'ms threshold. Prioritize sleep over training intensity this week.' + hrvTrendNote });
    } else if (hrv >= t.hrvHealthy) {
      insights.push({ severity: 'positive', category: 'hrv',
        title: 'HRV solid at ' + hrv.toFixed(1) + 'ms',
        body: 'Parasympathetic tone is healthy. Recovery capacity is good.' + hrvTrendNote });
    } else {
      insights.push({ severity: 'neutral', category: 'hrv',
        title: 'HRV at ' + hrv.toFixed(1) + 'ms \u2014 mid-range',
        body: 'Within normal range for someone in a caloric deficit.' + hrvTrendNote });
    }
  }

  // Sleep + HRV interaction
  if (sleepHrs != null && sleepHrs < t.sleepTarget) {
    if (hrv != null && hrv < 60) {
      insights.push({ severity: 'warning', category: 'sleep',
        title: 'Sleep deficit dragging HRV down',
        body: 'Averaging ' + sleepHrs.toFixed(1) + ' hrs \u2014 below the ' + t.sleepTarget + 'hr target. This is likely suppressing your HRV. An extra 30-45 min of sleep would likely move HRV more than any supplement.' });
    } else {
      insights.push({ severity: 'warning', category: 'sleep',
        title: 'Sleep below target (' + sleepHrs.toFixed(1) + ' hrs)',
        body: 'Averaging ' + sleepHrs.toFixed(1) + ' hrs \u2014 below the ' + t.sleepTarget + 'hr target. Recovery markers are holding for now, but chronic sub-' + t.sleepTarget + 'hr sleep compounds over weeks.' });
    }
  }

  // Sleep regularity
  if (sleepReg != null && sleepReg > t.sleepRegHigh) {
    insights.push({ severity: 'warning', category: 'sleep',
      title: 'Bedtime variance high (\u00b1' + Math.round(sleepReg) + ' min)',
      body: 'Irregular sleep timing disrupts circadian rhythm independent of duration. A consistent wake time (even on weekends) is the single most effective fix. Aim for <45 min stdev.' });
  }

  // RHR
  if (rhr != null) {
    var rhrTrendNote = formatTrendNote(rhrTrend, 'bpm', true);

    if (rhr > t.rhrElevated) {
      insights.push({ severity: 'critical', category: 'rhr',
        title: 'Resting HR elevated (' + rhr.toFixed(1) + ' bpm)',
        body: 'RHR above ' + t.rhrElevated + ' during a cut signals systemic stress. Consider a diet break or deload week.' + rhrTrendNote });
    } else if (rhr < t.rhrExcellent) {
      insights.push({ severity: 'positive', category: 'rhr',
        title: 'Resting HR excellent (' + rhr.toFixed(1) + ' bpm)',
        body: 'Sub-' + t.rhrExcellent + ' RHR indicates strong cardiovascular fitness and adequate recovery.' + rhrTrendNote });
    } else {
      insights.push({ severity: 'neutral', category: 'rhr',
        title: 'Resting HR at ' + rhr.toFixed(1) + ' bpm \u2014 normal range',
        body: 'Within healthy range.' + rhrTrendNote });
    }
  }

  // Zone 2
  if (zone2 != null) {
    if (zone2 >= t.zone2Target) {
      insights.push({ severity: 'positive', category: 'zone2',
        title: 'Zone 2 strong at ' + zone2 + ' min/week',
        body: 'Well above the ' + t.zone2Target + ' min/week recommendation. Zone 2 also supports fat oxidation during a cut.' });
    } else if (zone2 < t.zone2Low) {
      insights.push({ severity: 'warning', category: 'zone2',
        title: 'Zone 2 low (' + zone2 + ' min/week)',
        body: 'Below ' + t.zone2Target + ' min/week target. Even 2-3 brisk walks per week would help.' });
    }
  }

  // Weight rate + recovery interaction
  if (weeklyRate != null && weeklyRate > t.fastLoss && hrv != null && hrv < t.hrvWarning) {
    insights.push({ severity: 'critical', category: 'weight',
      title: 'Fast loss + low HRV \u2014 consider slowing down',
      body: 'Losing ' + weeklyRate.toFixed(1) + ' lbs/week with HRV at ' + hrv.toFixed(1) + 'ms. The deficit may be too aggressive for your current recovery capacity.' });
  }

  // Blood pressure
  if (bpReadings && bpReadings.length) {
    var lastBp = bpReadings[bpReadings.length - 1];
    if (lastBp.sys < t.bpSysOptimal && lastBp.dia < t.bpDiaOptimal) {
      insights.push({ severity: 'positive', category: 'bp',
        title: 'Blood pressure normal (' + lastBp.sys + '/' + lastBp.dia + ')',
        body: 'Optimal range. Continue monitoring — BP tends to improve with weight loss.' });
    } else if (lastBp.sys >= (t.bpSysElevated || 130) || lastBp.dia >= (t.bpDiaOptimal || 80)) {
      insights.push({ severity: 'warning', category: 'bp',
        title: 'Blood pressure elevated (' + lastBp.sys + '/' + lastBp.dia + ')',
        body: 'Above optimal range. Continue daily monitoring to establish a reliable baseline.' });
    }
  }

  return insights;
}

function formatTrendNote(trend, unit, invert) {
  if (!trend) return '';
  var threshold = unit === 'ms' ? 3 : 2;

  if (invert) {
    if (trend.delta < -threshold) {
      return ' 90-day trend: ' + trend.early.toFixed(1) + ' \u2192 ' + trend.late.toFixed(1) + ' ' + unit + ' (\u2193' + Math.abs(trend.delta).toFixed(1) + '). Improving.';
    } else if (trend.delta > threshold) {
      return ' 90-day trend: ' + trend.early.toFixed(1) + ' \u2192 ' + trend.late.toFixed(1) + ' ' + unit + ' (\u2191' + trend.delta.toFixed(1) + '). Watch closely.';
    }
  } else {
    if (trend.delta > threshold) {
      return ' 90-day trend positive: ' + trend.early.toFixed(0) + ' \u2192 ' + trend.late.toFixed(0) + unit + ' (+' + trend.delta.toFixed(1) + '). Building.';
    } else if (trend.delta < -threshold) {
      return ' 90-day trend declining: ' + trend.early.toFixed(0) + ' \u2192 ' + trend.late.toFixed(0) + unit + ' (' + trend.delta.toFixed(1) + '). Watch closely.';
    }
  }
  return ' 90-day trend stable: ' + trend.early.toFixed(1) + ' \u2192 ' + trend.late.toFixed(1) + ' ' + unit + '. Holding steady.';
}
