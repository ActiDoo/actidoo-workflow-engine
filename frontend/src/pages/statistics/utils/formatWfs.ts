import { DataPoint } from "./Graph";

export function createCountforWFs(
  selectedWorkflow: string,
  workflow_dates: Date[],
  startDate: Date,
  endDate: Date
): { name: string; data: DataPoint[] } {
  const toMidnight = (d: Date) => {
    const date = new Date(d);
    date.setHours(0, 0, 0, 0);
    return date;
  };

  // Count workflow occurrences per day
  const countedWfs: { date: Date; calls: number }[] = [];
  for (const wfDate of workflow_dates) {
    const normalizedDate = toMidnight(wfDate);
    const existingEntry = countedWfs.find(
      entry => entry.date.getTime() === normalizedDate.getTime()
    );
    if (existingEntry) {
      existingEntry.calls += 1;
    } else {
      countedWfs.push({ date: normalizedDate, calls: 1 });
    }
  }

  if (countedWfs.length === 0) {
    return { name: selectedWorkflow, data: [] };
  }

  // Earliest workflow date and baseline
  const earliest = countedWfs.reduce(
    (min, entry) => (entry.date < min ? entry.date : min),
    countedWfs[0].date
  );
  const baselineDefault = new Date(earliest);
  baselineDefault.setDate(baselineDefault.getDate() - 1);

  // Actual start/end bounds
  const actualStart = startDate ? toMidnight(startDate) : baselineDefault;
  const actualEnd = endDate ? toMidnight(endDate) : toMidnight(new Date());

  // Compute cumulative count from baselineDefault up to actualEnd
  let cumulativeCount = 0;
  const dailySeries: DataPoint[] = [];

  const current = new Date(baselineDefault);
  while (current <= actualEnd) {
    const dayMatch = countedWfs.find(entry => entry.date.getTime() === current.getTime());
    cumulativeCount += dayMatch?.calls || 0;
    dailySeries.push({ date: new Date(current), calls: cumulativeCount });
    current.setDate(current.getDate() + 1);
  }

  if (startDate) {
    return {
      name: selectedWorkflow,
      data: dailySeries.filter(d => d.date >= actualStart && d.date <= actualEnd)
    };
  } else {
    // Default: keep the original zero-baseline first point
    // i.e. baselineDefault is included naturally in dailySeries
    return { name: selectedWorkflow, data: dailySeries };
  }
}
