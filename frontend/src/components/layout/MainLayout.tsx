
import React from 'react';
import Navbar from './Navbar';
import { Toaster } from "@/components/ui/sonner";

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Toaster position="top-right" />
      <Navbar />
      <main className="flex-1 container mx-auto p-4 md:p-6">
        {children}
      </main>
    </div>
  );
};

export default MainLayout;
