import { toast } from 'sonner';
import { API_CONFIG } from '@/config';

// Use the API base URL from config
const API_BASE_URL = API_CONFIG.BASE_URL;

export interface Event {
  event_id: number;
  title: string;
  description?: string;
  start_time: string;
  end_time: string;
  location?: string;
  importance: number;
  status: string;
}

export interface ChatMessage {
  id: string;
  text: string;
  role: 'user' | 'assistant';
  timestamp: Date;
}

export interface MessageResponse {
  text: string;
  ui_action?: {
    type: string;
    event?: Event;
    event_id?: number;
  };
}

class ApiService {
  // Helper method to handle API errors
  private handleApiError(error: any, fallbackMessage: string): never {
    console.error(fallbackMessage, error);
    
    // Extract message from error if possible
    let errorMessage = fallbackMessage;
    if (error instanceof Error) {
      errorMessage = error.message;
    } else if (typeof error === 'string') {
      errorMessage = error;
    }
    
    // Show error toast
    toast.error(errorMessage);
    
    // Re-throw the error
    throw error;
  }

  // Chat API
  async sendMessage(message: string): Promise<MessageResponse> {
    try {
      console.log(`Sending message to ${API_BASE_URL}/message`);
      
      const response = await fetch(`${API_BASE_URL}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message, 
          user_id: 'user123',  // You might want to implement user authentication later
          conversation_id: 'default' 
        }),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error (${response.status}): ${errorText}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error sending message:', error);
      toast.error('Failed to send message. Is the backend server running?');
      
      // Return a fallback response to prevent the UI from breaking
      return {
        text: "I'm having trouble connecting to the server. Please check that the backend is running and that CORS is properly configured."
      };
    }
  }
  

async getEvents(startDate?: Date, endDate?: Date): Promise<Event[]> {
  try {
    // Create query parameters if dates are provided
    const queryParams = new URLSearchParams();
    if (startDate) queryParams.append('start', startDate.toISOString());
    if (endDate) queryParams.append('end', endDate.toISOString());
    
    // Make the API call
    const response = await fetch(`${API_BASE_URL}/events?${queryParams}`);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error fetching events:', error);
    toast.error('Failed to fetch events. Is the backend server running?');
    
    // Return empty array to prevent UI errors
    return [];
  }
}

  async createEvent(eventData: Omit<Event, 'event_id' | 'status'>): Promise<Event> {
    try {
      const response = await fetch(`${API_BASE_URL}/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(eventData),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error (${response.status}): ${errorText}`);
      }
      
      const data = await response.json();
      toast.success('Event created successfully');
      return data;
    } catch (error) {
      return this.handleApiError(error, 'Failed to create event');
    }
  }
  
  async updateEvent(eventId: number, eventData: Partial<Event>): Promise<Event> {
    try {
      const response = await fetch(`${API_BASE_URL}/events/${eventId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(eventData),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error (${response.status}): ${errorText}`);
      }
      
      const data = await response.json();
      toast.success('Event updated successfully');
      return data;
    } catch (error) {
      return this.handleApiError(error, 'Failed to update event');
    }
  }
  
  async deleteEvent(eventId: number): Promise<{ message: string }> {
    try {
      const response = await fetch(`${API_BASE_URL}/events/${eventId}`, {
        method: 'DELETE',
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error (${response.status}): ${errorText}`);
      }
      
      const data = await response.json();
      toast.success('Event deleted successfully');
      return data;
    } catch (error) {
      return this.handleApiError(error, 'Failed to delete event');
    }
  }
  
  async checkConflicts(startTime: string, endTime: string, excludeEventId?: number): Promise<{
    conflicts: Event[],
    has_conflicts: boolean
  }> {
    try {
      const queryParams = new URLSearchParams({
        start: startTime,
        end: endTime,
      });
      
      if (excludeEventId) {
        queryParams.append('exclude_event_id', excludeEventId.toString());
      }
      
      const response = await fetch(`${API_BASE_URL}/check-conflicts?${queryParams}`);
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error (${response.status}): ${errorText}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error checking conflicts:', error);
      return { conflicts: [], has_conflicts: false };
    }
  }
  
  // Simple health check
  async checkApiHealth(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE_URL}/health`);
      return response.ok;
    } catch (error) {
      console.error('API health check failed:', error);
      return false;
    }
  }
}

export const apiService = new ApiService();