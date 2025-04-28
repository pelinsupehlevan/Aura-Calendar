
import { useState } from "react";
import { useAppStore } from "@/lib/store";
import { format } from "date-fns";
import { CalendarEvent } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Calendar as CalendarIcon, Plus, Search, Trash2 } from "lucide-react";

export default function EventsPage() {
  const { events, deleteEvent } = useAppStore();
  const [searchTerm, setSearchTerm] = useState("");
  
  const sortedEvents = [...events].sort((a, b) => {
    return new Date(a.date).getTime() - new Date(b.date).getTime();
  });
  
  const filteredEvents = sortedEvents.filter(event => 
    event.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (event.description && event.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );
  
  const formatEventDate = (event: CalendarEvent) => {
    if (event.allDay) {
      return format(new Date(event.date), 'MMMM d, yyyy');
    }
    
    if (event.endDate) {
      return `${format(new Date(event.date), 'MMM d, HH:mm')} - ${format(new Date(event.endDate), 'HH:mm')}`;
    }
    
    return format(new Date(event.date), 'MMMM d, yyyy HH:mm');
  };
  
  const groupEventsByDate = (events: CalendarEvent[]) => {
    const grouped: Record<string, CalendarEvent[]> = {};
    
    events.forEach(event => {
      const dateKey = format(new Date(event.date), 'yyyy-MM-dd');
      if (!grouped[dateKey]) {
        grouped[dateKey] = [];
      }
      grouped[dateKey].push(event);
    });
    
    return Object.entries(grouped).sort(([dateA], [dateB]) => 
      new Date(dateA).getTime() - new Date(dateB).getTime()
    );
  };

  const groupedEvents = groupEventsByDate(filteredEvents);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Events</h1>
        <Button>
          <Plus className="h-4 w-4 mr-2" /> Add Event
        </Button>
      </div>
      
      <div className="relative">
        <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search events..."
          className="pl-8"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>
      
      <div className="space-y-6">
        {groupedEvents.length > 0 ? (
          groupedEvents.map(([dateKey, dateEvents]) => (
            <div key={dateKey} className="space-y-3">
              <h2 className="text-lg font-semibold sticky top-16 bg-background/95 backdrop-blur z-10 py-2">
                {format(new Date(dateKey), 'EEEE, MMMM d, yyyy')}
              </h2>
              <div className="space-y-3">
                {dateEvents.map(event => (
                  <Card key={event.id} className="overflow-hidden">
                    <div 
                      className="h-1.5" 
                      style={{ backgroundColor: event.color || 'hsl(var(--primary))' }} 
                    />
                    <CardHeader className="pb-2">
                      <div className="flex justify-between items-start">
                        <CardTitle>{event.title}</CardTitle>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-muted-foreground"
                          onClick={() => deleteEvent(event.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      <CardDescription className="flex items-center text-sm">
                        <CalendarIcon className="mr-1 h-3.5 w-3.5" />
                        {formatEventDate(event)}
                      </CardDescription>
                    </CardHeader>
                    {event.description && (
                      <CardContent className="pb-2">
                        <p className="text-sm">{event.description}</p>
                      </CardContent>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          ))
        ) : (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No events found</p>
          </div>
        )}
      </div>
    </div>
  );
}
