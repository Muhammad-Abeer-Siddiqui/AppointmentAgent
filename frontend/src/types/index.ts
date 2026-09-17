export interface User {
  id: number;
  name: string;
  email: string;
  timezone: string;
  locale: string;
}

export interface Appointment {
  id: number;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  status: string;
}

export interface Preferences {
  preferred_earliest_time: string;
  preferred_latest_time: string;
  avoid_lunch: boolean;
  min_break_minutes: number;
  preferred_duration_minutes: number;
}

export interface WorkingHours {
  day_of_week: number;
  start_time: string;
  end_time: string;
  is_off_day: boolean;
}

export interface GoogleStatus {
  connected: boolean;
  email?: string;
}

export interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
  suggestions?: AvailableSlot[];
}

export interface ToolCall {
  name: string;
  arguments: Record<string, any>;
  result?: any;
}

export interface AvailableSlot {
  start: string;
  end: string;
  score: number;
  id?: string;
}

export interface PendingConfirmation {
  action: string;
  details: string;
  appointmentId?: number;
}

export type PendingConfirmationState = PendingConfirmation | null;
