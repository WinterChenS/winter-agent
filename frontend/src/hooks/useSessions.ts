import { useState, useCallback, useEffect } from 'react';
import { Conversation } from '../types/chat';

export function useSessions() {
  const [sessions, setSessions] = useState<Conversation[]>([]);

  useEffect(() => {
    const stored = localStorage.getItem('chat_sessions');
    if (stored) {
      setSessions(JSON.parse(stored));
    }
  }, []);

  const saveSessions = (newSessions: Conversation[]) => {
    setSessions(newSessions);
    localStorage.setItem('chat_sessions', JSON.stringify(newSessions));
  };

  const createSession = useCallback((title: string = '新对话') => {
    const newSession: Conversation = {
      id: crypto.randomUUID(),
      title,
      createdAt: Date.now(),
    };
    saveSessions([newSession, ...sessions]);
    return newSession.id;
  }, [sessions]);

  const removeSession = useCallback((id: string) => {
    const updated = sessions.filter(s => s.id !== id);
    saveSessions(updated);
  }, [sessions]);

  const updateSessionTitle = useCallback((id: string, title: string) => {
    saveSessions(sessions.map(s => s.id === id ? { ...s, title } : s));
  }, [sessions]);

  return {
    sessions,
    createSession,
    removeSession,
    updateSessionTitle
  };
}
