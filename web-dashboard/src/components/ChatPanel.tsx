import { useState, useRef, useEffect } from 'react';
import { useChatLLM } from '../hooks/useChatLLM';
import type { PatternData } from '../hooks/usePattern';

const SUGGESTIONS = [
  'Is there a taxi available in Punggol now?',
  'Will it rain in East Coast Park in 2 hours?',
  'Which zone has the highest demand in 30 minutes?',
];

interface ChatPanelProps {
  patternData?: PatternData;
}

export default function ChatPanel({ patternData }: ChatPanelProps) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const { messages, loading, offline, offlineReason, sendMessage, clearHistory } = useChatLLM(patternData);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, open]);

  function handleSend(text?: string) {
    const q = (text ?? input).trim();
    if (!q || loading) return;
    setInput('');
    sendMessage(q);
  }

  return (
    <>
      {/* Floating bubble */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          title="Open taxi & weather assistant"
          style={{
            position: 'fixed',
            bottom: 72,
            right: 12,
            zIndex: 1100,
            width: 44,
            height: 44,
            borderRadius: '50%',
            background: 'rgba(6,182,212,0.88)',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 18px rgba(6,182,212,0.5)',
            backdropFilter: 'blur(8px)',
          }}
        >
          <svg width={20} height={20} viewBox="0 0 24 24" fill="none"
            stroke="#fff" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div
          style={{
            position: 'fixed',
            bottom: 72,
            right: 12,
            zIndex: 1100,
            width: 320,
            maxHeight: '65vh',
            display: 'flex',
            flexDirection: 'column',
            borderRadius: 12,
            overflow: 'hidden',
            background: 'rgba(10,14,20,0.94)',
            border: '1px solid rgba(6,182,212,0.22)',
            boxShadow: '0 8px 40px rgba(0,0,0,0.65)',
            backdropFilter: 'blur(14px)',
          }}
        >
          {/* Header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 12px',
            borderBottom: '1px solid rgba(255,255,255,0.07)',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <div style={{
                width: 6, height: 6, borderRadius: '50%',
                background: offline ? '#ef4444' : '#22c55e',
                boxShadow: `0 0 6px ${offline ? '#ef4444' : '#22c55e'}`,
                flexShrink: 0,
              }} />
              <span style={{
                fontSize: 9, fontWeight: 900, letterSpacing: '0.18em',
                color: 'rgba(255,255,255,0.65)', textTransform: 'uppercase',
              }}>
                SG Taxi Assistant
              </span>
              <span style={{
                fontSize: 7, color: 'rgba(255,255,255,0.22)', letterSpacing: '0.12em',
              }}>
                LMStudio
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              {messages.length > 0 && (
                <button
                  onClick={clearHistory}
                  style={{
                    fontSize: 7, color: 'rgba(255,255,255,0.3)', background: 'none',
                    border: 'none', cursor: 'pointer', padding: '2px 6px',
                    borderRadius: 4, letterSpacing: '0.1em', textTransform: 'uppercase',
                  }}
                >
                  Clear
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'rgba(255,255,255,0.4)', fontSize: 15, lineHeight: 1,
                  padding: '0 2px',
                }}
              >
                ✕
              </button>
            </div>
          </div>

          {/* Messages */}
          <div style={{
            flex: 1, overflowY: 'auto', padding: '10px 12px',
            display: 'flex', flexDirection: 'column', gap: 8, minHeight: 120,
          }}>
            {messages.length === 0 ? (
              <div>
                <p style={{
                  fontSize: 10, color: 'rgba(255,255,255,0.3)',
                  marginBottom: 10, lineHeight: 1.5,
                }}>
                  {offlineReason === 'cors'
                    ? 'CORS blocked. In LMStudio: Developer → Local Server → enable "Allow CORS from any origin".'
                    : offlineReason === 'no_model'
                    ? 'LMStudio is running but no model is loaded. Load a model and try again.'
                    : offlineReason === 'not_running'
                    ? 'LMStudio is not running on port 1234. Start LMStudio and load a model.'
                    : 'Ask about Singapore taxis or weather:'}
                </p>
                {!offline && SUGGESTIONS.map(s => (
                  <button
                    key={s}
                    onClick={() => handleSend(s)}
                    style={{
                      display: 'block', width: '100%', textAlign: 'left',
                      padding: '6px 8px', marginBottom: 5,
                      background: 'rgba(6,182,212,0.07)',
                      border: '1px solid rgba(6,182,212,0.16)',
                      borderRadius: 6, cursor: 'pointer',
                      fontSize: 10, color: 'rgba(6,182,212,0.75)',
                      letterSpacing: '0.02em', lineHeight: 1.4,
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            ) : (
              messages.map((msg, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  }}
                >
                  <div style={{
                    maxWidth: '85%',
                    padding: '6px 10px',
                    borderRadius: msg.role === 'user'
                      ? '10px 10px 2px 10px'
                      : '10px 10px 10px 2px',
                    background: msg.role === 'user'
                      ? 'rgba(6,182,212,0.18)'
                      : 'rgba(255,255,255,0.05)',
                    border: `1px solid ${msg.role === 'user'
                      ? 'rgba(6,182,212,0.28)'
                      : 'rgba(255,255,255,0.07)'}`,
                    fontSize: 11,
                    color: 'rgba(255,255,255,0.82)',
                    lineHeight: 1.55,
                  }}>
                    {msg.content}
                  </div>
                </div>
              ))
            )}

            {loading && (
              <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                <div style={{
                  padding: '6px 14px',
                  background: 'rgba(255,255,255,0.05)',
                  borderRadius: '10px 10px 10px 2px',
                  border: '1px solid rgba(255,255,255,0.07)',
                  fontSize: 14,
                  color: 'rgba(255,255,255,0.35)',
                  letterSpacing: 5,
                }}>
                  •••
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div style={{
            padding: '8px 12px',
            borderTop: '1px solid rgba(255,255,255,0.07)',
            display: 'flex',
            gap: 6,
            flexShrink: 0,
          }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              placeholder="Ask about taxis or weather…"
              disabled={loading}
              style={{
                flex: 1,
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 6,
                padding: '6px 8px',
                fontSize: 11,
                color: 'rgba(255,255,255,0.85)',
                outline: 'none',
              }}
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || loading}
              style={{
                padding: '6px 10px',
                background: input.trim() && !loading
                  ? 'rgba(6,182,212,0.78)'
                  : 'rgba(255,255,255,0.06)',
                border: 'none',
                borderRadius: 6,
                cursor: input.trim() && !loading ? 'pointer' : 'default',
                color: input.trim() && !loading ? '#fff' : 'rgba(255,255,255,0.22)',
                fontSize: 13,
                flexShrink: 0,
              }}
            >
              ▶
            </button>
          </div>
        </div>
      )}
    </>
  );
}
