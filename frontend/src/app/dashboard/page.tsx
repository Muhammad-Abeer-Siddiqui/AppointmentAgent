"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { calendarApi, ApiError } from "@/lib/api";
import type { Appointment } from "@/types";

export default function DashboardPage() {
  const { token, user } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [isLoading, setIsLoading] = useState(true);

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

  // Get upcoming appointments (status=scheduled and in the future)
  const upcoming = appointments
    .filter(
      (a) =>
        a.status === "scheduled" && new Date(a.start_time) > new Date(),
    )
    .sort(
      (a, b) =>
        new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
    )
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Welcome back, {user?.name}
        </h2>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Here&apos;s your scheduling overview
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-zinc-900 rounded-lg p-6 border border-zinc-200 dark:border-zinc-800">
          <div className="text-sm text-zinc-500 dark:text-zinc-400">Total Appointments</div>
          <div className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">
            {appointments.length}
          </div>
        </div>
        <div className="bg-white dark:bg-zinc-900 rounded-lg p-6 border border-zinc-200 dark:border-zinc-800">
          <div className="text-sm text-zinc-500 dark:text-zinc-400">Upcoming</div>
          <div className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">
            {upcoming.length}
          </div>
        </div>
        <div className="bg-white dark:bg-zinc-900 rounded-lg p-6 border border-zinc-200 dark:border-zinc-800">
          <div className="text-sm text-zinc-500 dark:text-zinc-400">Timezone</div>
          <div className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mt-2">
            {user?.timezone || "UTC"}
          </div>
        </div>
      </div>

      {/* Upcoming Appointments */}
      <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
        <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            Upcoming Appointments
          </h3>
        </div>
        <div className="p-4">
          {isLoading ? (
            <div className="text-center py-8 text-zinc-500">Loading...</div>
          ) : upcoming.length === 0 ? (
            <div className="text-center py-8 text-zinc-500">
              No upcoming appointments
            </div>
          ) : (
            <div className="space-y-3">
              {upcoming.map((appt) => (
                <div
                  key={appt.id}
                  className="flex items-center justify-between p-3 bg-zinc-50 dark:bg-zinc-800 rounded-lg"
                >
                  <div>
                    <div className="font-medium text-zinc-900 dark:text-zinc-100">
                      {appt.title}
                    </div>
                    <div className="text-sm text-zinc-500 dark:text-zinc-400">
                      {new Date(appt.start_time).toLocaleString()} -{" "}
                      {new Date(appt.end_time).toLocaleTimeString()}
                    </div>
                  </div>
                  <span className="px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded">
                    {appt.duration_minutes}min
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link
          href="/dashboard/chat"
          className="block bg-white dark:bg-zinc-900 rounded-lg p-6 border border-zinc-200 dark:border-zinc-800 hover:border-blue-500 dark:hover:border-blue-500 transition-colors"
        >
          <div className="text-2xl mb-2">💬</div>
          <div className="font-semibold text-zinc-900 dark:text-zinc-100">
            Chat with AI Agent
          </div>
          <div className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Ask the AI to schedule, reschedule, or cancel appointments
          </div>
        </Link>
        <Link
          href="/dashboard/calendar"
          className="block bg-white dark:bg-zinc-900 rounded-lg p-6 border border-zinc-200 dark:border-zinc-800 hover:border-blue-500 dark:hover:border-blue-500 transition-colors"
        >
          <div className="text-2xl mb-2">📅</div>
          <div className="font-semibold text-zinc-900 dark:text-zinc-100">
            View Calendar
          </div>
          <div className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            See all your appointments in a calendar view
          </div>
        </Link>
      </div>
    </div>
  );
}
