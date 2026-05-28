import { useState, useRef, useEffect, useCallback } from 'react';
import { MessageCircle, Send, X, Sparkles, ChevronDown } from 'lucide-react';

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

export default function ReportChat({ ticker, reportData }: ReportChatProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return;

      const userMessage: Message = { role: 'user', content: text.trim() };
      setMessages((prev) => [...prev, userMessage]);
      setInput('');
      setIsStreaming(true);

      // Add empty assistant message that we'll stream into
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

        if (!response.ok) {
          throw new Error(`Error ${response.status}`);
        }

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
                    updated[updated.length - 1] = {
                      ...last,
                      content: last.content + data.content,
                    };
                  }
                  return updated;
                });
              }
              if (data.error) {
                setMessages((prev) => {
                  const updated = [...prev];
                  updated[updated.length - 1] = {
                    role: 'assistant',
                    content: `Sorry, something went wrong: ${data.error}`,
                  };
                  return updated;
                });
              }
            } catch {
              // skip malformed
            }
          }
        }
      } catch (err: any) {
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[updated.length - 1]?.role === 'assistant' && !updated[updated.length - 1].content) {
            updated[updated.length - 1] = {
              role: 'assistant',
              content: 'Sorry, I couldn\'t connect. Please try again.',
            };
          }
          return updated;
        });
      } finally {
        setIsStreaming(false);
      }
    },
    [ticker, reportData, messages, isStreaming],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  // Floating button when closed
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 bg-accent hover:bg-accent-hover text-white rounded-full p-4 shadow-lg transition-all hover:scale-105 cursor-pointer flex items-center gap-2"
      >
        <Sparkles size={20} />
        <span className="text-sm font-medium hidden sm:inline">Ask AI about {ticker}</span>
        <MessageCircle size={20} className="sm:hidden" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-0 right-0 sm:bottom-6 sm:right-6 z-50 w-full sm:w-[420px] sm:max-w-[calc(100vw-2rem)] bg-white border border-border sm:rounded-[16px] rounded-t-[16px] shadow-2xl flex flex-col overflow-hidden"
      style={{ height: 'min(600px, calc(100vh - 4rem))' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-accent text-white rounded-t-[16px]">
        <div className="flex items-center gap-2">
          <Sparkles size={18} />
          <span className="font-semibold text-sm">Ask AI about {ticker}</span>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="hover:bg-white/20 rounded-full p-1 transition-colors cursor-pointer"
        >
          <ChevronDown size={18} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-muted text-center mt-2 mb-4">
              Ask anything about {ticker}'s financials, risks, or outlook. Answers are based on the report data.
            </p>
            <div className="space-y-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => sendMessage(q)}
                  className="w-full text-left text-sm px-3 py-2 rounded-[8px] border border-border hover:border-accent hover:text-accent transition-colors cursor-pointer"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] px-3 py-2 rounded-[12px] text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-accent text-white'
                  : 'bg-surface text-fg'
              }`}
            >
              {msg.role === 'assistant' ? (
                <div
                  className="prose prose-sm max-w-none [&_p]:my-1 [&_ul]:my-1 [&_li]:my-0.5"
                  dangerouslySetInnerHTML={{
                    __html: formatMarkdown(msg.content || (isStreaming && i === messages.length - 1 ? '●' : '')),
                  }}
                />
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="px-3 py-3 border-t border-border flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about financials, risks, outlook..."
          className="flex-1 px-3 py-2 text-sm rounded-[8px] border border-border focus:border-accent focus:outline-none transition-colors"
          disabled={isStreaming}
        />
        <button
          type="submit"
          disabled={!input.trim() || isStreaming}
          className="p-2 rounded-[8px] bg-accent text-white disabled:opacity-40 hover:bg-accent-hover transition-colors cursor-pointer disabled:cursor-not-allowed"
        >
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}

/** Simple markdown → HTML (bold, bullets, line breaks) */
function formatMarkdown(text: string): string {
  if (!text) return '';
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^- (.*)/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
    .replace(/\n/g, '<br/>');
}
