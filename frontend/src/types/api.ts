export interface WelcomeResponse {
  message: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  services?: Record<string, string>;
}

export interface Stop {
  name: string;
  lat: number;
  lon: number;
  order: number;
  time_from_start: number;
  passengers?: number;
  is_school?: boolean;
}

export interface Route {
  id: string;
  name: string;
  stops: Stop[];
  school_id: string;
  school_name: string;
  arrival_time?: string | null;
  departure_time?: string | null;
  capacity_needed: number;
  contract_id: string;
  type: 'entry' | 'exit' | string;
  days?: string[];
}

export interface ScheduleItem {
  route_id: string;
  start_time: string;
  end_time: string;
  type: string;
  capacity_needed?: number;
  original_start_time?: string | null;
  time_shift_minutes?: number;
  deadhead_minutes?: number;
  school_name?: string | null;
  stops?: Stop[];
  contract_id?: string | null;
}

export interface BusSchedule {
  bus_id: string;
  items: ScheduleItem[];
}

export interface ApiError {
  statusCode: number;
  detail: string;
  timestamp: string;
  path: string;
}

export interface UploadProgress {
  filename: string;
  loaded: number;
  total: number;
  percentage: number;
  status: 'uploading' | 'completed' | 'failed';
}
