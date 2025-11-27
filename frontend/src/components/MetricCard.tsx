import React from 'react';
import { FALLBACK_COPY, METRIC_LABELS, METRIC_UNITS, STATUS_COPY } from '../constants/ui';
import type { ServiceMetrics } from '../types';
import { formatUptime } from '../utils/metrics';

interface MetricCardProps {
  serviceName: string;
  data: ServiceMetrics;
}

export const MetricCard: React.FC<MetricCardProps> = ({ serviceName, data }) => {
  const isHealthy = data.exegesis_service_status === 1;
  const status = isHealthy ? STATUS_COPY.healthy : STATUS_COPY.degraded;
  const statusClass = isHealthy ? 'healthy' : 'degraded';
  const restarts = data.exegesis_service_restarts ?? 0;
  const avgResponse = data.exegesis_service_average_response_ms ?? 0;
  const memoryMB = data.exegesis_service_working_set_bytes
    ? data.exegesis_service_working_set_bytes / (1024 * 1024)
    : 0;

  return (
    <div className="card">
      <div className="card-header">
        <h2>{serviceName.toUpperCase()}</h2>
        <div className={`status ${statusClass}`}>
          <span className={`status-indicator ${statusClass}`} />
          {status}
        </div>
      </div>
      <div className="metrics-grid">
        <div className="metric">
          <span className="metric-label">{METRIC_LABELS.uptime}</span>
          <span className="metric-value">
            {formatUptime(data.exegesis_service_uptime_seconds ?? 0)}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">{METRIC_LABELS.restarts}</span>
          <span className={`metric-value ${restarts > 0 ? 'warning' : ''}`}>
            {restarts}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">{METRIC_LABELS.avgResponse}</span>
          <span
            className={`metric-value ${
              avgResponse > 500 ? 'warning' : avgResponse > 1000 ? 'danger' : ''
            }`}
          >
            {avgResponse.toFixed(1)}
            <span className="metric-icon">{METRIC_UNITS.milliseconds}</span>
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">{METRIC_LABELS.lastResponse}</span>
          <span className="metric-value">
            {(data.exegesis_service_last_response_ms ?? 0).toFixed(1)}
            <span className="metric-icon">{METRIC_UNITS.milliseconds}</span>
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">{METRIC_LABELS.cpuTime}</span>
          <span className="metric-value">
            {(data.exegesis_service_cpu_seconds_total ?? 0).toFixed(1)}
            <span className="metric-icon">{METRIC_UNITS.seconds}</span>
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">{METRIC_LABELS.memory}</span>
          <span
            className={`metric-value ${
              memoryMB > 500 ? 'warning' : memoryMB > 1000 ? 'danger' : ''
            }`}
          >
            {memoryMB > 0 ? memoryMB.toFixed(0) : FALLBACK_COPY.notAvailable}
            {memoryMB > 0 && <span className="metric-icon">{METRIC_UNITS.megabytes}</span>}
          </span>
        </div>
      </div>
    </div>
  );
};
