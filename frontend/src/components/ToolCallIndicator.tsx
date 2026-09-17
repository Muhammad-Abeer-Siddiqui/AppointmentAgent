"use client";

interface ToolCallIndicatorProps {
  toolCalls: Array<{
    name: string;
    arguments: Record<string, any>;
  }>;
}

const toolIcons: Record<string, string> = {
  search_availability: "??",
  create_appointment: "??",
  multi_person_availability: "??",
  update_appointment: "??",
  cancel_appointment: "?",
  get_user_profile: "??",
  set_user_preferences: "??",
  get_calendar: "??",
  sync_to_google_calendar: "??",
  sync_from_google_calendar: "??",
};

const toolLabels: Record<string, string> = {
  search_availability: "Searching available slots",
  create_appointment: "Creating appointment",
  multi_person_availability: "Finding common availability",
  update_appointment: "Updating appointment",
  cancel_appointment: "Cancelling appointment",
  get_user_profile: "Getting profile",
  set_user_preferences: "Updating preferences",
  get_calendar: "Loading calendar",
  sync_to_google_calendar: "Syncing to Google Calendar",
  sync_from_google_calendar: "Syncing from Google Calendar",
};

export default function ToolCallIndicator({ toolCalls }: ToolCallIndicatorProps) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="flex justify-start">
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-3 border border-zinc-200 dark:border-zinc-700 animate-slide-in">
        <div className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400 mb-2">
          <span className="text-lg">??</span>
          <span className="font-medium">Assistant is working...</span>
        </div>
        <div className="space-y-1.5 ml-6">
          {toolCalls.map((tc, index) => (
            <div key={index} className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
              <span className="text-base">{toolIcons[tc.name] || "??"}</span>
              <span className="font-mono text-zinc-700 dark:text-zinc-300">
                {toolLabels[tc.name] || tc.name}
              </span>
              <div className="flex items-center gap-1">
                <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse" />
                <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse delay-75" />
                <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse delay-150" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
