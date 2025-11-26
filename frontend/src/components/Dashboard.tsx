import React, { useEffect, useState } from 'react';
import { DASHBOARD_COPY, ICONS } from '../constants/ui';
import type { MetricsData } from '../types';
import { parseMetrics } from '../utils/metrics';
import { MetricCard } from './MetricCard';

export const Dashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<MetricsData>({});
  const [error, setError] = useState<string | null>(null);

  const metricsUrl = import.meta.env.VITE_METRICS_URL || 'http://localhost:9101/metrics';

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch(metricsUrl);
        if (!response.ok) throw new Error(`Request failed: ${response.status}`);
        const text = await response.text();
        setMetrics(parseMetrics(text));
        setError(null);
      } catch (err: any) {
        setError(err.message);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, [metricsUrl]);

  const services = Object.keys(metrics);

  return (
    <div>
      <header>
        <h1>{DASHBOARD_COPY.title}</h1>
        <p>{DASHBOARD_COPY.subtitle}</p>
      </header>
      <main>
        {error && (
          <div className="error-banner" role="status" aria-live="polite">
            <span className="error-icon" aria-hidden="true">
              {ICONS.alert}
            </span>
            <p>{`${DASHBOARD_COPY.metricsUnavailable}: ${error}`}</p>
          </div>
        )}
        {services.length === 0 && !error && (
          <div className="error-banner" role="status" aria-live="polite">
            <span className="error-icon" aria-hidden="true">
              {ICONS.alert}
            </span>
            <p>{DASHBOARD_COPY.waiting}</p>
          </div>
        )}
        <section className="grid" aria-label="Service metrics">
          {services.map((service) => (
            <MetricCard key={service} serviceName={service} data={metrics[service]} />
          ))}
        </section>
      </main>
    </div>
  );
};
