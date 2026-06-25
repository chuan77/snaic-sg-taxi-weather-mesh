import { useState } from 'react';
import type { ChatMessage } from '../types';
import type { PatternData, AreaPrediction } from './usePattern';

// LLM requests use the Vite proxy (/llm/* → Docker Model Runner).
// Proxy target is configured via LLM_PROXY_TARGET in vite.config.ts (server-side env var).

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
    .map(p => {
      const label = (p.dominant_forecast as string) ||
        (p.dominant_intensity as string)?.replace(/_/g, ' ') || 'drizzle';
      const r = p.regions as Record<string, string> | undefined;
      const reg = r ? ` (C:${r.central} E:${r.east} N:${r.north} S:${r.south} W:${r.west})` : '';
      return `- ${p.time_text}: ${label}${reg}`;
    })
    .join('\n');

  const forecastNote = ctx.sufficient_forecast
    ? '30-min predictions are from a trained model.'
    : '30-min predictions use current counts (insufficient history for model training).';

  const planningAreas = (ctx.planning_areas as Array<{name: string; region: string; count: number}> ?? [])
    .map(a => `- ${a.name} (${a.region}): ${a.count} taxis now`)
    .join('\n');

  const areaPredictions = (ctx.planning_area_predictions as AreaPrediction[] ?? [])
    .map(a => `- ${a.area}: now=${a.now}, +30min=${a.in_30min}, +1h=${a.in_1h}, +2h=${a.in_2h}`)
    .join('\n');

  const rainfallActive = Boolean(ctx.rainfall_active);
  const rainfallText = rainfallActive
    ? (ctx.rainfall_stations as Array<{name: string; rainfall_mm: number}> ?? [])
        .map(s => `- ${s.name}: ${s.rainfall_mm} mm`)
        .join('\n') || 'Rain detected but no station details.'
    : 'No active rainfall detected.';

  const lowHours = ctx.low_availability_hours as Record<string, number[]> ?? {};
  const lowHoursText = Object.entries(lowHours)
    .filter(([, hours]) => hours.length > 0)
    .map(([area, hours]) => `- ${area}: typically low at hours ${hours.join(', ')}`)
    .join('\n');

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

PLANNING AREAS (current taxi counts — all 55 areas):
${planningAreas || 'No planning area data.'}

PLANNING AREA PREDICTIONS (now / +30min / +1h / +2h):
${areaPredictions || 'No predictions available (insufficient history).'}

RAINFALL (current):
${rainfallText}

HISTORICAL LOW-AVAILABILITY PATTERNS (hours of day, 0-23):
${lowHoursText || 'No pattern data available yet.'}

Rules:
- Weather questions: match the place name to the nearest area in the WEATHER list.
- "now" = current data. "in 30 min" = use predicted counts and nowcast trend.
- "1 hour" or "2 hours" = use nowcast trend and 24-hour forecast for the relevant region.
- "tonight" = use 24-hour forecast.
- Taxi questions for areas not listed as a zone: use the nearest zone and same-region context.
- Area questions ("taxis in Bedok", "Punggol now"): search PLANNING AREAS and PLANNING AREA PREDICTIONS first. Only fall back to TAXI DEMAND ZONES if the area is not found.
- Time-horizon questions ("in 1 hour", "in 2 hours"): use in_1h / in_2h from PLANNING AREA PREDICTIONS.
- Rain questions ("during rain", "when raining"): reference RAINFALL section; if rainfall_active, name which areas are wet.
- Pattern questions ("usually", "typically", "at 8am"): use HISTORICAL LOW-AVAILABILITY PATTERNS.
- Think briefly. Answer in 2-3 sentences max. State uncertainty clearly. No emojis.`;
}

export type OfflineReason = 'not_running' | 'no_model' | 'cors' | null;

async function detectModel(): Promise<{ model: string | null; reason: OfflineReason }> {
  try {
    const res = await fetch('/llm/models');
    if (!res.ok) return { model: null, reason: 'not_running' };
    const data = await res.json();
    const id: string | undefined = data.data?.[0]?.id;
    return id ? { model: id, reason: null } : { model: null, reason: 'no_model' };
  } catch {
    return { model: null, reason: 'cors' };
  }
}

export function useChatLLM(patternData?: PatternData) {
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
        reason === 'no_model' ? 'Docker Model Runner is running but no model is loaded. Pull the model: docker model pull ai/gemma4:E4B' :
        reason === 'cors'     ? 'Cannot reach Docker Model Runner. Ensure Docker Desktop is running and the model is pulled: docker model pull ai/gemma4:E4B' :
                                'Docker Model Runner is not reachable. Start Docker Desktop and ensure the model runner is enabled.';
      setMessages(prev => [...prev, { role: 'assistant', content: hint }]);
      setLoading(false);
      return;
    }

    let chatCtx: Record<string, unknown> = {};
    try {
      const ctxRes = await fetch(`/data/chat_context.json?t=${Date.now()}`);
      if (ctxRes.ok) chatCtx = await ctxRes.json();
    } catch { /* use empty context */ }

    const ctx: Record<string, unknown> = {
      ...chatCtx,
      planning_area_predictions: patternData?.predictions ?? [],
      low_availability_hours: patternData?.low_availability_hours ?? {},
    };

    const systemPrompt = buildSystemPrompt(ctx);

    try {
      const res = await fetch('/llm/chat/completions', {
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
          max_tokens: 2048,
          stream: false,
        }),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}${body ? ' — ' + body.slice(0, 200) : ''}`);
      }
      const data = await res.json();
      const raw = data.choices?.[0]?.message;
      const reply: string =
        raw?.content?.trim() ||
        (raw?.reasoning_content as string | undefined)?.split('\n').slice(-3).join(' ').trim() ||
        '(no response)';
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
