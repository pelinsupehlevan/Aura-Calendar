import React, { useEffect, useState, ReactNode } from 'react';
import { apiService } from '@/services/api';
import ApiError from './api-error';
import { Card, CardContent } from './card';
import { Loader2 } from 'lucide-react';

interface ApiConnectionWrapperProps {
  children: ReactNode;
  loadingMessage?: string;
  errorMessage?: string;
  showCard?: boolean;
  className?: string;
}

const ApiConnectionWrapper: React.FC<ApiConnectionWrapperProps> = ({
  children,
  loadingMessage = "Connecting to backend...",
  errorMessage = "Failed to connect to the Aura Calendar backend.",
  showCard = true,
  className = "",
}) => {
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [isChecking, setIsChecking] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        setIsChecking(true);
        const isHealthy = await apiService.checkApiHealth();
        
        if (isHealthy) {
          setIsConnected(true);
          setError(null);
        } else {
          setIsConnected(false);
          setError(new Error("Backend server is not responding"));
        }
      } catch (error) {
        setIsConnected(false);
        setError(error instanceof Error ? error : new Error("Failed to connect to backend"));
      } finally {
        setIsChecking(false);
      }
    };

    checkConnection();
  }, []);

  // If still checking, show a loading state
  if (isChecking) {
    return showCard ? (
      <Card className={`p-6 ${className}`}>
        <CardContent className="flex flex-col items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
          <p className="text-muted-foreground">{loadingMessage}</p>
        </CardContent>
      </Card>
    ) : (
      <div className={`flex flex-col items-center justify-center py-8 ${className}`}>
        <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
        <p className="text-muted-foreground">{loadingMessage}</p>
      </div>
    );
  }

  // If not connected, show an error
  if (!isConnected) {
    return (
      <ApiError 
        title="Backend Connection Issue"
        message={errorMessage}
        error={error}
        action={async () => {
          setIsChecking(true);
          setIsConnected(null);
          const isHealthy = await apiService.checkApiHealth();
          setIsConnected(isHealthy);
          setIsChecking(false);
        }}
        actionLabel="Retry Connection"
      />
    );
  }

  // If connected, render children
  return <>{children}</>;
};

export default ApiConnectionWrapper;