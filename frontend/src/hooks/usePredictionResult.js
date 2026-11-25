import { useEffect, useState, useSyncExternalStore } from 'react';
import { createPredictionController, predictionStamp } from '../services/profileState.js';

export function usePredictionResult(profileKey, inputs, predict) {
  const key = predictionStamp(profileKey, inputs);
  const [controller] = useState(() => createPredictionController(predict));
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot);
  useEffect(() => {
    controller.select(key);
    return () => controller.cancel();
  }, [controller, key]);
  const current = state.key === key;
  return { result: current ? state.result : null, error: current ? state.error : null,
    busy: current && state.busy, run: (submitted = inputs) => controller.run(key, submitted) };
}
