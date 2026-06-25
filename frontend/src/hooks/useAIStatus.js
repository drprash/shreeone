import { useQuery } from '@tanstack/react-query';
import { getAIStatus } from '../services/aiAPI';

export const useAIStatus = () => {
  const { data } = useQuery({
    queryKey: ['ai-status'],
    queryFn: getAIStatus,
    staleTime: 1000 * 60,
    retry: false,
  });
  return data ?? { ai_service_available: false, ai_services_enabled: true };
};
