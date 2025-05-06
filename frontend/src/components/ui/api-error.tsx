import React from 'react';
import { AlertCircle, Server } from 'lucide-react';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { API_CONFIG } from '@/config';

interface ApiErrorProps {
  title?: string;
  message?: string;
  error?: Error | string;
  action?: () => void;
  actionLabel?: string;
}

const ApiError: React.FC<ApiErrorProps> = ({
  title = "Connection Error",
  message = "We couldn't connect to the Aura Calendar API.",
  error,
  action,
  actionLabel = "Try Again"
}) => {
  return (
    <Alert variant="destructive" className="my-4">
      <AlertCircle className="h-5 w-5" />
      <AlertTitle className="flex items-center gap-2">
        {title}
      </AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        {error && (
          <div className="mt-2 text-xs opacity-80 rounded bg-destructive/20 p-2 overflow-auto">
            {typeof error === 'string' ? error : error.message || "Unknown error"}
          </div>
        )}
        <div className="mt-3">
          <p className="text-xs mb-2 flex items-center gap-1">
            <Server className="h-3 w-3" /> API URL: {API_CONFIG.BASE_URL}
          </p>
          {action && (
            <Button 
              variant="outline" 
              size="sm" 
              onClick={action}
              className="mt-1"
            >
              {actionLabel}
            </Button>
          )}
        </div>
      </AlertDescription>
    </Alert>
  );
};

export default ApiError;