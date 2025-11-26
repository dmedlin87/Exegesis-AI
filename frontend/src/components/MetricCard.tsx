import React from 'react';
import type { ServiceMetrics } from '../types';
import { formatUptime } from '../utils/metrics';

interface MetricCardProps {
  serviceName: string;
  data: ServiceMetrics;
}

export const MetricCard: React.FC<MetricCardProps> = ({ serviceName, data }) => {
  const isHealthy = data.theoria_service_status === 1;
  const status = isHealthy ? 'Healthy' : 'Degraded';
  const statusClass = isHealthy ? 'healthy' : 'degraded';
  const restarts = data.theoria_service_restarts ?? 0;
  const avgResponse = data.theoria_service_average_response_ms ?? 0;
  const memoryMB = data.theoria_service_working_set_bytes
    ? data.theoria_service_working_set_bytes / (1024 * 1024)
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
          <span className="metric-label">Uptime</span>
          <span className="metric-value">
            {formatUptime(data.theoria_service_uptime_seconds ?? 0)}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Restarts</span>
          <span className={`metric-value ${restarts > 0 ? 'warning' : ''}`}>
            {restarts}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Avg Response</span>
          <span
            className={`metric-value ${
              avgResponse > 500 ? 'warning' : avgResponse > 1000 ? 'danger' : ''
            }`}
          >
            {avgResponse.toFixed(1)}
            <span className="metric-icon">ms</span>
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Last Response</span>
          <span className="metric-value">
            {(data.theoria_service_last_response_ms ?? 0).toFixed(1)}
            <span className="metric-icon">ms</span>
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">CPU Time</span>
          <span className="metric-value">
            {(data.theoria_service_cpu_seconds_total ?? 0).toFixed(1)}
            <span className="metric-icon">s</span>
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Memory</span>
          <span
            className={`metric-value ${
              memoryMB > 500 ? 'warning' : memoryMB > 1000 ? 'danger' : ''
            }`}
          >
            {memoryMB > 0 ? memoryMB.toFixed(0) : 'N/A'}
            {memoryMB > 0 && <span className="metric-icon">MB</span>}
          </span>
        </div>
      </div>
    </div>
  );
};
