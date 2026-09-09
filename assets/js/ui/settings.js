import { el } from "./elements.js";
import { state } from "../state.js";
export function effectiveContextSize() { return el.contextMode.value === "auto" && state.detectedContextTokens ? state.detectedContextTokens : Number(el.context.value || state.detectedContextTokens || 4096); }
export function updateSettingRanges() {
  const context = effectiveContextSize(); el.temperatureValue.textContent = `${Number(el.temperature.value || 0).toFixed(1)} / 2`;
  el.contextValue.textContent = `${context.toLocaleString()} tokens${el.contextMode.value === "auto" ? " auto" : ""}`; el.context.disabled = el.contextMode.value === "auto";
  el.contextMaxLabel.textContent = state.modelContextTokens ? `model max ${state.modelContextTokens.toLocaleString()}` : "max unknown";
  el.contextHelp.textContent = el.contextMode.value === "auto"
    ? state.contextSource === "hardware" ? "Auto uses a conservative hardware-based recommendation." : "Auto uses the selected model's maximum context window."
    : "Manual sets how much prior text the model can consider.";
}
export function applyDetectedContext(tokens, modelMax = tokens, source = "model") { state.detectedContextTokens = tokens; state.modelContextTokens = modelMax; state.contextSource = source; if (modelMax) { el.context.max = String(modelMax); if (Number(el.context.value) > modelMax) el.context.value = String(modelMax); } else el.context.removeAttribute("max"); updateSettingRanges(); }
