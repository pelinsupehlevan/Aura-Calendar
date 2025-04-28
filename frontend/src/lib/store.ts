import { create } from "zustand";
import { persist } from "zustand/middleware";
import { v4 as uuidv4 } from "uuid";
import { CalendarEvent, ChatMessage } from "./types";

interface AppState {
  events: CalendarEvent[];
  messages: ChatMessage[];
  addEvent: (event: Omit<CalendarEvent, "id">) => void;
  updateEvent: (event: CalendarEvent) => void;
  deleteEvent: (id: string) => void;
  addMessage: (message: Omit<ChatMessage, "id" | "timestamp">) => void;
  clearMessages: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      events: [
        {
          id: "1",
          title: "Team Meeting",
          description: "Weekly team sync",
          date: new Date(new Date().setHours(10, 0, 0, 0)),
          endDate: new Date(new Date().setHours(11, 0, 0, 0)),
        },
        {
          id: "2",
          title: "Doctor Appointment",
          description: "Annual checkup",
          date: new Date(new Date().setDate(new Date().getDate() + 2)),
          allDay: true,
        },
        {
          id: "3",
          title: "Project Deadline",
          description: "Submit final deliverables",
          date: new Date(new Date().setDate(new Date().getDate() + 5)),
          color: "#7E69AB",
        },
      ],
      messages: [
        {
          id: "welcome-1",
          role: "assistant",
          content: "Hello! I'm your Personal Assistant. How can I help you today?",
          timestamp: new Date(),
        },
      ],
      addEvent: (event) =>
        set((state) => ({
          events: [...state.events, { ...event, id: uuidv4() }],
        })),
      updateEvent: (updatedEvent) =>
        set((state) => ({
          events: state.events.map((event) =>
            event.id === updatedEvent.id ? updatedEvent : event
          ),
        })),
      deleteEvent: (id) =>
        set((state) => ({
          events: state.events.filter((event) => event.id !== id),
        })),
      addMessage: (message) =>
        set((state) => ({
          messages: [
            ...state.messages,
            { ...message, id: uuidv4(), timestamp: new Date() },
          ],
        })),
      clearMessages: () =>
        set({
          messages: [
            {
              id: "welcome-1",
              role: "assistant",
              content: "Hello! I'm your Personal Assistant. How can I help you today?",
              timestamp: new Date(),
            },
          ],
        }),
    }),
    {
      name: "aura-calendar-storage",
    }
  )
);
