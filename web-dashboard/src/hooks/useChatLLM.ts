import { useState } from 'react';
import type { ChatMessage } from '../types';

const LM_BASE = 'http://localhost:1234';

function buildSystemPrompt(ctx: Record<string, unknown>): string {
  const areas = (ctx.areas as Array<Record<string, string>> ?? [])
    .map(a => `- ${a.name} (${a.region}): ${a.forecast}`)
    .join('\n');

  const hotspots = (ctx.hotspots as Array<Record<string, unknown>> ?? [])
    .map(h =>
      `- ${h.name}: ${h.taxi_count} taxis now → ${h.predicted_count} in 30min (${h.sdi_label})`
    )
    .join('\n');

  const timeline = (ctx.nowcast_timeline as Array<Record<string, string>> ?? [])
    .map(t => `- ${t.time}: ${t.label}`)
    .join('\n');

  const forecast24h = (ctx.forecast_24h as Array<Record<string, unknown>> ?? [])
    .map(p => `- ${p.time_text}: ${p.dominant_forecast}`)
    .join('\n');

  const forecastNote = ctx.sufficient_forecast
    ? '30-min predictions are from a trained model.'
    : '30-min predictions use current counts (insufficient history for model training).';

  return `You are a Singapore taxi and weather assistant. Answer concisely using ONLY the data below.
Current time: ${ctx.generated_at}. Total taxis online: ${ctx.total_taxis}.
${forecastNote}

WEATHER (current ${ctx.valid_period_text}):
${areas || 'No weather data available.'}

TAXI DEMAND ZONES (current → predicted in 30 min):
${hotspots || 'No zone data available.'}

2-HOUR NOWCAST:
${timeline || 'No nowcast data.'}

24-HOUR FORECAST:
${forecast24h || 'No 24-hour forecast data.'}

Rules:
- Weather questions: match the place name to the nearest area in the WEATHER list.
- "now" = current data. "in 30 min" = use predicted counts and nowcast trend.
- "1 hour" or "2 hours" = use nowcast trend and 24-hour forecast for the relevant region.
- "tonight" = use 24-hour forecast.
- Taxi questions for areas not listed as a zone: use the nearest zone and same-region context.
- Answer in 2-3 sentences max. State uncertainty clearly. No emojis.`;
}

export type OfflineReason = 'not_running' | 'no_model' | 'cors' | null;

async function detectModel(): Promise<{ model: string | null; reason: OfflineReason }> {
  try {
    const res = await fetch(`${LM_BASE}/v1/models`);
    if (!res.ok) return { model: null, reason: 'not_running' };
    const data = await res.json();
    const id: string | undefined = data.data?.[0]?.id;
    return id ? { model: id, reason: null } : { model: null, reason: 'no_model' };
  } catch {
    return { model: null, reason: 'cors' };
  }
}

export function useChatLLM() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [offlineReason, setOfflineReason] = useState<OfflineReason>(null);

  async function sendMessage(question: string) {
    const userMsg: ChatMessage = { role: 'user', content: question };
    const prevMessages = messages;
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    // Detect model first — also verifies LMStudio is reachable and CORS is enabled
    const { model, reason } = await detectModel();
    if (!model) {
      setOfflineReason(reason);
      const hint =
        reason === 'no_model'   ? 'LMStudio is running but no model is loaded. Load a model in LMStudio and try again.' :
        reason === 'cors'       ? 'LMStudio is running but CORS is blocked. In LMStudio go to Developer → Local Server and enable "Allow CORS from any origin".' :
                                  'LMStudio is not running on port 1234. Start LMStudio and load a model.';
      setMessages(prev => [...prev, { role: 'assistant', content: hint }]);
      setLoading(false);
      return;
    }

    let ctx: Record<string, unknown> = {};
    try {
      const ctxRes = await fetch(`/data/chat_context.json?t=${Date.now()}`);
      if (ctxRes.ok) ctx = await ctxRes.json();
    } catch { /* use empty context */ }

    const systemPrompt = buildSystemPrompt(ctx);

    try {
      const res = await fetch(`${LM_BASE}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model,
          messages: [
            { role: 'system', content: systemPrompt },
            ...prevMessages,
            userMsg,
          ],
          temperature: 0.5,
          max_tokens: 200,
          stream: false,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const reply: string = data.choices?.[0]?.message?.content?.trim() ?? '(no response)';
      setMessages(prev => [...prev, { role: 'assistant', content: reply }]);
      setOfflineReason(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${msg}` }]);
    } finally {
      setLoading(false);
    }
  }

  return {
    messages,
    loading,
    offline: offlineReason !== null,
    offlineReason,
    sendMessage,
    clearHistory: () => { setMessages([]); setOfflineReason(null); },
  };
}
