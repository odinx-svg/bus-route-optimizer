// Schedule data structures (matches backend response)
export interface ScheduleItem {
  route_id: string;
  start_time: string;
  end_time: string;
  type: 'entry' | 'exit';
  original_start_time?: string;
  time_shift_minutes?: number;
  deadhead_minutes?: number;
  school_name?: string;
  contract_id?: string;
}

export interface BusSchedule {
  bus_id: string;
  items: ScheduleItem[];
}

// Computed metrics
export interface Metrics {
  totalBuses: number;
  totalRoutes: number;
  avgRoutesPerBus: number;
  totalDeadhead: number;
  efficiency: number;
}

// Chart data
export interface ChartDataPoint {
  name: string;
  routes: number;
}

// Trend direction for indicators
export type TrendDirection = 'up' | 'down' | 'neutral';
