import { get, post, fetchWithRetry } from "../api/client.js";
import { el } from "../ui/elements.js";
import { setBusy, setModelRuntime, setStatus } from "../ui/status.js";
import { applyDetectedContext } from "../ui/settings.js";

const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes (PE-001)

const cache = {
  tags: { data: null, timestamp: 0 },
  context: new Map(), // modelName -> { recommended, modelMax, source, timestamp }
};

/**
 * Invalidate all cached model tags and context metadata.
 */
export function invalidateModelCaches() {
  cache.tags = { data: null, timestamp: 0 };
  cache.context.clear();
}

/**
 * Fetch names of currently loaded/running models in Ollama memory.
 */
export async function fetchRunningModelNames() {
  const response = await fetchWithRetry("/api/ps");
  if (!response) return [];
  
  try {
    const data = await response.json();
    return data.models?.map((model) => model.name).filter(Boolean) || [];
  } catch {
    return [];
  }
}

/**
 * Update UI indicating whether the selected model is currently in memory.
 * FG-004: Uses retry wrapper with offline detection.
 */
export async function loadRunningModels() {
  if (!el.model.value) {
    setModelRuntime("", "No model selected");
    return;
  }

  // FG-004: Offline detection
  window.addEventListener("offline", () => setStatus("warning", "Network disconnected"), { once: true });

  const names = await fetchRunningModelNames();
  setModelRuntime(
    names.includes(el.model.value) ? "ok" : "",
    names.includes(el.model.value) ? "Selected model is active" : "Selected model is idle"
  );
}

/**
 * Load available Ollama models, using cached list if within TTL unless forceRefresh is true.
 * FG-004: Uses retry wrapper for network requests with offline detection.
 *
 * @param {boolean} forceRefresh - If true, bypasses in-memory cache.
 */
export async function loadModels(forceRefresh = false) {
  // FG-004: Offline detection
  window.addEventListener("offline", () => setStatus("warning", "Network disconnected"), { once: true });

  setStatus("", "Checking server...");
  const previous = el.model.value;
  el.model.innerHTML = "";

  if (forceRefresh) {
    invalidateModelCaches();
  }

  try {
    const now = Date.now();
    let tags = null;

    if (!forceRefresh && cache.tags.data && now - cache.tags.timestamp < CACHE_TTL_MS) {
      tags = cache.tags.data;
    } else {
      const response = await fetchWithRetry("/api/tags");
      if (!response) throw new Error("Failed to fetch models");
      
      tags = await response.json();
      cache.tags = { data: tags, timestamp: now };
    }

    const runningNames = await fetchRunningModelNames();
    const running = new Set(runningNames);
    const names = (tags.models || [])
      .map((model) => model.name)
      .sort((a, b) => Number(running.has(b)) - Number(running.has(a)) || a.localeCompare(b));

    if (!names.length) {
      setStatus("bad", "No models found");
      el.activeModel.textContent = "Pull a model with ollama pull";
      return;
    }

    names.forEach((name) =>
      el.model.add(new Option(running.has(name) ? `${name} (active)` : name, name))
    );

    el.model.value = names.includes(previous)
      ? previous
      : runningNames.find((name) => names.includes(name)) || names[0];
    el.activeModel.textContent = el.model.value;
    setStatus("ok", "Connected");

    await Promise.all([loadRunningModels(), loadModelContext()]);
  } catch (error) {
    console.error("Failed to load models:", error);
    // FG-004: Offline detection already handled with online/offline events and retry wrapper
    setStatus("bad", "Ollama unavailable");
    el.activeModel.textContent = "Cannot reach Ollama";
    setModelRuntime("bad", "Runtime unavailable");
  } finally {
    setBusy(false);
  }
}

/**
 * Load and apply context window limits and hardware recommendations for the selected model.
 * Uses cached result if within TTL (PE-001).
 * FG-004: Uses retry wrapper for network requests.
 *
 * @param {boolean} forceRefresh - If true, bypasses context recommendation cache.
 */
export async function loadModelContext(forceRefresh = false) {
  const model = el.model.value;
  if (!model) return applyDetectedContext(null, null);

  const now = Date.now();
  if (!forceRefresh && cache.context.has(model)) {
    const cached = cache.context.get(model);
    if (now - cached.timestamp < CACHE_TTL_MS) {
      applyDetectedContext(cached.recommended, cached.modelMax, cached.source);
      return;
    }
  }

  try {
    const response = await fetchWithRetry("/api/context-recommendation", {
      body: JSON.stringify({ model }),
      headers: { "Content-Type": "application/json" },
    });

    if (!response) throw new Error("Network error");
    
    const data = await response.json();
    cache.context.set(model, {
      recommended: data.recommendedContext,
      modelMax: data.modelContext,
      source: data.source,
      timestamp: now,
    });
    applyDetectedContext(data.recommendedContext, data.modelContext, data.source);
  } catch (error) {
    // Try fallback to /api/show for context extraction
    try {
      const response = await fetchWithRetry("/api/show", {
        body: JSON.stringify({ model }),
        headers: { "Content-Type": "application/json" },
      });

      if (!response) throw new Error("Network error");
      
      const data = await response.json();
      const context = extractContextTokens(data);
      cache.context.set(model, {
        recommended: context,
        modelMax: context,
        source: "model",
        timestamp: now,
      });
      applyDetectedContext(context, context, "model");
    } catch (fallbackError) {
      console.error("Failed to load context:", fallbackError);
      applyDetectedContext(null, null);
    }
  }
}

/**
 * Extract context window length from Ollama model metadata or modelfile parameters.
 */
export function extractContextTokens(data) {
  if (!data) return null;

  const isContextLimitKey = (key) => {
    const normalized = key.toLowerCase();
    return (
      normalized === "num_ctx" ||
      normalized === "context_length" ||
      normalized.endsWith(".context_length")
    );
  };

  const search = (value) => {
    if (!value || typeof value !== "object") return null;
    for (const [key, item] of Object.entries(value)) {
      if (isContextLimitKey(key)) {
        const number = Number(item);
        if (Number.isFinite(number) && number >= 512) return Math.floor(number);
      }
      const nested = search(item);
      if (nested) return nested;
    }
    return null;
  };

  const metadata = search(data.model_info) || search(data.details) || search(data);
  if (metadata) return metadata;

  const text = [data.parameters, data.modelfile].join("\n");
  const match = text.match(/\b(?:num_ctx|context_length|context\s+length)\b\s*(?:=|:)?\s*(\d+)/i);
  return match && Number(match[1]) >= 512 ? Number(match[1]) : null;
}
