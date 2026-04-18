import { useQuery } from '@tanstack/react-query';
import { getAIStatus } from '../services/aiAPI';

export const useAIStatus = () => {
  const { data } = useQuery({
    queryKey: ['ai-status'],
    queryFn: getAIStatus,
    staleTime: 1000 * 60,  // re-check every minute
    retry: false,
    // Silently returns undefined if AI is unreachable — callers check ai_service_available
  });
  return data ?? { ai_service_available: false };
};
