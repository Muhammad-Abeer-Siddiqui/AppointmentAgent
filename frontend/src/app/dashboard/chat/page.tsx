"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { agentApi, ApiError } from "@/lib/api";

type Message = {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
};

export default function ChatPage() {
  const { token, user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      // Parse the user's request and call appropriate agent endpoints
      const response = await processUserRequest(userMessage.content, token!);

      const assistantMessage: Message = {
        role: "assistant",
        content: response,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage: Message = {
        role: "assistant",
        content: "Sorry, I encountered an error processing your request. Please try again.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const processUserRequest = async (request: string, token: string): Promise<string> => {
    const lowerRequest = request.toLowerCase();

    // Simple intent detection
    if (lowerRequest.includes("schedule") || lowerRequest.includes("book") || lowerRequest.includes("find time")) {
      return await handleScheduleRequest(request, token);
    }

    if (lowerRequest.includes("cancel")) {
      return "To cancel an appointment, please go to the Calendar view and click on the appointment you'd like to cancel.";
    }

    if (lowerRequest.includes("reschedule")) {
      return "To reschedule, please cancel the existing appointment and book a new one with your preferred time.";
    }

    if (lowerRequest.includes("help")) {
      return `I can help you with:
• **Scheduling**: "Find me a 30-minute slot next week"
• **Booking**: "Book a meeting tomorrow at 2pm"
• **Viewing**: Check your calendar in the Dashboard

Just describe what you need in natural language!`;
    }

    return "I can help you schedule appointments. Try saying something like 'Find me a 30-minute slot next week' or 'Book a meeting tomorrow at 2pm'. Type 'help' for more options.";
  };

  const handleScheduleRequest = async (request: string, token: string): Promise<string> => {
    // Extract duration if mentioned
    const durationMatch = request.match(/(\d+)\s*(min|minute|hour|hr)/i);
    let duration = 60; // default
    if (durationMatch) {
      duration = parseInt(durationMatch[1]);
      if (durationMatch[2].toLowerCase().startsWith("hour") || durationMatch[2].toLowerCase().startsWith("hr")) {
        duration *= 60;
      }
    }

    // Set date range (next 7 days by default)
    const today = new Date();
    const nextWeek = new Date(today);
    nextWeek.setDate(nextWeek.getDate() + 7);

    const startDate = today.toISOString().split("T")[0];
    const endDate = nextWeek.toISOString().split("T")[0];

    try {
      const result = await agentApi.searchAvailability(token, {
        duration_minutes: duration,
        start_date: startDate,
        end_date: endDate,
        user_tz: user?.timezone || "UTC",
      });

      if (result.slots && result.slots.length > 0) {
        const slotsList = result.slots
          .slice(0, 5)
          .map((slot: any, i: number) => {
            const start = new Date(slot.start);
            return `${i + 1}. ${start.toLocaleDateString("en-US", {
              weekday: "short",
              month: "short",
              day: "numeric",
            })} at ${start.toLocaleTimeString("en-US", {
              hour: "numeric",
              minute: "2-digit",
            })}`;
          })
          .join("\n");

        return `I found ${result.slots.length} available slots for a ${duration}-minute meeting:\n\n${slotsList}\n\nWould you like me to book one of these? Just tell me which number.`;
      }

      return `I couldn't find any available ${duration}-minute slots in the next week. Try adjusting the duration or checking back later.`;
    } catch (err) {
      return "I had trouble searching for availability. Please try again.";
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-zinc-500 dark:text-zinc-400 py-8">
            <div className="text-4xl mb-4">🤖</div>
            <div className="text-lg font-medium mb-2">AI Scheduling Agent</div>
            <div className="text-sm">
              Ask me to schedule, book, or find available times for appointments.
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg p-3 ${
                message.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 border border-zinc-200 dark:border-zinc-700"
              }`}
            >
              <div className="whitespace-pre-wrap text-sm">{message.content}</div>
              <div
                className={`text-xs mt-1 ${
                  message.role === "user"
                    ? "text-blue-200"
                    : "text-zinc-400"
                }`}
              >
                {message.timestamp.toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-3 border border-zinc-200 dark:border-zinc-700">
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <div className="w-2 h-2 bg-zinc-400 rounded-full animate-pulse" />
                <div className="w-2 h-2 bg-zinc-400 rounded-full animate-pulse delay-75" />
                <div className="w-2 h-2 bg-zinc-400 rounded-full animate-pulse delay-150" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-zinc-200 dark:border-zinc-800 p-4">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask me to schedule an appointment..."
            disabled={isLoading}
            className="flex-1 px-4 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg transition-colors"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
