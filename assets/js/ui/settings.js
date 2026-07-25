import { el } from "./elements.js";
import { state } from "../state.js";
export function effectiveContextSize() { return el.contextMode.value === "auto" && state.detectedContextTokens ? state.detectedContextTokens : Number(el.context.value || state.detectedContextTokens || 4096); }
export function updateSettingRanges() {
  const context = effectiveContextSize(); el.temperatureValue.textContent = `${Number(el.temperature.value || 0).toFixed(1)} / 2`;
  el.contextValue.textContent = `${context.toLocaleString()} tokens${el.contextMode.value === "auto" ? " auto" : ""}`; el.context.disabled = el.contextMode.value === "auto";
  el.contextMaxLabel.textContent = state.detectedContextTokens ? `max ${state.detectedContextTokens.toLocaleString()}` : "max unknown";
  el.contextHelp.textContent = el.contextMode.value === "auto" ? "Auto uses the selected model's detected context window." : "Manual sets how much prior text the model can consider.";
}
export function applyDetectedContext(tokens) { state.detectedContextTokens = tokens; if (tokens) { el.context.max = String(tokens); if (Number(el.context.value) > tokens) el.context.value = String(tokens); } else el.context.removeAttribute("max"); updateSettingRanges(); }
