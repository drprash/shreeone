import { WifiOff, RefreshCw } from 'lucide-react';
import { useOfflineQueue } from '../context/OfflineQueueContext';

export default function OfflineBanner() {
  const { isOnline, isSyncing, pendingOps, syncNow } = useOfflineQueue();
  const count = pendingOps.length;

  if (isOnline && !isSyncing && count === 0) return null;

  if (!isOnline) {
    return (
      <div className="bg-amber-50 dark:bg-amber-900/30 border-b border-amber-200 dark:border-amber-700 px-4 py-2 flex items-center gap-2 text-amber-800 dark:text-amber-200 text-sm">
        <WifiOff className="w-4 h-4 flex-shrink-0" />
        <span>
          You're offline. New transactions are saved locally and will sync automatically when you reconnect.
        </span>
        {count > 0 && (
          <span className="ml-auto font-semibold whitespace-nowrap">{count} pending</span>
        )}
      </div>
    );
  }

  if (isSyncing) {
    return (
      <div className="bg-blue-50 dark:bg-blue-900/30 border-b border-blue-200 dark:border-blue-700 px-4 py-2 flex items-center gap-2 text-blue-800 dark:text-blue-200 text-sm">
        <RefreshCw className="w-4 h-4 flex-shrink-0 animate-spin" />
        <span>Syncing {count} offline transaction{count !== 1 ? 's' : ''}…</span>
      </div>
    );
  }

  // Online, not syncing, but still has pending (failed to sync)
  if (count > 0) {
    return (
      <div className="bg-red-50 dark:bg-red-900/30 border-b border-red-200 dark:border-red-700 px-4 py-2 flex items-center gap-2 text-red-800 dark:text-red-200 text-sm">
        <WifiOff className="w-4 h-4 flex-shrink-0" />
        <span>{count} transaction{count !== 1 ? 's' : ''} failed to sync.</span>
        <button
          onClick={syncNow}
          className="ml-auto underline font-medium whitespace-nowrap"
        >
          Retry
        </button>
      </div>
    );
  }

  return null;
}
