import { useSyncExternalStore } from 'react';
import { authSession } from '../services/auth.js';
export function useAuth() { return useSyncExternalStore(authSession.subscribe, authSession.getSnapshot); }
