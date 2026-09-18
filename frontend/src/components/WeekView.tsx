"use client";

import { useMemo } from "react";
import type { Appointment } from "@/types";

interface WeekViewProps {
  weekStart: Date; // Monday
  appointments: Appointment[];
  onSelectDate: (date: Date) => void;
  onPrevWeek: () => void;
  onNextWeek: () => void;
  onToday: () => void;
}

const HOURS = Array.from({ length: 16 }, (_, i) => i + 6); // 6 AM to 9 PM

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function isToday(date: Date): boolean {
  return isSameDay(date, new Date());
}

function formatHour(hour: number): string {
  if (hour === 0) return "12 AM";
  if (hour < 12) return `${hour} AM`;
  if (hour === 12) return "12 PM";
  return `${hour - 12} PM`;
}

export default function WeekView({
  weekStart,
  appointments,
  onSelectDate,
  onPrevWeek,
  onNextWeek,
  onToday,
}: WeekViewProps) {
  const days = useMemo(() => {
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(weekStart);
      d.setDate(d.getDate() + i);
      return d;
    });
  }, [weekStart]);

  const weekLabel = `${days[0].toLocaleString("en-US", { month: "short", day: "numeric" })} – ${days[6].toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric" })}`;

  // Build appointment map by day key
  const appointmentMap = useMemo(() => {
    const map = new Map<string, Appointment[]>();
    for (const appt of appointments) {
      const d = new Date(appt.start_time);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(appt);
    }
    return map;
  }, [appointments]);

  const getDayKey = (date: Date) =>
    `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

  const getApptPosition = (appt: Appointment) => {
    const start = new Date(appt.start_time);
    const end = new Date(appt.end_time);
    const startHour = start.getHours() + start.getMinutes() / 60;
    const endHour = end.getHours() + end.getMinutes() / 60;
    const top = ((startHour - 6) / 16) * 100; // 6 AM = 0%, 9 PM = 100%
    const height = ((endHour - startHour) / 16) * 100;
    return { top: `${top}%`, height: `${Math.max(height, 2)}%` };
  };

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-200 dark:border-zinc-800">
        <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
          {weekLabel}
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={onToday}
            className="px-3 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
          >
            Today
          </button>
          <button
            onClick={onPrevWeek}
            className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
          >
            <svg className="w-5 h-5 text-zinc-600 dark:text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <button
            onClick={onNextWeek}
            className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
          >
            <svg className="w-5 h-5 text-zinc-600 dark:text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-8 border-b border-zinc-200 dark:border-zinc-800">
        <div className="py-2" /> {/* Time gutter */}
        {days.map((day) => {
          const today = isToday(day);
          return (
            <button
              key={day.toISOString()}
              onClick={() => onSelectDate(day)}
              className={`py-2 text-center border-l border-zinc-100 dark:border-zinc-800/50 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors ${
                today ? "bg-blue-50/50 dark:bg-blue-900/10" : ""
              }`}
            >
              <div className="text-xs text-zinc-500 dark:text-zinc-400">
                {day.toLocaleString("en-US", { weekday: "short" })}
              </div>
              <div
                className={`text-sm font-semibold mt-0.5 ${
                  today
                    ? "bg-blue-600 text-white w-7 h-7 rounded-full flex items-center justify-center mx-auto"
                    : "text-zinc-900 dark:text-zinc-100"
                }`}
              >
                {day.getDate()}
              </div>
            </button>
          );
        })}
      </div>

      {/* Time grid */}
      <div className="grid grid-cols-8 overflow-y-auto" style={{ maxHeight: "600px" }}>
        {/* Time gutter */}
        <div className="relative">
          {HOURS.map((hour) => (
            <div
              key={hour}
              className="h-12 border-b border-zinc-100 dark:border-zinc-800/50 flex items-start justify-end pr-2"
            >
              <span className="text-[10px] text-zinc-400 dark:text-zinc-500 -mt-2">
                {formatHour(hour)}
              </span>
            </div>
          ))}
        </div>

        {/* Day columns */}
        {days.map((day) => {
          const key = getDayKey(day);
          const dayAppts = appointmentMap.get(key) || [];

          return (
            <div
              key={day.toISOString()}
              className="relative border-l border-zinc-100 dark:border-zinc-800/50"
            >
              {/* Hour lines */}
              {HOURS.map((hour) => (
                <div
                  key={hour}
                  className="h-12 border-b border-zinc-100 dark:border-zinc-800/50"
                />
              ))}

              {/* Appointments */}
              {dayAppts.map((appt) => {
                const pos = getApptPosition(appt);
                const isScheduled = appt.status === "scheduled";
                return (
                  <div
                    key={appt.id}
                    className={`absolute left-0.5 right-0.5 rounded px-1 py-0.5 text-[10px] leading-tight overflow-hidden cursor-pointer ${
                      isScheduled
                        ? "bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 border border-blue-200 dark:border-blue-800"
                        : "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-700"
                    }`}
                    style={{ top: pos.top, height: pos.height }}
                    title={`${appt.title} (${appt.duration_minutes}min)`}
                  >
                    <div className="font-medium truncate">{appt.title}</div>
                    <div className="truncate opacity-75">
                      {new Date(appt.start_time).toLocaleTimeString("en-US", {
                        hour: "numeric",
                        minute: "2-digit",
                        hour12: true,
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
