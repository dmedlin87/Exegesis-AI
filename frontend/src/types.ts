export interface ServiceMetrics {
    exegesis_service_status?: number;
    exegesis_service_restarts?: number;
    exegesis_service_average_response_ms?: number;
    exegesis_service_working_set_bytes?: number;
    exegesis_service_uptime_seconds?: number;
    exegesis_service_last_response_ms?: number;
    exegesis_service_cpu_seconds_total?: number;
    [key: string]: number | undefined;
}

export interface MetricsData {
    [serviceName: string]: ServiceMetrics;
}
