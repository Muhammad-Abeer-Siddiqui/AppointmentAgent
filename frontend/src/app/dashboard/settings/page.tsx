"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { apiFetch, ApiError, authApi } from "@/lib/api";

type GoogleStatus = {
  connected: boolean;
  calendar_id?: string;
  last_sync?: string;
};

type Preferences = {
  preferred_earliest_time: string;
  preferred_latest_time: string;
  avoid_lunch: boolean;
  min_break_minutes: number;
  preferred_duration_minutes: number;
};

type WorkingHours = {
  [day: string]: {
    start: string;
    end: string;
    is_off_day: boolean;
  };
};

type TimezoneOption = {
  value: string;
  label: string;
};

// Common timezones for the selector
const COMMON_TIMEZONES: TimezoneOption[] = [
  { value: "UTC", label: "UTC (Coordinated Universal Time)" },
  { value: "America/New_York", label: "Eastern Time (ET)" },
  { value: "America/Chicago", label: "Central Time (CT)" },
  { value: "America/Denver", label: "Mountain Time (MT)" },
  { value: "America/Los_Angeles", label: "Pacific Time (PT)" },
  { value: "America/Anchorage", label: "Alaska Time (AKT)" },
  { value: "Pacific/Honolulu", label: "Hawaii Time (HST)" },
  { value: "America/Toronto", label: "Toronto (ET)" },
  { value: "America/Vancouver", label: "Vancouver (PT)" },
  { value: "Europe/London", label: "London (GMT/BST)" },
  { value: "Europe/Paris", label: "Paris (CET/CEST)" },
  { value: "Europe/Berlin", label: "Berlin (CET/CEST)" },
  { value: "Asia/Tokyo", label: "Tokyo (JST)" },
  { value: "Asia/Shanghai", label: "Shanghai (CST)" },
  { value: "Asia/Kolkata", label: "Kolkata (IST)" },
  { value: "Australia/Sydney", label: "Sydney (AEST/AEDT)" },
  { value: "Pacific/Auckland", label: "Auckland (NZST/NZDT)" },
];

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function SettingsPage() {
  const { token, user } = useAuth();
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus | null>(null);
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [workingHours, setWorkingHours] = useState<WorkingHours | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [isSavingPrefs, setIsSavingPrefs] = useState(false);
  const [isSavingHours, setIsSavingHours] = useState(false);
  const [prefsMessage, setPrefsMessage] = useState<string | null>(null);
  const [hoursMessage, setHoursMessage] = useState<string | null>(null);
  const [timezoneSearch, setTimezoneSearch] = useState("");
  const [showTimezoneDropdown, setShowTimezoneDropdown] = useState(false);

  useEffect(() => {
    if (token) {
      fetchGoogleStatus();
      fetchPreferences();
      fetchWorkingHours();
    }
  }, [token]);

  const fetchGoogleStatus = async () => {
    try {
      const data = await apiFetch("/auth/google/status", { token: token! });
      setGoogleStatus(data);
    } catch (err) {
      console.error("Failed to fetch Google status:", err);
    }
  };

  const fetchPreferences = async () => {
    try {
      const data = await apiFetch("/preferences", { token: token! });
      setPreferences({
        preferred_earliest_time: data.preferred_earliest_time || "09:00",
        preferred_latest_time: data.preferred_latest_time || "17:00",
        avoid_lunch: data.avoid_lunch ?? true,
        min_break_minutes: data.min_break_minutes ?? 30,
        preferred_duration_minutes: data.preferred_duration_minutes ?? 60,
      });
    } catch (err) {
      console.error("Failed to fetch preferences:", err);
    }
  };

  const fetchWorkingHours = async () => {
    try {
      const data = await apiFetch("/users/working-hours", { token: token! });
      const hours: WorkingHours = {};
      DAYS.forEach((day, index) => {
        hours[day] = data[day] || { start: "09:00", end: "17:00", is_off_day: index >= 5 };
      });
      setWorkingHours(hours);
    } catch (err) {
      console.error("Failed to fetch working hours:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConnectGoogle = async () => {
    try {
      const data = await authApi.googleLogin(token!);
      if (data.auth_url) {
        window.location.href = data.auth_url;
      }
    } catch (err) {
      console.error("Failed to initiate Google login:", err);
    }
  };

  const handleDisconnectGoogle = async () => {
    if (!confirm("Are you sure you want to disconnect Google Calendar?")) {
      return;
    }

    try {
      await apiFetch("/auth/google/disconnect", {
        method: "DELETE",
        token: token!,
      });
      setGoogleStatus({ connected: false });
    } catch (err) {
      console.error("Failed to disconnect Google Calendar:", err);
    }
  };

  const handleSync = async (direction: "to" | "from" | "both") => {
    setIsSyncing(true);
    setSyncMessage(null);

    try {
      let result;
      if (direction === "to") {
        result = await apiFetch("/integrations/sync", {
          method: "POST",
          body: { direction: "app_to_google" },
          token: token!,
        });
      } else if (direction === "from") {
        result = await apiFetch("/integrations/sync", {
          method: "POST",
          body: { direction: "google_to_app" },
          token: token!,
        });
      } else {
        result = await apiFetch("/integrations/sync", {
          method: "POST",
          body: { direction: "two_way" },
          token: token!,
        });
      }

      setSyncMessage(result.message || "Sync completed successfully");
      fetchGoogleStatus();
    } catch (err) {
      setSyncMessage("Sync failed. Please try again.");
      console.error("Failed to sync:", err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleSavePreferences = async () => {
    if (!preferences) return;
    setIsSavingPrefs(true);
    setPrefsMessage(null);

    try {
      await apiFetch("/users/preferences", {
        method: "PATCH",
        body: preferences,
        token: token!,
      });
      setPrefsMessage("Preferences saved successfully!");
      setTimeout(() => setPrefsMessage(null), 3000);
    } catch (err) {
      setPrefsMessage("Failed to save preferences. Please try again.");
      console.error("Failed to save preferences:", err);
    } finally {
      setIsSavingPrefs(false);
    }
  };

  const handleSaveWorkingHours = async () => {
    if (!workingHours) return;
    setIsSavingHours(true);
    setHoursMessage(null);

    try {
      const hoursArray = DAYS.map((day) => ({
        day_of_week: DAYS.indexOf(day),
        start_time: workingHours[day]?.start || "09:00",
        end_time: workingHours[day]?.end || "17:00",
        is_off_day: workingHours[day]?.is_off_day || false,
      }));

      await apiFetch("/users/working-hours", {
        method: "PATCH",
        body: { working_hours: hoursArray },
        token: token!,
      });
      setHoursMessage("Working hours saved successfully!");
      setTimeout(() => setHoursMessage(null), 3000);
    } catch (err) {
      setHoursMessage("Failed to save working hours. Please try again.");
      console.error("Failed to save working hours:", err);
    } finally {
      setIsSavingHours(false);
    }
  };

  const handleTimezoneSelect = (tz: TimezoneOption) => {
    setPreferences((prev) => prev ? { ...prev, timezone: tz.value } : null);
    setShowTimezoneDropdown(false);
    setTimezoneSearch("");
  };

  const filteredTimezones = COMMON_TIMEZONES.filter((tz) =>
    tz.label.toLowerCase().includes(timezoneSearch.toLowerCase()) ||
    tz.value.toLowerCase().includes(timezoneSearch.toLowerCase())
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-zinc-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Settings
        </h2>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Manage your account, preferences, and integrations
        </p>
      </div>

      {/* Profile Section */}
      <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
        <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            Profile
          </h3>
        </div>
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Name
              </label>
              <div className="mt-1 text-zinc-900 dark:text-zinc-100">
                {user?.name}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Email
              </label>
              <div className="mt-1 text-zinc-900 dark:text-zinc-100">
                {user?.email}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Timezone
              </label>
              <div className="relative mt-1">
                <select
                  value={user?.timezone || "UTC"}
                  onChange={(e) => handleTimezoneSelect({ value: e.target.value, label: e.target.value })}
                  className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {COMMON_TIMEZONES.map((tz) => (
                    <option key={tz.value} value={tz.value} selected={tz.value === (user?.timezone || "UTC")}>
                      {tz.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Scheduling Preferences */}
      <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
        <div className="p-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            Scheduling Preferences
          </h3>
          {prefsMessage && (
            <span className="text-sm text-green-600 dark:text-green-400">{prefsMessage}</span>
          )}
        </div>
        <div className="p-4 space-y-6">
          {preferences && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Preferred Earliest Time
                  </label>
                  <input
                    type="time"
                    value={preferences.preferred_earliest_time}
                    onChange={(e) => setPreferences({ ...preferences!, preferred_earliest_time: e.target.value })}
                    className="mt-1 w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Preferred Latest Time
                  </label>
                  <input
                    type="time"
                    value={preferences.preferred_latest_time}
                    onChange={(e) => setPreferences({ ...preferences!, preferred_latest_time: e.target.value })}
                    className="mt-1 w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Minimum Break Between Appointments (minutes)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="120"
                    step="5"
                    value={preferences.min_break_minutes}
                    onChange={(e) => setPreferences({ ...preferences!, min_break_minutes: parseInt(e.target.value) || 0 })}
                    className="mt-1 w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Preferred Appointment Duration (minutes)
                  </label>
                  <select
                    value={preferences.preferred_duration_minutes}
                    onChange={(e) => setPreferences({ ...preferences!, preferred_duration_minutes: parseInt(e.target.value) })}
                    className="mt-1 w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value={15}>15 minutes</option>
                    <option value={30}>30 minutes</option>
                    <option value={45}>45 minutes</option>
                    <option value={60}>60 minutes</option>
                    <option value={90}>90 minutes</option>
                    <option value={120}>120 minutes</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="avoid_lunch"
                  checked={preferences.avoid_lunch}
                  onChange={(e) => setPreferences({ ...preferences!, avoid_lunch: e.target.checked })}
                  className="h-4 w-4 text-blue-600 border-zinc-300 rounded focus:ring-blue-500"
                />
                <label htmlFor="avoid_lunch" className="text-sm text-zinc-700 dark:text-zinc-300">
                  Avoid scheduling during lunch hours (12:00 - 13:00)
                </label>
              </div>

              <div className="flex justify-end pt-4 border-t border-zinc-200 dark:border-zinc-800">
                <button
                  onClick={handleSavePreferences}
                  disabled={isSavingPrefs}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg transition-colors"
                >
                  {isSavingPrefs ? "Saving..." : "Save Preferences"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Working Hours */}
      <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
        <div className="p-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            Working Hours
          </h3>
          {hoursMessage && (
            <span className="text-sm text-green-600 dark:text-green-400">{hoursMessage}</span>
          )}
        </div>
        <div className="p-4 space-y-3">
          {workingHours && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-sm text-zinc-500 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800">
                      <th className="pb-2 font-medium">Day</th>
                      <th className="pb-2 font-medium">Start</th>
                      <th className="pb-2 font-medium">End</th>
                      <th className="pb-2 font-medium">Off Day</th>
                    </tr>
                  </thead>
                  <tbody>
                    {DAYS.map((day, index) => (
                      <tr key={day} className="border-b border-zinc-100 dark:border-zinc-800 last:border-0">
                        <td className="py-2 font-medium text-zinc-900 dark:text-zinc-100">{day}</td>
                        <td className="py-2">
                          <input
                            type="time"
                            value={workingHours[day]?.start || "09:00"}
                            onChange={(e) => setWorkingHours({ ...workingHours!, [day]: { ...workingHours![day]!, start: e.target.value } })}
                            disabled={workingHours[day]?.is_off_day}
                            className="w-24 px-2 py-1 border border-zinc-300 dark:border-zinc-700 rounded bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 disabled:opacity-50"
                          />
                        </td>
                        <td className="py-2">
                          <input
                            type="time"
                            value={workingHours[day]?.end || "17:00"}
                            onChange={(e) => setWorkingHours({ ...workingHours!, [day]: { ...workingHours![day]!, end: e.target.value } })}
                            disabled={workingHours[day]?.is_off_day}
                            className="w-24 px-2 py-1 border border-zinc-300 dark:border-zinc-700 rounded bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 disabled:opacity-50"
                          />
                        </td>
                        <td className="py-2">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={workingHours[day]?.is_off_day || false}
                              onChange={(e) => setWorkingHours({ ...workingHours!, [day]: { ...workingHours![day]!, is_off_day: e.target.checked } })}
                              className="h-4 w-4 text-blue-600 border-zinc-300 rounded focus:ring-blue-500"
                            />
                            <span className="text-sm text-zinc-700 dark:text-zinc-300">Off</span>
                          </label>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex justify-end pt-4 border-t border-zinc-200 dark:border-zinc-800">
                <button
                  onClick={handleSaveWorkingHours}
                  disabled={isSavingHours}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg transition-colors"
                >
                  {isSavingHours ? "Saving..." : "Save Working Hours"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Google Calendar Integration */}
      <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
        <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            Google Calendar Integration
          </h3>
        </div>
        <div className="p-4">
          {googleStatus?.connected ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <span className="text-xl">?</span>
                <span className="font-medium">Connected</span>
              </div>

              <div className="text-sm text-zinc-500 dark:text-zinc-400">
                <div>
                  Calendar ID: {googleStatus.calendar_id || "primary"}
                </div>
                {googleStatus.last_sync && (
                  <div>
                    Last sync:{" "}
                    {new Date(googleStatus.last_sync).toLocaleString()}
                  </div>
                )}
              </div>

              {/* Sync Buttons */}
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => handleSync("to")}
                  disabled={isSyncing}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSyncing ? "Syncing..." : "Sync App ? Google"}
                </button>

                <button
                  onClick={() => handleSync("from")}
                  disabled={isSyncing}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSyncing ? "Syncing..." : "Sync Google ? App"}
                </button>

                <button
                  onClick={() => handleSync("both")}
                  disabled={isSyncing}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSyncing ? "Syncing..." : "Two-Way Sync"}
                </button>
              </div>

              {syncMessage && (
                <div className="p-3 bg-zinc-100 dark:bg-zinc-800 rounded-lg text-sm">
                  {syncMessage}
                </div>
              )}

              <button
                onClick={handleDisconnectGoogle}
                className="px-4 py-2 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20"
              >
                Disconnect Google Calendar
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-zinc-600 dark:text-zinc-400">
                Connect your Google Calendar to sync appointments
                automatically.
              </p>

              <button
                onClick={handleConnectGoogle}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
              >
                <span>??</span>
                Connect Google Calendar
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
