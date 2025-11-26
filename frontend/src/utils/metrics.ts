import type { MetricsData } from '../types';

export function parseMetrics(text: string): MetricsData {
  const lines = text.split('\n').filter(Boolean);
  const metrics: MetricsData = {};

  for (const line of lines) {
    if (line.startsWith('#')) continue;

    // Match Prometheus format: metric_name{label="value",...} value
    const match = line.match(/^(\w+)\{([^}]*)\}\s+([0-9eE+\-.]+)/);
    let metricName: string;
    let labelString: string | undefined;
    let value: string;
    let labels: Record<string, string> = {};

    if (match) {
      [, metricName, labelString, value] = match;
      if (labelString) {
        labels = Object.fromEntries(
          labelString.split(',').map((kv) => {
            const parts = kv.split('=');
            if (parts.length >= 2) {
              return [parts[0], parts.slice(1).join('=').replace(/"/g, '')];
            }
            return [parts[0], ''];
          })
        );
      }
    } else {
      // Fallback for simple format: metric_name value
      const fallback = line.match(/^(\w+)\s+([0-9eE+\-.]+)/);
      if (!fallback) continue;
      [, metricName, value] = fallback;
      labels = { service: 'manager' };
    }

    const key = labels.service || 'default';
    if (!metrics[key]) {
      metrics[key] = {};
    }

    metrics[key][metricName] = Number(value);
  }

  return metrics;
}

export function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}
