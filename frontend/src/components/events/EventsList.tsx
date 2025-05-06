
import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { apiService, Event } from '@/services/api';
import { format, isSameDay, parseISO } from 'date-fns';
import { Calendar, Clock } from 'lucide-react';

const EventsList: React.FC = () => {
  const [events, setEvents] = useState<Event[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const fetchedEvents = await apiService.getEvents();
        setEvents(fetchedEvents);
      } catch (error) {
        console.error('Failed to fetch events:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchEvents();
  }, []);

  // Group events by date
  const groupedEvents = events.reduce((acc, event) => {
    const date = parseISO(event.start_time).toDateString();
    if (!acc[date]) {
      acc[date] = [];
    }
    acc[date].push(event);
    return acc;
  }, {} as Record<string, Event[]>);

  // Sort dates chronologically
  const sortedDates = Object.keys(groupedEvents).sort(
    (a, b) => new Date(a).getTime() - new Date(b).getTime()
  );

  const getImportanceBadge = (importance: number) => {
    if (importance >= 8) {
      return <Badge className="bg-red-500">High</Badge>;
    } else if (importance >= 5) {
      return <Badge className="bg-yellow-500">Medium</Badge>;
    } else {
      return <Badge>Low</Badge>;
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[70vh] items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col h-[70vh] items-center justify-center text-center">
        <Calendar className="h-16 w-16 mb-4 text-muted-foreground" />
        <h2 className="text-2xl font-semibold mb-2">No events found</h2>
        <p className="text-muted-foreground max-w-md">
          You don't have any events scheduled. Try asking Aura to create one for you.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {sortedDates.map((dateStr) => {
        const date = new Date(dateStr);
        const isToday = isSameDay(date, new Date());
        
        return (
          <div key={dateStr} className="animate-fade-in">
            <div className="flex items-center mb-4">
              <div className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center mr-3">
                <Calendar className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-lg font-medium">
                  {isToday ? 'Today' : format(date, 'EEEE, MMMM d')}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {groupedEvents[dateStr].length} events
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {groupedEvents[dateStr].map((event) => (
                <Card key={event.event_id} className="overflow-hidden">
                  <CardContent className="p-0">
                    <div className="flex border-l-4 border-primary h-full">
                      <div className="p-4 flex-1">
                        <div className="flex items-start justify-between">
                          <h4 className="font-medium">{event.title}</h4>
                          {getImportanceBadge(event.importance)}
                        </div>
                        
                        {event.description && (
                          <p className="text-sm text-muted-foreground mt-1">
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
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default EventsList;
