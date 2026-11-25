/** Connect the assessment's server deadline and subscribe to its UI state. */
import { useEffect, useSyncExternalStore } from "react";

export default function useTestTimer(controller) {
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot);

  useEffect(() => {
    const disconnect = controller.connect();
    const synchronize = () => {
      const current = controller.getSnapshot();
      if (!document.hidden && current.phase === "running" && !current.submitting && !current.checking) {
        void controller.checkStatus();
      }
    };
    window.addEventListener("focus", synchronize);
    document.addEventListener("visibilitychange", synchronize);
    return () => {
      disconnect();
      window.removeEventListener("focus", synchronize);
      document.removeEventListener("visibilitychange", synchronize);
    };
  }, [controller]);

  return state;
}
