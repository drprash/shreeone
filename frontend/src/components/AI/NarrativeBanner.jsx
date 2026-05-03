import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Sparkles, X } from 'lucide-react';
import { getNarratives, dismissNarrative } from '../../services/aiAPI';
import { useAIStatus } from '../../hooks/useAIStatus';

const NarrativeBanner = () => {
  const aiStatus = useAIStatus();
  const queryClient = useQueryClient();

  const { data: narratives = [] } = useQuery({
    queryKey: ['ai-narratives'],
    queryFn: getNarratives,
    enabled: aiStatus.ai_services_enabled && aiStatus.ai_monthly_narrative_enabled !== false,
    staleTime: 1000 * 60 * 5,
  });

  const { mutate: dismiss } = useMutation({
    mutationFn: dismissNarrative,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai-narratives'] }),
  });

  // Show the most recent undismissed narrative
  const narrative = narratives[0];
  if (!narrative) return null;

  const isWeekly = narrative.narrative_type === 'WEEKLY';

  return (
    <div className={`rounded-xl border p-4 mb-6 flex gap-3 items-start
      ${isWeekly
        ? 'bg-violet-50 border-violet-200 dark:bg-violet-900/20 dark:border-violet-700'
        : 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-700'}`}
    >
      <Sparkles className={`w-4 h-4 mt-0.5 shrink-0
        ${isWeekly ? 'text-violet-500' : 'text-blue-500'}`}
      />
      <div className="flex-1 min-w-0">
        <p className={`text-xs font-medium mb-1
          ${isWeekly ? 'text-violet-600 dark:text-violet-400' : 'text-blue-600 dark:text-blue-400'}`}
        >
          {isWeekly ? 'Weekly digest' : 'Monthly summary'} · {narrative.period_label}
        </p>
        <p className="text-sm text-gray-700 dark:text-slate-300 leading-relaxed">
          {narrative.content}
        </p>
      </div>
      <button
        onClick={() => dismiss(narrative.id)}
        className="shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-slate-300"
        title="Dismiss"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};

export default NarrativeBanner;
