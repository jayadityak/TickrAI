import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';

export interface AgentResult {
  agent_name: string;
  agent_index: number;
  status: string;
  data: any;
  error?: string;
}

interface UseReportReturn {
  agentResults: AgentResult[];
  isLoading: boolean;
  isComplete: boolean;
  isEtf: boolean;
  error: string | null;
  startReport: () => void;
}

/**
 * Parse SSE text chunks into events.
 * Handles the "event: xxx\ndata: {...}\n\n" format.
 */
function parseSSE(text: string): Array<{ event: string; data: string }> {
  const events: Array<{ event: string; data: string }> = [];
  const blocks = text.split('\n\n');
  for (const block of blocks) {
    if (!block.trim()) continue;
    let event = 'message';
    let data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('event: ')) {
        event = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        data = line.slice(6);
      }
    }
    if (data) {
      events.push({ event, data });
    }
  }
  return events;
}

export function useReport(ticker: string | undefined): UseReportReturn {
  const { logout } = useAuth();
  const [agentResults, setAgentResults] = useState<AgentResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [isEtf, setIsEtf] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const stopStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const startReport = useCallback(async () => {
    if (!ticker) return;

    // Reset state
    setAgentResults([]);
    setIsLoading(true);
    setIsComplete(false);
    setIsEtf(false);
    setError(null);
    stopStream();

    const controller = new AbortController();
    abortRef.current = controller;

    // Get the token from localStorage
    const token = localStorage.getItem('tickrai_token');

    // Use VITE_API_URL so the SSE stream hits the Railway backend in production.
    // Native fetch() ignores axios.defaults.baseURL, so we resolve it manually.
    const apiBase = import.meta.env.VITE_API_URL
      ? import.meta.env.VITE_API_URL.replace(/\/$/, '')
      : '/api';

    try {
      const response = await fetch(`${apiBase}/reports/${ticker}/stream`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: controller.signal,
      });

      if (response.status === 401) {
        // Token is expired or invalid — clear it so AuthGate shows fresh sign-in
        logout();
        setIsLoading(false);
        return;
      }

      if (!response.ok) {
        // Try to extract the detail message from the JSON body
        try {
          const body = await response.json();
          const detail = body?.detail || body?.error;
          if (response.status === 404 && detail) {
            setError(`${detail}. This stock may have been delisted or renamed.`);
          } else if (detail) {
            setError(detail);
          } else {
            setError(`Server error (${response.status}). Please try again.`);
          }
        } catch {
          setError(`Server error (${response.status}). Please try again.`);
        }
        setIsLoading(false);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        setError('Streaming not supported.');
        setIsLoading(false);
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE blocks (separated by double newlines)
        const parts = buffer.split('\n\n');
        // Keep the last incomplete part in the buffer
        buffer = parts.pop() || '';

        for (const part of parts) {
          if (!part.trim()) continue;
          const events = parseSSE(part + '\n\n');
          for (const evt of events) {
            if (evt.event === 'report_start') {
              try {
                const d = JSON.parse(evt.data);
                setIsEtf(d.is_etf ?? false);
              } catch { /* ignore */ }
            } else if (evt.event === 'agent_complete') {
              try {
                const result: AgentResult = JSON.parse(evt.data);
                setAgentResults((prev) => {
                  const filtered = prev.filter(
                    (r) => r.agent_index !== result.agent_index,
                  );
                  return [...filtered, result].sort(
                    (a, b) => a.agent_index - b.agent_index,
                  );
                });
              } catch {
                // Ignore malformed events
              }
            } else if (evt.event === 'report_complete') {
              setIsComplete(true);
              setIsLoading(false);
            } else if (evt.event === 'error') {
              try {
                const errData = JSON.parse(evt.data);
                setError(errData.error || 'Unknown error');
              } catch {
                setError('Unknown error');
              }
              setIsLoading(false);
            }
          }
        }
      }

      // Stream finished — mark complete if not already
      setIsLoading(false);
      setIsComplete(true);
    } catch (err: any) {
      if (err.name === 'AbortError') return; // User navigated away
      setError('Connection lost. Please try again.');
      setIsLoading(false);
    }
  }, [ticker, stopStream, logout]);

  // Auto-start when ticker changes
  useEffect(() => {
    if (ticker) {
      startReport();
    }
    return () => {
      stopStream();
    };
  }, [ticker]); // eslint-disable-line react-hooks/exhaustive-deps

  return { agentResults, isLoading, isComplete, isEtf, error, startReport };
}
