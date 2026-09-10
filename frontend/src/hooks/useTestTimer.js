/**
 * useTestTimer - countdown timer hook for mock tests.
 *
 * - Starts at `totalSeconds` and ticks down once per second while `active`.
 * - Calls onExpire() exactly once when it reaches zero (auto-submit).
 * - The interval is cleared whenever `active` flips or the component
 *   unmounts, so there are no memory leaks.
 * - No setState in effect bodies: the countdown updates inside the interval
 *   callback, and expiry is raised through a ref callback. Fresh attempts
 *   reset the timer by remounting the component that uses this hook.
 */
import { useEffect, useRef, useState } from "react";

export default function useTestTimer({ totalSeconds, onExpire, active }) {
  const [secondsLeft, setSecondsLeft] = useState(totalSeconds);
  const expireRef = useRef(onExpire);

  useEffect(() => {
    expireRef.current = onExpire;
  }, [onExpire]);

  useEffect(() => {
    if (!active) return undefined;

    const interval = setInterval(() => {
      setSecondsLeft((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(interval);
  }, [active]);

  useEffect(() => {
    if (active && secondsLeft === 0) {
      expireRef.current?.();
    }
  }, [active, secondsLeft]);

  return { secondsLeft };
}
