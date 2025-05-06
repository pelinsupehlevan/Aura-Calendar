import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatMessage, apiService, Event } from '@/services/api';
import { ArrowUp, AlertCircle, Calendar, Trash2, Edit } from 'lucide-react';
import { toast } from 'sonner';
import ApiError from '../ui/api-error';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { format, parseISO } from 'date-fns';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';

// Key for storing chat history in localStorage
const CHAT_HISTORY_KEY = 'aura-chat-history';

interface ConflictAction {
  type: 'show_conflict';
  conflicts: Event[];
  proposed_event: Partial<Event>;
}

const ChatInterface: React.FC = () => {
  // Initialize with default welcome message or stored history
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    // Try to load from localStorage
    const savedMessages = localStorage.getItem(CHAT_HISTORY_KEY);
    if (savedMessages) {
      try {
        // Parse and validate the saved messages
        const parsedMessages = JSON.parse(savedMessages);
        
        // Convert string timestamps back to Date objects
        if (Array.isArray(parsedMessages) && parsedMessages.length > 0) {
          return parsedMessages.map(msg => ({
            ...msg,
            timestamp: new Date(msg.timestamp)
          }));
        }
      } catch (error) {
        console.error('Error parsing saved chat history:', error);
      }
    }
    
    // Default welcome message if no history or invalid history
    return [
      {
        id: '1',
        text: "Hi there! I'm Aura, your smart calendar assistant. How can I help you today?",
        role: 'assistant',
        timestamp: new Date(),
      },
    ];
  });
  
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<Error | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);
  
  // Conflict handling state
  const [conflictDialog, setConflictDialog] = useState<{
    open: boolean;
    conflicts: Event[];
    proposedEvent: Partial<Event>;
  }>({
    open: false,
    conflicts: [],
    proposedEvent: {}
  });
  
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  // Save messages to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(messages));
  }, [messages]);

  // Check backend connection on mount
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const isConnected = await apiService.checkApiHealth();
        setIsBackendConnected(isConnected);
        if (!isConnected) {
          setApiError(new Error("Could not connect to the backend server"));
        }
      } catch (error) {
        setIsBackendConnected(false);
        setApiError(error instanceof Error ? error : new Error("Connection error"));
      }
    };
    
    checkConnection();
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!inputMessage.trim()) return;
    
    // Add user message to the chat
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      text: inputMessage,
      role: 'user',
      timestamp: new Date(),
    };
    
    setMessages((prev) => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setApiError(null);
    
    try {
      // Send message to API
      const response = await apiService.sendMessage(userMessage.text);
      
      // Add assistant response to the chat
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        text: response.text,
        role: 'assistant',
        timestamp: new Date(),
      };
      
      setMessages((prev) => [...prev, assistantMessage]);
      
      // Handle any UI actions from the response
      if (response.ui_action) {
        switch (response.ui_action.type) {
          case 'update_calendar':
            toast.success('Event added to calendar');
            break;
          case 'remove_event':
            toast.success('Event removed from calendar');
            break;
          case 'show_conflict':
            const conflictAction = response.ui_action as ConflictAction;
            setConflictDialog({
              open: true,
              conflicts: conflictAction.conflicts,
              proposedEvent: conflictAction.proposed_event
            });
            break;
          // Add more action types as needed
        }
      }
    } catch (error) {
      console.error('Error processing message:', error);
      
      // Set API error for display
      setApiError(error instanceof Error ? error : new Error("Failed to send message"));
      
      // Also add an error message in the chat interface
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        text: "I'm having trouble communicating with my backend. Please check if the server is running.",
        role: 'assistant',
        timestamp: new Date(),
      };
      
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // Clear chat history
  const clearChat = () => {
    // Keep only the welcome message
    const welcomeMessage = {
      id: Date.now().toString(),
      text: "Hi there! I'm Aura, your smart calendar assistant. How can I help you today?",
      role: 'assistant' as const,
      timestamp: new Date(),
    };
    
    setMessages([welcomeMessage]);
    toast.success('Chat history cleared');
  };

  // Retry connection to backend
  const retryConnection = async () => {
    setApiError(null);
    try {
      const isConnected = await apiService.checkApiHealth();
      setIsBackendConnected(isConnected);
      if (isConnected) {
        toast.success("Successfully connected to backend!");
      } else {
        setApiError(new Error("Still unable to connect to the backend"));
      }
    } catch (error) {
      setIsBackendConnected(false);
      setApiError(error instanceof Error ? error : new Error("Connection failed"));
    }
  };

  // Handle auto-expanding textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 150)}px`;
    }
  }, [inputMessage]);

  // Handle conflict resolution
  const handleConflictResolution = async (action: 'replace' | 'cancel', conflictToDelete?: Event) => {
    if (action === 'cancel') {
      setConflictDialog({ open: false, conflicts: [], proposedEvent: {} });
      toast.info("Event creation cancelled");
      
      // Add a message to the chat
      const message: ChatMessage = {
        id: Date.now().toString(),
        text: "I've cancelled the event creation due to the scheduling conflict.",
        role: 'assistant',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, message]);
    } else if (action === 'replace' && conflictToDelete) {
      // Delete the conflicting event and create the new one
      try {
        await apiService.deleteEvent(conflictToDelete.event_id);
        
        // Create the new event
        const newEvent = await apiService.createEvent(conflictDialog.proposedEvent as Omit<Event, 'event_id' | 'status'>);
        
        setConflictDialog({ open: false, conflicts: [], proposedEvent: {} });
        toast.success(`Replaced "${conflictToDelete.title}" with "${newEvent.title}"`);
        
        // Add a message to the chat
        const message: ChatMessage = {
          id: Date.now().toString(),
          text: `I've deleted "${conflictToDelete.title}" and created "${newEvent.title}" as requested.`,
          role: 'assistant',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, message]);
      } catch (error) {
        console.error('Error resolving conflict:', error);
        toast.error('Failed to resolve conflict. Please try again.');
      }
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)]">
      {/* Clear chat button */}
      <div className="flex justify-end mb-2">
        <Button 
          variant="outline" 
          size="sm" 
          onClick={clearChat}
        >
          Clear Chat
        </Button>
      </div>
      
      {/* Show API error if we have one */}
      {apiError && (
        <ApiError 
          title="Backend Connection Issue" 
          message="I'm having trouble connecting to the Aura Calendar backend. Some features might not work correctly."
          error={apiError}
          action={retryConnection}
          actionLabel="Retry Connection"
        />
      )}
      
      <div className="flex-1 relative">
        <ScrollArea className="h-full pr-4">
          <div className="space-y-4 px-1 py-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] md:max-w-[70%] px-4 py-3 rounded-lg ${
                    message.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary text-secondary-foreground'
                  }`}
                >
                  <p className="whitespace-pre-wrap break-words">{message.text}</p>
                  <p className="mt-1 text-xs opacity-70">
                    {message.timestamp.toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>
      </div>
      
      <div className="mt-4 border rounded-lg bg-background">
        <form onSubmit={handleSubmit} className="flex items-end">
          <Textarea
            ref={inputRef}
            placeholder="Type a message..."
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            className="flex-1 resize-none min-h-[4rem] max-h-[12rem] bg-transparent border-0 focus-visible:ring-0 focus-visible:ring-offset-0"
            disabled={isLoading || isBackendConnected === false}
          />
          <Button
            type="submit"
            size="icon"
            disabled={isLoading || !inputMessage.trim() || isBackendConnected === false}
            className="mb-3 mr-3"
          >
            {isLoading ? (
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            ) : (
              <ArrowUp className="h-5 w-5" />
            )}
          </Button>
        </form>
      </div>

      {/* Conflict Resolution Dialog */}
      <AlertDialog open={conflictDialog.open} onOpenChange={(open) => setConflictDialog({...conflictDialog, open})}>
        <AlertDialogContent className="max-w-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-yellow-500" />
              Scheduling Conflict
            </AlertDialogTitle>
            <AlertDialogDescription className="pt-2">
              The event "{conflictDialog.proposedEvent.title}" conflicts with existing events. What would you like to do?
            </AlertDialogDescription>
          </AlertDialogHeader>
          
          <div className="py-4 space-y-4">
            <div>
              <h4 className="font-medium mb-2">Proposed Event:</h4>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{conflictDialog.proposedEvent.title}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    {conflictDialog.proposedEvent.start_time && (
                      <span>
                        {format(new Date(conflictDialog.proposedEvent.start_time), 'MMM d, yyyy h:mm a')} - 
                        {conflictDialog.proposedEvent.end_time && format(new Date(conflictDialog.proposedEvent.end_time), 'h:mm a')}
                      </span>
                    )}
                  </div>
                  {conflictDialog.proposedEvent.description && (
                    <p className="mt-1">{conflictDialog.proposedEvent.description}</p>
                  )}
                </CardContent>
              </Card>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">Conflicting Events:</h4>
              <div className="space-y-2">
                {conflictDialog.conflicts.map((conflict) => (
                  <Alert key={conflict.event_id} className="relative">
                    <div className="pr-20">
                      <div className="flex items-center gap-2 font-medium">
                        {conflict.title}
                        <span className="text-xs px-2 py-0.5 bg-secondary rounded">
                          Importance: {conflict.importance}/10
                        </span>
                      </div>
                      <div className="text-sm text-muted-foreground mt-1">
                        {format(parseISO(conflict.start_time), 'MMM d, yyyy h:mm a')} - 
                        {format(parseISO(conflict.end_time), 'h:mm a')}
                      </div>
                      {conflict.description && (
                        <p className="text-sm text-muted-foreground mt-1">
                          {conflict.description}
                        </p>
                      )}
                    </div>
                    <div className="absolute top-2 right-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleConflictResolution('replace', conflict)}
                        className="gap-2"
                      >
                        <Trash2 className="h-3 w-3" />
                        Replace This
                      </Button>
                    </div>
                  </Alert>
                ))}
              </div>
            </div>
          </div>
          
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => handleConflictResolution('cancel')}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction onClick={() => setConflictDialog({...conflictDialog, open: false})}>
              Keep Both (choose different time)
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default ChatInterface;