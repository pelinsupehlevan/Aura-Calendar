
import React from 'react';
import MainLayout from '@/components/layout/MainLayout';
import CalendarView from '@/components/calendar/CalendarView';

const CalendarPage: React.FC = () => {
  return (
    <MainLayout>
      <h1 className="text-3xl font-bold mb-6 aura-gradient-text">Calendar</h1>
      <CalendarView />
    </MainLayout>
  );
};

export default CalendarPage;
