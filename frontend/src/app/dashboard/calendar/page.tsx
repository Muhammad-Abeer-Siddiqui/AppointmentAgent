"use client";

import { useEffect, useState, useMemo } from "react";
import { useAuth } from "@/lib/auth-context";
import { calendarApi, ApiError } from "@/lib/api";
import type { Appointment } from "@/types";
import MonthCalendar from "@/components/MonthCalendar";
import WeekView from "@/components/WeekView";

type ViewMode = "month" | "week";

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function getMonday(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  d.setDate(diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

export default function CalendarPage() {
  const { token } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [viewMode, setViewMode] = useState<ViewMode>("month");
  const [currentMonth, setCurrentMonth] = useState({
    year: new Date().getFullYear(),
    month: new Date().getMonth(),
  });
  const [currentWeekStart, setCurrentWeekStart] = useState(() =>
    getMonday(new Date())
  );

  useEffect(() => {
    if (token) {
      fetchAppointments();
    }
  }, [token]);

  const fetchAppointments = async () => {
    try {
      const data = await calendarApi.getAppointments(token!);
      setAppointments(data.appointments || []);
    } catch (err) {
      console.error("Failed to fetch appointments:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = async (appointmentId: number) => {
    if (!confirm("Are you sure you want to cancel this appointment?")) {
      return;
    }
    try {
      await calendarApi.deleteAppointment(token!, appointmentId);
      await fetchAppointments();
    } catch (err) {
      console.error("Failed to cancel appointment:", err);
    }
  };

  // Filter appointments for selected date
  const dayAppointments = useMemo(() => {
    return appointments
      .filter((appt) => {
        const apptDate = new Date(appt.start_time);
        return isSameDay(apptDate, selectedDate);
      })
      .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
  }, [appointments, selectedDate]);

  // Month navigation
  const handlePrevMonth = () => {
    setCurrentMonth((prev) => {
      const m = prev.month - 1;
      if (m < 0) return { year: prev.year - 1, month: 11 };
      return { year: prev.year, month: m };
    });
  };

  const handleNextMonth = () => {
    setCurrentMonth((prev) => {
      const m = prev.month + 1;
      if (m > 11) return { year: prev.year + 1, month: 0 };
      return { year: prev.year, month: m };
    });
  };

  const handleToday = () => {
    const now = new Date();
    setSelectedDate(now);
    setCurrentMonth({ year: now.getFullYear(), month: now.getMonth() });
    setCurrentWeekStart(getMonday(now));
  };

  // Week navigation
  const handlePrevWeek = () => {
    setCurrentWeekStart((prev) => {
      const d = new Date(prev);
      d.setDate(d.getDate() - 7);
      return d;
    });
  };

  const handleNextWeek = () => {
    setCurrentWeekStart((prev) => {
      const d = new Date(prev);
      d.setDate(d.getDate() + 7);
      return d;
    });
  };

  const selectedDateLabel = selectedDate.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="space-y-6">
      {/* Top bar */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Calendar
        </h2>
        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="flex items-center bg-zinc-100 dark:bg-zinc-800 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode("month")}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                viewMode === "month"
                  ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 shadow-sm"
                  : "text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
              }`}
            >
              Month
            </button>
            <button
              onClick={() => setViewMode("week")}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                viewMode === "week"
                  ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 shadow-sm"
                  : "text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
              }`}
            >
              Week
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Calendar view */}
        <div className={viewMode === "month" ? "lg:col-span-2" : "lg:col-span-2"}>
          {isLoading ? (
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-8 text-center text-zinc-500">
              Loading calendar...
            </div>
          ) : viewMode === "month" ? (
            <MonthCalendar
              year={currentMonth.year}
              month={currentMonth.month}
              selectedDate={selectedDate}
              appointments={appointments}
              onSelectDate={setSelectedDate}
              onPrevMonth={handlePrevMonth}
              onNextMonth={handleNextMonth}
              onToday={handleToday}
            />
          ) : (
            <WeekView
              weekStart={currentWeekStart}
              appointments={appointments}
              onSelectDate={setSelectedDate}
              onPrevWeek={handlePrevWeek}
              onNextWeek={handleNextWeek}
              onToday={handleToday}
            />
          )}
        </div>

        {/* Day detail panel */}
        <div className="lg:col-span-1">
          <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 sticky top-8">
            {/* Day header */}
            <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800">
              <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                {selectedDateLabel}
              </h4>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                {dayAppointments.length === 0
                  ? "No appointments"
                  : `${dayAppointments.length} appointment${dayAppointments.length > 1 ? "s" : ""}`}
              </p>
            </div>

            {/* Appointments list */}
            {dayAppointments.length === 0 ? (
              <div className="p-8 text-center text-zinc-400 dark:text-zinc-500">
                <svg className="w-12 h-12 mx-auto mb-3 text-zinc-300 dark:text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p className="text-sm">No appointments on this day</p>
                <p className="text-xs mt-1 text-zinc-400 dark:text-zinc-500">
                  Click a day with a dot to see details
                </p>
              </div>
            ) : (
              <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {dayAppointments.map((appt) => {
                  const start = new Date(appt.start_time);
                  const end = new Date(appt.end_time);
                  const isScheduled = appt.status === "scheduled";
                  return (
                    <div
                      key={appt.id}
                      className="p-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        {/* Time indicator */}
                        <div className="flex flex-col items-center min-w-[48px]">
                          <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                            {start.toLocaleTimeString("en-US", {
                              hour: "numeric",
                              minute: "2-digit",
                              hour12: true,
                            })}
                          </span>
                          <span className="text-[10px] text-zinc-400 dark:text-zinc-500">
                            {appt.duration_minutes}min
                          </span>
                          <span className="text-[10px] text-zinc-400 dark:text-zinc-500">
                            {end.toLocaleTimeString("en-US", {
                              hour: "numeric",
                              minute: "2-digit",
                              hour12: true,
                            })}
                          </span>
                        </div>

                        {/* Details */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">
                              {appt.title}
                            </span>
                            <span
                              className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${
                                isScheduled
                                  ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
                                  : "bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400"
                              }`}
                            >
                              {appt.status}
                            </span>
                          </div>
                          {appt.description && (
                            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 line-clamp-2">
                              {appt.description}
                            </p>
                          )}
                          {isScheduled && (
                            <button
                              onClick={() => handleCancel(appt.id)}
                              className="mt-1.5 text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 transition-colors"
                            >
                              Cancel appointment
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
