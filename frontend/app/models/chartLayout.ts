/** Layout only: swap the two selected slots without shifting other charts. */
export function swapCharts<T extends { id: string }>(charts: T[], sourceId: string, targetId: string): T[] {
  const source = charts.findIndex(chart => chart.id === sourceId);
  const target = charts.findIndex(chart => chart.id === targetId);
  if (source < 0 || target < 0 || source === target) return charts;
  const next = [...charts];
  [next[source], next[target]] = [next[target], next[source]];
  return next;
}
