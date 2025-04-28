export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  user_message?: string;  
  intent_info?: { 
    intent: string;      
    summary: string;
    importance: number;
  };
}


export interface CalendarEvent {
  id: string;
  title: string;
  description?: string;
  date: Date;
  endDate?: Date;
  allDay?: boolean;
  color?: string;
}

