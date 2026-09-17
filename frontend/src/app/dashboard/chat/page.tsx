"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { agentApi, ApiError } from "@/lib/api";
import ToolCallIndicator from "@/components/ToolCallIndicator";
import AppointmentSuggestionCard from "@/components/AppointmentSuggestionCard";
import ConfirmationModal from "@/components/ConfirmationModal";
import type { Message, PendingConfirmation, PendingConfirmationState, AvailableSlot } from "@/types";

export default function ChatPage() {
  const { token, user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [pendingConfirmation, setPendingConfirmation] = useState<PendingConfirmationState>(null);
  const [selectedSlot, setSelectedSlot] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSlotSelect = async (slot: any) => {
    setSelectedSlot(slot);
    setPendingConfirmation({
      action: `Book appointment for ${new Date(slot.start).toLocaleString()}`,
      details: `Would you like to book a ${Math.round((new Date(slot.end).getTime() - new Date(slot.start).getTime()) / 60000)}-minute appointment on ${new Date(slot.start).toLocaleString()}?`,
    });
  };

  const handleConfirm = async () => {
    if (!pendingConfirmation || !selectedSlot) return;

    setIsLoading(true);
    try {
      const response = await agentApi.createAppointment(token!, {
        title: "New Appointment",
        description: "",
        start_time: selectedSlot.start,
        end_time: selectedSlot.end,
        duration_minutes: Math.round((new Date(selectedSlot.end).getTime() - new Date(selectedSlot.start).getTime()) / 60000),
      });

      const assistantMessage: Message = {
        role: "assistant",
        content: `Appointment booked for ${new Date(selectedSlot.start).toLocaleString()}!`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      console.error("Booking error:", err);
      const errorMessage: Message = {
        role: "assistant",
        content: "Sorry, I couldn't book that appointment. Please try again.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setPendingConfirmation(null);
      setSelectedSlot(null);
    }
  };

  const handleCancelConfirmation = () => {
    setPendingConfirmation(null);
    setSelectedSlot(null);
  };

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
      // Call the AI agent endpoint
      const response = await agentApi.chat(token!, {
        message: userMessage.content,
        conversation_history: messages.slice(-5).map((msg) => ({
          role: msg.role,
          content: msg.content,
        })),
      });

      // Extract suggestions from tool calls
      let suggestions: any[] = [];
      if (response.tool_calls) {
        for (const tc of response.tool_calls) {
          if (tc.name === "search_availability" || tc.name === "multi_person_availability") {
            if (tc.result?.slots) {
              suggestions = tc.result.slots;
            }
          }
        }
      }

      const assistantMessage: Message = {
        role: "assistant",
        content: response.response || "I couldn't process your request. Please try again.",
        timestamp: new Date(),
        toolCalls: response.tool_calls || undefined,
        suggestions: suggestions.length > 0 ? suggestions : undefined,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      console.error("Chat error:", err);
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

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-zinc-500 dark:text-zinc-400 py-8">
            <div className="text-4xl mb-4">??</div>
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

        {/* Tool call indicator */}
        {isLoading && (
          <ToolCallIndicator toolCalls={[]} />
        )}

        {/* Suggestions carousel */}
        {messages[messages.length - 1]?.suggestions && messages[messages.length - 1].suggestions!.length > 0 && (
          <div className="flex justify-start">
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-3 border border-zinc-200 dark:border-zinc-700 max-w-[80%]">
              <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
                Available slots:
              </div>
              <div className="space-y-2">
                {messages[messages.length - 1].suggestions!.slice(0, 3).map((slot: any) => (
                  <AppointmentSuggestionCard key={slot.id} slot={slot} onSelect={handleSlotSelect} />
                ))}
              </div>
              {messages[messages.length - 1].suggestions!.length > 3 && (
                <div className="text-center mt-2">
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    ...and {messages[messages.length - 1].suggestions!.length - 3} more slots
                  </span>
                </div>
              )}
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

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={!!pendingConfirmation}
        onClose={handleCancelConfirmation}
        onConfirm={handleConfirm}
        title="Confirm Action"
        message={pendingConfirmation?.details || "Are you sure?"}
        confirmText="Yes, book it"
        cancelText="Cancel"
        variant="warning"
      />
    </div>
  );
}
