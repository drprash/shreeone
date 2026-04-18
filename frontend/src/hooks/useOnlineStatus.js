import { useState, useEffect, useCallback, useRef } from 'react';

const PING_TIMEOUT = 5000;   // 5 s — max wait for a single ping
const RETRY_INTERVAL = 15000; // 15 s — poll when server is unreachable

/**
 * Ping the /health endpoint (nginx proxies it to the backend).
 * Uses GET (not HEAD) because the backend only registers GET for this route.
 * Any HTTP response means the server is reachable; only a network error means
 * it is not.
 */
async function pingServer() {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), PING_TIMEOUT);
    await fetch(`${window.location.origin}/health`, {
      signal: controller.signal,
      cache: 'no-store',
    });
    clearTimeout(timer);
    return true;
  } catch {
    return false;
  }
}

/**
 * Server-reachability hook.
 *
 * Returns `{ isOnline, checkNow }` where `isOnline` is true when the API
 * server last responded to a ping, and `checkNow()` forces an immediate
 * re-check (returns a promise resolving to the result).
 *
 * Re-checks automatically on:
 *  - mount
 *  - browser `online` event (verify — the event only means a NIC is up)
 *  - browser `offline` event (trust — no interface = definitely unreachable)
 *  - `visibilitychange` to visible (app foregrounded — network may have changed)
 *
 * When the server is unreachable, polls every 15 s to detect recovery.
 */
export function useOnlineStatus() {
  // Optimistic initial value — corrected on mount by the first ping.
  const [isOnline, setIsOnline] = useState(true);
  const retryRef = useRef(null);

  const checkNow = useCallback(async () => {
    const reachable = await pingServer();
    setIsOnline(reachable);
    return reachable;
  }, []);

  // Event-driven checks
  useEffect(() => {
    checkNow(); // verify on mount

    const onOnline = () => checkNow(); // NIC came up — verify server
    const onOffline = () => setIsOnline(false); // NIC down — definitely unreachable
    const onVisibility = () => {
      if (document.visibilityState === 'visible') checkNow();
    };

    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [checkNow]);

  // When unreachable, poll to detect recovery.
  // When reachable, stop polling (event-driven checks are sufficient).
  useEffect(() => {
    clearInterval(retryRef.current);
    if (!isOnline) {
      retryRef.current = setInterval(checkNow, RETRY_INTERVAL);
    }
    return () => clearInterval(retryRef.current);
  }, [isOnline, checkNow]);

  return { isOnline, checkNow };
}
