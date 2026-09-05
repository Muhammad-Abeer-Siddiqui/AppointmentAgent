"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { calendarApi, agentApi, ApiError } from "@/lib/api";

type Appointment = {
  id: number;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  status: string;
};

export default function CalendarPage() {
  const { token } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(new Date());

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
      await fetch(`http://localhost:8000/appointments/${appointmentId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      await fetchAppointments();
    } catch (err) {
      console.error("Failed to cancel appointment:", err);
    }
  };

  // Filter appointments for selected date
  const dayAppointments = appointments.filter((appt) => {
    const apptDate = new Date(appt.start_time);
    return (
      apptDate.getFullYear() === selectedDate.getFullYear() &&
      apptDate.getMonth() === selectedDate.getMonth() &&
      apptDate.getDate() === selectedDate.getDate()
    );
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Calendar
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const prev = new Date(selectedDate);
              prev.setDate(prev.getDate() - 1);
              setSelectedDate(prev);
            }}
            className="px-3 py-1 text-sm border border-zinc-300 dark:border-zinc-700 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            ← Prev
          </button>
          <span className="px-4 py-1 text-sm font-medium text-zinc-900 dark:text-zinc-100">
            {selectedDate.toLocaleDateString("en-US", {
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </span>
          <button
            onClick={() => {
              const next = new Date(selectedDate);
              next.setDate(next.getDate() + 1);
              setSelectedDate(next);
            }}
            className="px-3 py-1 text-sm border border-zinc-300 dark:border-zinc-700 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            Next →
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
        {isLoading ? (
          <div className="p-8 text-center text-zinc-500">Loading...</div>
        ) : dayAppointments.length === 0 ? (
          <div className="p-8 text-center text-zinc-500">
            No appointments on this day
          </div>
        ) : (
          <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {dayAppointments.map((appt) => (
              <div key={appt.id} className="p-4 hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-zinc-900 dark:text-zinc-100">
                      {appt.title}
                    </div>
                    <div className="text-sm text-zinc-500 dark:text-zinc-400">
                      {new Date(appt.start_time).toLocaleTimeString()} -{" "}
                      {new Date(appt.end_time).toLocaleTimeString()}
                      <span className="ml-2 px-2 py-0.5 text-xs bg-zinc-100 dark:bg-zinc-800 rounded">
                        {appt.duration_minutes}min
                      </span>
                    </div>
                    {appt.description && (
                      <div className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                        {appt.description}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-1 text-xs rounded ${
                        appt.status === "scheduled"
                          ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
                          : "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400"
                      }`}
                    >
                      {appt.status}
                    </span>
                    {appt.status === "scheduled" && (
                      <button
                        onClick={() => handleCancel(appt.id)}
                        className="px-2 py-1 text-xs text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
