
import React from 'react';
import MainLayout from '@/components/layout/MainLayout';
import EventsList from '@/components/events/EventsList';

const EventsPage: React.FC = () => {
  return (
    <MainLayout>
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6 aura-gradient-text">Your Events</h1>
        <EventsList />
      </div>
    </MainLayout>
  );
};

export default EventsPage;
