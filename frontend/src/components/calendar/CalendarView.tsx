import React, { useState, useEffect, useCallback } from 'react';
import { Calendar } from '@/components/ui/calendar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { apiService, Event } from '@/services/api';
import { format, parseISO, isSameDay, endOfMonth, startOfMonth } from 'date-fns';
import { Badge } from '@/components/ui/badge';
import { Clock, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import ApiError from '../ui/api-error';

const CalendarView: React.FC = () => {
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(new Date());
  const [events, setEvents] = useState<Event[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [apiError, setApiError] = useState<Error | null>(null);
  const [eventDates, setEventDates] = useState<Date[]>([]);
  const [fetchingMonth, setFetchingMonth] = useState<Date | null>(null);

  // Function to fetch events for a specific month
  const fetchEventsForMonth = useCallback(async (date: Date) => {
    try {
      setIsLoading(true);
      setApiError(null);
      setFetchingMonth(date);
      
      // Calculate start and end of month
      const start = startOfMonth(date);
      const end = endOfMonth(date);
      
      // Fetch events from API
      const fetchedEvents = await apiService.getEvents(start, end);
      setEvents(fetchedEvents);
      
      // Extract dates with events for highlighting in calendar
      const dates = fetchedEvents.map(event => parseISO(event.start_time));
      setEventDates(dates);
    } catch (error) {
      console.error('Failed to fetch events:', error);
      setApiError(error instanceof Error ? error : new Error('Failed to fetch events'));
    } finally {
      setIsLoading(false);
      setFetchingMonth(null);
    }
  }, []);

  // Fetch events when the component mounts
  useEffect(() => {
    if (selectedDate) {
      fetchEventsForMonth(selectedDate);
    }
  }, [fetchEventsForMonth, selectedDate]);

  // Handler for month change
  const handleMonthChange = (date: Date) => {
    fetchEventsForMonth(date);
  };

  // Filter events for the selected date
  const filteredEvents = events.filter((event) => 
    selectedDate && isSameDay(parseISO(event.start_time), selectedDate)
  );

  // Function to determine importance badge
  const getImportanceBadge = (importance: number) => {
    if (importance >= 8) {
      return <Badge className="bg-red-500">High</Badge>;
    } else if (importance >= 5) {
      return <Badge className="bg-yellow-500">Medium</Badge>;
    } else {
      return <Badge>Low</Badge>;
    }
  };

  return (
    <div>
      {apiError && (
        <ApiError 
          message="Failed to fetch calendar events from the backend."
          error={apiError}
          action={() => selectedDate && fetchEventsForMonth(selectedDate)}
        />
      )}
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-1">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle>Calendar</CardTitle>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => selectedDate && fetchEventsForMonth(selectedDate)}
                disabled={isLoading}
              >
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
            </CardHeader>
            <CardContent>
              <Calendar
                mode="single"
                selected={selectedDate}
                onSelect={setSelectedDate}
                onMonthChange={handleMonthChange}
                className="rounded-md border"
                disabled={isLoading}
                modifiers={{
                  hasEvents: (date) => 
                    eventDates.some(eventDate => isSameDay(eventDate, date))
                }}
                modifiersStyles={{
                  hasEvents: { 
                    fontWeight: 'bold',
                    backgroundColor: 'hsl(var(--primary) / 0.1)',
                    color: 'hsl(var(--primary))'
                  }
                }}
              />
            </CardContent>
          </Card>
        </div>
        
        <div className="md:col-span-2">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>
                {selectedDate 
                  ? `Events for ${format(selectedDate, 'MMMM d, yyyy')}`
                  : 'Events'
                }
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center h-32">
                  <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary"></div>
                </div>
              ) : filteredEvents.length > 0 ? (
                <div className="space-y-4">
                  {filteredEvents.map((event) => (
                    <div 
                      key={event.event_id} 
                      className="p-4 border rounded-lg animate-fade-in"
                    >
                      <div className="flex items-start justify-between mb-1">
                        <h3 className="font-medium">{event.title}</h3>
                        {getImportanceBadge(event.importance)}
                      </div>
                      
                      {event.description && (
                        <p className="text-sm text-muted-foreground">
                          {event.description}
                        </p>
                      )}
                      
                      <div className="flex items-center mt-2 text-sm text-muted-foreground">
                        <Clock className="h-3.5 w-3.5 mr-1" />
                        <span>
                          {format(parseISO(event.start_time), 'h:mm a')} - 
                          {format(parseISO(event.end_time), 'h:mm a')}
                        </span>
                      </div>
                      
                      {event.location && (
                        <div className="mt-1 text-sm text-muted-foreground">
                          📍 {event.location}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-muted-foreground">
                    No events scheduled for this date.
                  </p>
                  <p className="text-sm text-muted-foreground mt-2">
                    Try asking Aura to schedule something for you.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default CalendarView;