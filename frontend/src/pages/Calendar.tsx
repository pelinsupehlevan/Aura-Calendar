
import { useState } from "react";
import { useAppStore } from "@/lib/store";
import { format, addDays, startOfWeek, eachDayOfInterval, isSameDay, isSameMonth } from "date-fns";
import { Calendar } from "@/components/ui/calendar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { CalendarEvent } from "@/lib/types";

export default function CalendarPage() {
  const { events } = useAppStore();
  const [date, setDate] = useState<Date | undefined>(new Date());
  const [view, setView] = useState<"month" | "week">("month");

  const eventsForDate = (date: Date) => {
    return events.filter(event => 
      isSameDay(new Date(event.date), date)
    );
  };

  const weekDays = date 
    ? eachDayOfInterval({
        start: startOfWeek(date, { weekStartsOn: 1 }),
        end: addDays(startOfWeek(date, { weekStartsOn: 1 }), 6),
      })
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col space-y-4 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
        <h1 className="text-2xl font-bold">Calendar</h1>
        <div className="flex space-x-2">
          <Badge 
            variant={view === "month" ? "default" : "outline"} 
            className="cursor-pointer"
            onClick={() => setView("month")}
          >
            Month
          </Badge>
          <Badge 
            variant={view === "week" ? "default" : "outline"} 
            className="cursor-pointer"
            onClick={() => setView("week")}
          >
            Week
          </Badge>
        </div>
      </div>

      {view === "month" ? (
        <Card className="border">
          <Calendar
            mode="single"
            selected={date}
            onSelect={setDate}
            className="rounded-md border shadow-sm"
          />
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-7 gap-1 text-center text-sm font-medium">
            {weekDays.map((day) => (
              <div key={day.toString()} className="py-2">
                <div className="mb-1 text-xs">{format(day, 'EEE')}</div>
                <div className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full mx-auto",
                  isSameDay(day, new Date()) && "bg-primary text-primary-foreground"
                )}>
                  {format(day, 'd')}
                </div>
              </div>
            ))}
          </div>
          
          <div className="grid grid-cols-7 gap-1">
            {weekDays.map((day) => {
              const dayEvents = eventsForDate(day);
              return (
                <Card key={day.toString()} className={cn(
                  "min-h-[120px] border",
                  isSameDay(day, new Date()) && "ring-1 ring-primary"
                )}>
                  <CardContent className="p-2 space-y-1">
                    {dayEvents.length > 0 ? (
                      dayEvents.map(event => (
                        <div 
                          key={event.id} 
                          className="text-xs p-1 rounded truncate"
                          style={{ backgroundColor: event.color || 'hsl(var(--primary/15%))' }}
                        >
                          {format(new Date(event.date), 'HH:mm')} {event.title}
                        </div>
                      ))
                    ) : (
                      <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                        No events
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {date && (
        <Card>
          <CardHeader>
            <CardTitle>Events on {format(date, 'MMMM d, yyyy')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {eventsForDate(date).length > 0 ? (
              eventsForDate(date).map(event => (
                <div key={event.id} className="flex items-center space-x-2 p-2 rounded-md hover:bg-muted/50">
                  <div 
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: event.color || 'hsl(var(--primary))' }}
                  ></div>
                  <div className="flex-1">
                    <p className="font-medium">{event.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {event.allDay 
                        ? 'All day' 
                        : format(new Date(event.date), 'HH:mm')}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-muted-foreground text-sm">No events on this day</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
