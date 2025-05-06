
import React from 'react';
import MainLayout from '@/components/layout/MainLayout';
import ChatInterface from '@/components/chat/ChatInterface';

const Index: React.FC = () => {
  return (
    <MainLayout>
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6 aura-gradient-text">Chat with Aura</h1>
        <ChatInterface />
      </div>
    </MainLayout>
  );
};

export default Index;
