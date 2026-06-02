import { useState, useRef, useEffect, useCallback } from 'react';
import { MessageCircle, Send, X, Sparkles, RotateCcw, Copy, Check, ChevronDown } from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ReportChatProps {
  ticker: string;
  reportData: Record<string, any>;
}

const SUGGESTED_QUESTIONS = [
  "What's the biggest risk for this company?",
  "Is this stock undervalued based on the data?",
  "Summarize the key findings in 3 bullets",
  "How does it compare to its peers?",
  "What are the strongest bullish signals?",
];

// ── Markdown renderer ─────────────────────────────────────────────────────────
function renderMarkdown(text: string): string {
  if (!text) return '';

  // Escape HTML first
  const escape = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const lines = text.split('\n');
  const out: string[] = [];
  let inUl = false;
  let inOl = false;

  const closeList = () => {
    if (inUl) { out.push('</ul>'); inUl = false; }
    if (inOl) { out.push('</ol>'); inOl = false; }
  };

  const inlineFormat = (s: string) =>
    escape(s)
      .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code class="bg-surface px-1 rounded text-xs font-mono">$1</code>')
      .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" class="text-accent underline" target="_blank">$1</a>');

  for (const raw of lines) {
    const line = raw;

    // Headings
    if (/^### /.test(line)) { closeList(); out.push(`<h3 class="font-semibold text-sm mt-3 mb-1">${inlineFormat(line.slice(4))}</h3>`); continue; }
    if (/^## /.test(line))  { closeList(); out.push(`<h2 class="font-semibold text-sm mt-3 mb-1">${inlineFormat(line.slice(3))}</h2>`); continue; }
    if (/^# /.test(line))   { closeList(); out.push(`<h1 class="font-bold text-sm mt-3 mb-1">${inlineFormat(line.slice(2))}</h1>`); continue; }

    // Horizontal rule
    if (/^---+$/.test(line.trim())) { closeList(); out.push('<hr class="border-border my-2"/>'); continue; }

    // Unordered list
    const ulMatch = line.match(/^[-*•]\s+(.*)/);
    if (ulMatch) {
      if (!inUl) { closeList(); out.push('<ul class="list-disc list-inside space-y-0.5 my-1 ml-1">'); inUl = true; }
      out.push(`<li class="text-sm">${inlineFormat(ulMatch[1])}</li>`);
      continue;
    }

    // Ordered list
    const olMatch = line.match(/^\d+\.\s+(.*)/);
    if (olMatch) {
      if (!inOl) { closeList(); out.push('<ol class="list-decimal list-inside space-y-0.5 my-1 ml-1">'); inOl = true; }
      out.push(`<li class="text-sm">${inlineFormat(olMatch[1])}</li>`);
      continue;
    }

    // Empty line
    if (!line.trim()) {
      closeList();
      out.push('<div class="h-2"/>');
      continue;
    }

    // Regular paragraph
    closeList();
    out.push(`<p class="text-sm leading-relaxed">${inlineFormat(line)}</p>`);
  }

  closeList();
  return out.join('');
}

// ── Streaming cursor ──────────────────────────────────────────────────────────
function StreamingCursor() {
  return (
    <span className="inline-flex items-center gap-0.5 ml-0.5 align-middle">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1 h-1 rounded-full bg-muted animate-bounce"
          style={{ animationDelay: `${i * 0.15}s`, animationDuration: '0.8s' }}
        />
      ))}
    </span>
  );
}

// ── Copy button ───────────────────────────────────────────────────────────────
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button
      onClick={copy}
      className="p-1.5 rounded-lg bg-card border border-border shadow-sm transition-all hover:bg-surface2 active:scale-95"
      title="Copy response"
    >
      {copied ? <Check size={12} className="text-green" /> : <Copy size={12} className="text-muted" />}
    </button>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ReportChat({ ticker, reportData }: ReportChatProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  useEffect(() => {
    if (isOpen && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isOpen]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 100) + 'px';
    }
  }, [input]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return;

      const userMessage: Message = { role: 'user', content: text.trim() };
      setMessages((prev) => [...prev, userMessage]);
      setInput('');
      setIsStreaming(true);
      setShowSuggestions(false);

      setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

      const token = localStorage.getItem('tickrai_token');

      try {
        const response = await fetch(`/api/reports/${ticker}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: text.trim(),
            report_data: reportData,
            history: messages,
          }),
        });

        if (!response.ok) throw new Error(`Error ${response.status}`);

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No reader');

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const data = JSON.parse(line.slice(6));
              if (data.content) {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.role === 'assistant') {
                    updated[updated.length - 1] = { ...last, content: last.content + data.content };
                  }
                  return updated;
                });
              }
              if (data.error) {
                setMessages((prev) => {
                  const updated = [...prev];
                  updated[updated.length - 1] = { role: 'assistant', content: `Sorry, something went wrong: ${data.error}` };
                  return updated;
                });
              }
            } catch { /* skip malformed */ }
          }
        }
      } catch {
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[updated.length - 1]?.role === 'assistant' && !updated[updated.length - 1].content) {
            updated[updated.length - 1] = { role: 'assistant', content: "Sorry, I couldn't connect. Please try again." };
          }
          return updated;
        });
      } finally {
        setIsStreaming(false);
        setTimeout(() => textareaRef.current?.focus(), 50);
      }
    },
    [ticker, reportData, messages, isStreaming],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setShowSuggestions(true);
    setTimeout(() => textareaRef.current?.focus(), 50);
  };

  // ── Floating button ──
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 bg-accent hover:bg-accent-hover text-white rounded-full px-4 py-3 shadow-lg transition-all hover:scale-105 cursor-pointer flex items-center gap-2"
      >
        <Sparkles size={18} />
        <span className="text-sm font-semibold hidden sm:inline">Ask AI about {ticker}</span>
        <MessageCircle size={18} className="sm:hidden" />
      </button>
    );
  }

  const hasMessages = messages.length > 0;

  return (
    <div
      className="fixed bottom-0 right-0 sm:bottom-6 sm:right-6 z-50 w-full sm:w-[440px] sm:max-w-[calc(100vw-2rem)] bg-card border border-border sm:rounded-2xl rounded-t-2xl shadow-2xl flex flex-col overflow-hidden"
      style={{ height: 'min(620px, calc(100vh - 3rem))' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-accent text-white rounded-t-2xl shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center">
            <Sparkles size={15} />
          </div>
          <div>
            <p className="font-semibold text-sm leading-tight">TickrAI Research</p>
            <p className="text-white/70 text-xs leading-tight">{ticker} · Report Q&A</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {hasMessages && (
            <button
              onClick={clearChat}
              className="hover:bg-white/20 rounded-full p-1.5 transition-colors cursor-pointer"
              title="Clear chat"
            >
              <RotateCcw size={15} />
            </button>
          )}
          <button
            onClick={() => setIsOpen(false)}
            className="hover:bg-white/20 rounded-full p-1.5 transition-colors cursor-pointer"
            title="Close"
          >
            <ChevronDown size={15} />
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="hover:bg-white/20 rounded-full p-1.5 transition-colors cursor-pointer sm:hidden"
            title="Close"
          >
            <X size={15} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">

        {/* Empty state */}
        {!hasMessages && (
          <div className="flex flex-col items-center pt-4 pb-2 text-center">
            <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center mb-3">
              <Sparkles size={22} className="text-accent" />
            </div>
            <p className="text-sm font-semibold text-fg mb-1">Ask anything about {ticker}</p>
            <p className="text-xs text-muted max-w-[260px]">
              Answers are grounded in the full report — financials, risk, peers, earnings, and signals.
            </p>
          </div>
        )}

        {/* Suggested questions — shown when no messages yet */}
        {showSuggestions && !hasMessages && (
          <div className="space-y-2">
            {SUGGESTED_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => sendMessage(q)}
                className="w-full text-left text-sm px-3 py-2.5 rounded-xl border border-border hover:border-accent hover:bg-accent/5 hover:text-accent transition-all cursor-pointer group flex items-center gap-2"
              >
                <span className="text-muted group-hover:text-accent transition-colors">›</span>
                <span>{q}</span>
              </button>
            ))}
          </div>
        )}

        {/* Conversation messages */}
        {messages.map((msg, i) => {
          const isLast = i === messages.length - 1;
          const isStreamingThisMsg = isStreaming && isLast && msg.role === 'assistant';
          const isEmpty = msg.role === 'assistant' && !msg.content;

          return (
            <div
              key={i}
              className={`group relative flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {/* AI avatar */}
              {msg.role === 'assistant' && (
                <div className="w-7 h-7 rounded-full bg-accent/10 flex items-center justify-center shrink-0 mt-0.5">
                  <Sparkles size={13} className="text-accent" />
                </div>
              )}

              <div className={`max-w-[82%] ${msg.role === 'user' ? 'items-end' : 'items-start'} flex flex-col`}>
                <div
                  className={`px-3.5 py-2.5 rounded-2xl ${
                    msg.role === 'user'
                      ? 'bg-accent text-white rounded-tr-sm text-sm leading-relaxed'
                      : 'bg-surface text-fg rounded-tl-sm border border-border/60'
                  }`}
                >
                  {msg.role === 'assistant' ? (
                    <>
                      {isEmpty ? (
                        <StreamingCursor />
                      ) : (
                        <div
                          dangerouslySetInnerHTML={{
                            __html: renderMarkdown(msg.content),
                          }}
                        />
                      )}
                      {isStreamingThisMsg && !isEmpty && <StreamingCursor />}
                    </>
                  ) : (
                    <span className="text-sm">{msg.content}</span>
                  )}
                </div>
              </div>

              {/* Copy button — absolutely positioned, zero layout impact */}
              {msg.role === 'assistant' && msg.content && !isStreamingThisMsg && (
                <div className="absolute bottom-0 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <CopyButton text={msg.content} />
                </div>
              )}
            </div>
          );
        })}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="px-3 py-3 border-t border-border shrink-0 bg-card">
        {/* Suggested question chips — shown after conversation, anchored in input area */}
        {hasMessages && !isStreaming && (
          <div className="mb-2">
            {showSuggestions ? (
              <div className="flex flex-wrap gap-1.5">
                {SUGGESTED_QUESTIONS.slice(0, 3).map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    className="text-xs px-2.5 py-1 rounded-full border border-border hover:border-accent hover:text-accent transition-all cursor-pointer bg-card"
                  >
                    {q}
                  </button>
                ))}
                <button
                  onClick={() => setShowSuggestions(false)}
                  className="text-xs px-2 py-1 text-muted hover:text-accent transition-colors cursor-pointer"
                  title="Hide suggestions"
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowSuggestions(true)}
                className="text-xs text-muted hover:text-accent transition-colors flex items-center gap-1 bg-card"
              >
                <Sparkles size={11} /> Show suggested questions
              </button>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about financials, risks, outlook… (Enter to send)"
            rows={1}
            className="flex-1 px-3 py-2 text-sm rounded-xl border border-border focus:border-accent focus:outline-none transition-colors resize-none leading-relaxed"
            style={{ minHeight: '38px', maxHeight: '100px' }}
            disabled={isStreaming}
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="p-2.5 rounded-xl bg-accent text-white disabled:opacity-40 hover:bg-accent-hover transition-colors cursor-pointer disabled:cursor-not-allowed shrink-0"
          >
            <Send size={15} />
          </button>
        </form>
        <p className="text-xs text-muted mt-1.5 text-center">Shift+Enter for new line</p>
      </div>
    </div>
  );
}
