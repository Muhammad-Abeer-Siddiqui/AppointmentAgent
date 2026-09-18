"use client";

import { useMemo } from "react";
import type { Appointment } from "@/types";

interface MonthCalendarProps {
  year: number;
  month: number; // 0-indexed
  selectedDate: Date;
  appointments: Appointment[];
  onSelectDate: (date: Date) => void;
  onPrevMonth: () => void;
  onNextMonth: () => void;
  onToday: () => void;
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number): number {
  // Returns 0=Mon, 6=Sun
  const day = new Date(year, month, 1).getDay();
  return day === 0 ? 6 : day - 1;
}

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

export default function MonthCalendar({
  year,
  month,
  selectedDate,
  appointments,
  onSelectDate,
  onPrevMonth,
  onNextMonth,
  onToday,
}: MonthCalendarProps) {
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfMonth(year, month);

  const monthName = new Date(year, month).toLocaleString("en-US", {
    month: "long",
    year: "numeric",
  });

  // Build appointment count map keyed by "YYYY-MM-DD"
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

  // Build calendar grid rows
  const cells: (number | null)[] = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const rows: (number | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) {
    rows.push(cells.slice(i, i + 7));
  }

  const getStatusColor = (appts: Appointment[]) => {
    const hasScheduled = appts.some((a) => a.status === "scheduled");
    const hasCancelled = appts.some((a) => a.status === "cancelled");
    if (hasCancelled && !hasScheduled) return "bg-zinc-400 dark:bg-zinc-600";
    return "bg-blue-500 dark:bg-blue-400";
  };

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-200 dark:border-zinc-800">
        <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
          {monthName}
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={onToday}
            className="px-3 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
          >
            Today
          </button>
          <button
            onClick={onPrevMonth}
            className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
          >
            <svg className="w-5 h-5 text-zinc-600 dark:text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <button
            onClick={onNextMonth}
            className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
          >
            <svg className="w-5 h-5 text-zinc-600 dark:text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Weekday headers */}
      <div className="grid grid-cols-7 border-b border-zinc-200 dark:border-zinc-800">
        {WEEKDAYS.map((day) => (
          <div
            key={day}
            className="py-2 text-center text-xs font-medium text-zinc-500 dark:text-zinc-400"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Day grid */}
      <div className="grid grid-cols-7">
        {rows.map((row, ri) =>
          row.map((day, ci) => {
            if (day === null) {
              return <div key={`empty-${ri}-${ci}`} className="h-20 border-b border-r border-zinc-100 dark:border-zinc-800/50" />;
            }

            const date = new Date(year, month, day);
            const key = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
            const dayAppts = appointmentMap.get(key) || [];
            const today = isToday(date);
            const selected = isSameDay(date, selectedDate);

            return (
              <button
                key={day}
                onClick={() => onSelectDate(date)}
                className={`h-20 border-b border-r border-zinc-100 dark:border-zinc-800/50 p-1 text-left hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors ${
                  selected ? "bg-blue-50 dark:bg-blue-900/20" : ""
                }`}
              >
                <div className="flex items-start justify-between">
                  <span
                    className={`inline-flex items-center justify-center w-7 h-7 text-sm ${
                      today
                        ? "bg-blue-600 text-white rounded-full font-semibold"
                        : selected
                          ? "text-blue-600 dark:text-blue-400 font-semibold"
                          : "text-zinc-700 dark:text-zinc-300"
                    }`}
                  >
                    {day}
                  </span>
                  {dayAppts.length > 0 && (
                    <span className="flex items-center gap-0.5">
                      {dayAppts.length <= 3 ? (
                        dayAppts.map((_, i) => (
                          <span
                            key={i}
                            className={`w-1.5 h-1.5 rounded-full ${getStatusColor(dayAppts)}`}
                          />
                        ))
                      ) : (
                        <span className="text-[10px] font-medium text-zinc-500 dark:text-zinc-400">
                          {dayAppts.length}
                        </span>
                      )}
                    </span>
                  )}
                </div>
                {/* Show first appointment title if space allows */}
                {dayAppts.length > 0 && (
                  <div className="mt-0.5">
                    <div className="text-[10px] leading-tight text-zinc-600 dark:text-zinc-400 truncate">
                      {dayAppts[0].title}
                    </div>
                    {dayAppts.length > 1 && (
                      <div className="text-[10px] leading-tight text-zinc-400 dark:text-zinc-500">
                        +{dayAppts.length - 1} more
                      </div>
                    )}
                  </div>
                )}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
