import { get, post } from "../api/client.js";
import { el } from "../ui/elements.js";
import { setBusy, setModelRuntime, setStatus } from "../ui/status.js";
import { applyDetectedContext } from "../ui/settings.js";
export async function fetchRunningModelNames() { try { return (await get("/api/ps")).models?.map((model) => model.name).filter(Boolean) || []; } catch { return []; } }
export async function loadRunningModels() { if (!el.model.value) return setModelRuntime("", "No model selected"); const names = await fetchRunningModelNames(); setModelRuntime(names.includes(el.model.value) ? "ok" : "", names.includes(el.model.value) ? "Selected model is active" : "Selected model is idle"); }
export async function loadModels() { setStatus("", "Checking server..."); const previous = el.model.value; el.model.innerHTML = ""; try { const [tags, runningNames] = await Promise.all([get("/api/tags"), fetchRunningModelNames()]); const running = new Set(runningNames), names = (tags.models || []).map((model) => model.name).sort((a, b) => Number(running.has(b)) - Number(running.has(a)) || a.localeCompare(b)); if (!names.length) { setStatus("bad", "No models found"); el.activeModel.textContent = "Pull a model with ollama pull"; return; } names.forEach((name) => el.model.add(new Option(running.has(name) ? `${name} (active)` : name, name))); el.model.value = names.includes(previous) ? previous : runningNames.find((name) => names.includes(name)) || names[0]; el.activeModel.textContent = el.model.value; setStatus("ok", "Connected"); await Promise.all([loadRunningModels(), loadModelContext()]); } catch { setStatus("bad", "Ollama unavailable"); el.activeModel.textContent = "Cannot reach Ollama"; setModelRuntime("bad", "Runtime unavailable"); } finally { setBusy(false); } }
export async function loadModelContext() { if (!el.model.value) return applyDetectedContext(null); try { applyDetectedContext(extractContextTokens(await (await post("/api/show", { model: el.model.value })).json())); } catch { applyDetectedContext(null); } }
export function extractContextTokens(data) {
  const isContextLimitKey = (key) => {
    const normalized = key.toLowerCase();
    return normalized === "num_ctx" || normalized === "context_length" || normalized.endsWith(".context_length");
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
