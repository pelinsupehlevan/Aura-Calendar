import React, { useEffect, useState } from 'react';
import { Wifi, WifiOff } from 'lucide-react';
import { apiService } from '@/services/api';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { API_CONFIG } from '@/config';

const ConnectionStatus: React.FC = () => {
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [lastCheckTime, setLastCheckTime] = useState(0);

  // Check connection on component mount and periodically
  useEffect(() => {
    const checkConnection = async () => {
      // Don't check more often than every 30 seconds
      const now = Date.now();
      if (now - lastCheckTime < 30000) {
        return;
      }
      
      if (isChecking) return;
      
      setIsChecking(true);
      setLastCheckTime(now);
      
      try {
        const isHealthy = await apiService.checkApiHealth();
        setIsConnected(isHealthy);
      } catch (error) {
        setIsConnected(false);
        console.error('Connection check failed:', error);
      } finally {
        setIsChecking(false);
      }
    };
    
    // Check immediately on mount
    checkConnection();
    
    // Check every 60 seconds instead of 30
    const interval = setInterval(checkConnection, 60000);
    
    return () => clearInterval(interval);
  }, [isChecking, lastCheckTime]);

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex items-center">
            {isConnected === null ? (
              <div className="h-4 w-4 rounded-full bg-gray-300 animate-pulse" />
            ) : isConnected ? (
              <Wifi className="h-4 w-4 text-green-500" />
            ) : (
              <WifiOff className="h-4 w-4 text-red-500" />
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom">
          <p>
            {isConnected === null
              ? 'Checking API connection...'
              : isConnected
              ? 'Connected to Aura Calendar API'
              : `Not connected to API at ${API_CONFIG.BASE_URL}`}
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default ConnectionStatus;