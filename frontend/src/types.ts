export interface ServiceMetrics {
    theoria_service_status?: number;
    theoria_service_restarts?: number;
    theoria_service_average_response_ms?: number;
    theoria_service_working_set_bytes?: number;
    theoria_service_uptime_seconds?: number;
    theoria_service_last_response_ms?: number;
    theoria_service_cpu_seconds_total?: number;
    [key: string]: number | undefined;
}

export interface MetricsData {
    [serviceName: string]: ServiceMetrics;
}
