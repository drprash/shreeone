const DAY_MS = 24 * 60 * 60 * 1000;

function startOfDay(d) {
  const out = new Date(d);
  out.setHours(0, 0, 0, 0);
  return out;
}

/**
 * Returns { start, end } Date objects for the period at the given offset
 * from the current period. offset=0 is current, -1 is previous, +1 is next.
 * Weeks start on Monday (ISO 8601).
 */
export function getPeriodDates(mode, offset = 0) {
  const today = startOfDay(new Date());

  if (mode === 'W') {
    const dow = today.getDay(); // 0=Sun
    const daysFromMonday = (dow + 6) % 7;
    const monday = new Date(today.getTime() - daysFromMonday * DAY_MS + offset * 7 * DAY_MS);
    return { start: monday, end: new Date(monday.getTime() + 6 * DAY_MS) };
  }

  if (mode === 'M') {
    const base = new Date(today.getFullYear(), today.getMonth() + offset, 1);
    return {
      start: new Date(base.getFullYear(), base.getMonth(), 1),
      end: new Date(base.getFullYear(), base.getMonth() + 1, 0),
    };
  }

  if (mode === 'Q') {
    const currentQ = Math.floor(today.getMonth() / 3);
    const totalQ = currentQ + offset;
    const yearAdj = Math.floor(totalQ / 4);
    const q = ((totalQ % 4) + 4) % 4;
    const year = today.getFullYear() + yearAdj;
    return {
      start: new Date(year, q * 3, 1),
      end: new Date(year, q * 3 + 3, 0),
    };
  }

  if (mode === 'Y') {
    const year = today.getFullYear() + offset;
    return { start: new Date(year, 0, 1), end: new Date(year, 11, 31) };
  }

  return { start: today, end: today };
}

/** Format a Date as YYYY-MM-DD for API query params and date inputs. */
export function formatDateParam(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Human-readable label for the period ("May 2026", "Q2 2026", "Week of 4 May", "2026"). */
export function getPeriodLabel(mode, start) {
  if (mode === 'W') {
    return `Week of ${start.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}`;
  }
  if (mode === 'M') {
    return start.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  }
  if (mode === 'Q') {
    const q = Math.floor(start.getMonth() / 3) + 1;
    return `Q${q} ${start.getFullYear()}`;
  }
  if (mode === 'Y') {
    return String(start.getFullYear());
  }
  return '';
}

/** Short label for the prior period used in trend badges ("Apr", "last week", "Q1 2026", "2025"). */
export function getPriorPeriodLabel(mode, currentStart) {
  if (mode === 'W') return 'last week';
  if (mode === 'M') {
    const prev = new Date(currentStart.getFullYear(), currentStart.getMonth() - 1, 1);
    return prev.toLocaleDateString('en-US', { month: 'short' });
  }
  if (mode === 'Q') {
    const q = Math.floor(currentStart.getMonth() / 3) + 1;
    const prevQ = q === 1 ? 4 : q - 1;
    const prevYear = q === 1 ? currentStart.getFullYear() - 1 : currentStart.getFullYear();
    return `Q${prevQ} ${prevYear}`;
  }
  if (mode === 'Y') return String(currentStart.getFullYear() - 1);
  return 'prior period';
}

/** True when the period end is today or in the future — disables the → stepper button. */
export function isFuturePeriodEnd(end) {
  const today = startOfDay(new Date());
  return startOfDay(end) >= today;
}

/**
 * Given a date picked from the calendar, compute the offset (relative to today's
 * period) of the period that contains that date.
 */
export function offsetForDate(mode, picked) {
  const today = startOfDay(new Date());
  const p = startOfDay(picked);

  if (mode === 'W') {
    const todayMonday = new Date(today.getTime() - ((today.getDay() + 6) % 7) * DAY_MS);
    const pickedMonday = new Date(p.getTime() - ((p.getDay() + 6) % 7) * DAY_MS);
    return Math.round((pickedMonday - todayMonday) / (7 * DAY_MS));
  }
  if (mode === 'M') {
    return (p.getFullYear() - today.getFullYear()) * 12 + (p.getMonth() - today.getMonth());
  }
  if (mode === 'Q') {
    const currentQ = Math.floor(today.getMonth() / 3) + today.getFullYear() * 4;
    const pickedQ = Math.floor(p.getMonth() / 3) + p.getFullYear() * 4;
    return pickedQ - currentQ;
  }
  if (mode === 'Y') {
    return p.getFullYear() - today.getFullYear();
  }
  return 0;
}

/** Choose chart bar granularity based on period duration in days. */
export function getGranularity(startStr, endStr) {
  const start = new Date(startStr + 'T00:00:00');
  const end = new Date(endStr + 'T00:00:00');
  const days = Math.round((end - start) / DAY_MS) + 1;
  if (days <= 31) return 'day';
  if (days <= 92) return 'week';
  return 'month';
}

/**
 * Group daily totals from the API into weekly or monthly buckets for the chart.
 * Returns the same shape: [{ date, income, expenses }] sorted ascending by date.
 */
export function aggregateDailyTotals(dailyTotals, granularity) {
  if (!dailyTotals || dailyTotals.length === 0) return [];
  if (granularity === 'day') return dailyTotals;

  const buckets = {};

  dailyTotals.forEach(({ date, income, expenses }) => {
    const d = new Date(date + 'T00:00:00');
    let key;
    if (granularity === 'week') {
      const daysFromMonday = (d.getDay() + 6) % 7;
      const monday = new Date(d.getTime() - daysFromMonday * DAY_MS);
      key = formatDateParam(monday);
    } else {
      key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
    }
    if (!buckets[key]) buckets[key] = { date: key, income: 0, expenses: 0 };
    buckets[key].income += Number(income);
    buckets[key].expenses += Number(expenses);
  });

  return Object.values(buckets).sort((a, b) => a.date.localeCompare(b.date));
}
