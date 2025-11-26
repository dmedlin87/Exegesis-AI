import React, { useEffect, useState } from 'react';
import type { MetricsData } from '../types';
import { parseMetrics } from '../utils/metrics';
import { MetricCard } from './MetricCard';

export const Dashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<MetricsData>({});
  const [error, setError] = useState<string | null>(null);

  // Use environment variable or default to localhost
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
        <h1>Theoria Service Health</h1>
        <p>Real-time monitoring dashboard • Updates every 5 seconds</p>
      </header>
      <main>
        {error && (
          <div className="error-banner">
            <span className="error-icon">⚠️</span>
            <p>Metrics unavailable: {error}</p>
          </div>
        )}
        {services.length === 0 && !error && (
          <div className="error-banner">
            <span className="error-icon">ℹ️</span>
            <p>Waiting for service metrics...</p>
          </div>
        )}
        <section className="grid">
          {services.map((service) => (
            <MetricCard key={service} serviceName={service} data={metrics[service]} />
          ))}
        </section>
      </main>
    </div>
  );
};
