"use client";

interface AppointmentSuggestionCardProps {
  slot: {
    id: number;
    start: string;
    end: string;
    score: number;
    date: string;
  };
  onSelect: (slot: any) => void;
}

export default function AppointmentSuggestionCard({ slot, onSelect }: AppointmentSuggestionCardProps) {
  const startDate = new Date(slot.start);
  const endDate = new Date(slot.end);
  
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  };
  
  const formatDate = (date: Date) => {
    return date.toLocaleDateString("en-US", {
      weekday: "long",
      month: "short",
      day: "numeric",
    });
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300";
    if (score >= 60) return "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300";
    return "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400";
  };

  return (
    <div 
      className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 p-4 hover:border-blue-300 dark:hover:border-blue-700 cursor-pointer transition-colors"
      onClick={() => onSelect(slot)}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
            {formatDate(startDate)}
          </div>
          <div className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mt-1">
            {formatTime(startDate)} - {formatTime(endDate)}
          </div>
          <div className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            {Math.round((new Date(slot.end).getTime() - new Date(slot.start).getTime()) / 60000)} minutes
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-1 text-xs rounded-full ${getScoreColor(slot.score)}`}>
            Match: {slot.score}%
          </span>
          <button
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              onSelect(slot);
            }}
          >
            Book
          </button>
        </div>
      </div>
    </div>
  );
}
