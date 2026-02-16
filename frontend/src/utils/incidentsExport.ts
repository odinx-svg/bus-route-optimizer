export interface IncidentRow {
  day?: string;
  bus_id?: string;
  route_a?: string;
  route_b?: string;
  issue_type?: string;
  severity?: string;
  time_available?: number | null;
  travel_time?: number | null;
  buffer_minutes?: number | null;
  message?: string;
  suggestion?: string;
}

export interface FleetValidationReport {
  generated_at?: string;
  summary?: Record<string, any>;
  days?: Array<Record<string, any>>;
  incidents?: IncidentRow[];
}

const pad = (value: number): string => String(value).padStart(2, '0');

const timestampSuffix = (): string => {
  const d = new Date();
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`;
};

const downloadBlob = (blob: Blob, filename: string): void => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

export const toIncidentRows = (report: FleetValidationReport): IncidentRow[] => {
  return Array.isArray(report?.incidents) ? report.incidents : [];
};

export const downloadIncidentsAsJson = (report: FleetValidationReport): void => {
  const payload = {
    generated_at: report?.generated_at || new Date().toISOString(),
    summary: report?.summary || {},
    days: report?.days || [],
    incidents: toIncidentRows(report),
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
  downloadBlob(blob, `incidencias_${timestampSuffix()}.json`);
};

export const downloadIncidentsAsCsv = (report: FleetValidationReport): void => {
  const rows = toIncidentRows(report);
  const headers = [
    'day',
    'bus_id',
    'route_a',
    'route_b',
    'issue_type',
    'severity',
    'time_available',
    'travel_time',
    'buffer_minutes',
    'message',
    'suggestion',
  ];

  const escape = (value: unknown): string => {
    const text = value === null || value === undefined ? '' : String(value);
    const escaped = text.replace(/"/g, '""');
    return `"${escaped}"`;
  };

  const metadataRows = [
    ['generated_at', report?.generated_at || new Date().toISOString()],
    ['incidents_total', rows.length],
  ];

  const csvLines: string[] = [];
  metadataRows.forEach((meta) => {
    csvLines.push(meta.map(escape).join(','));
  });
  csvLines.push('');
  csvLines.push(headers.join(','));

  rows.forEach((row) => {
    csvLines.push([
      row.day ?? '',
      row.bus_id ?? '',
      row.route_a ?? '',
      row.route_b ?? '',
      row.issue_type ?? '',
      row.severity ?? '',
      row.time_available ?? '',
      row.travel_time ?? '',
      row.buffer_minutes ?? '',
      row.message ?? '',
      row.suggestion ?? '',
    ].map(escape).join(','));
  });

  const blob = new Blob([csvLines.join('\n')], { type: 'text/csv;charset=utf-8' });
  downloadBlob(blob, `incidencias_${timestampSuffix()}.csv`);
};
