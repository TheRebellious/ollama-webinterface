import { el } from "./elements.js";
import { state } from "../state.js";

/**
 * Determine effective context token count based on active mode ('auto' vs 'manual').
 *
 * @returns {number} Effective context tokens to pass in num_ctx.
 */
export function effectiveContextSize() {
  return el.contextMode.value === "auto" && state.detectedContextTokens
    ? state.detectedContextTokens
    : Number(el.context.value || state.detectedContextTokens || 4096);
}

/**
 * Update settings UI range labels, descriptions, and enable/disable states.
 */
export function updateSettingRanges() {
  const context = effectiveContextSize();
  el.temperatureValue.textContent = `${Number(el.temperature.value || 0).toFixed(1)} / 2`;
  el.contextValue.textContent = `${context.toLocaleString()} tokens${
    el.contextMode.value === "auto" ? " auto" : ""
  }`;
  el.context.disabled = el.contextMode.value === "auto";
  el.contextMaxLabel.textContent = state.modelContextTokens
    ? `model max ${state.modelContextTokens.toLocaleString()}`
    : "max unknown";
  el.contextHelp.textContent =
    el.contextMode.value === "auto"
      ? state.contextSource === "hardware"
        ? "Auto uses a conservative hardware-based recommendation."
        : "Auto uses the selected model's maximum context window."
      : "Manual sets how much prior text the model can consider.";
}

/**
 * Apply detected context tokens and maximum limit for the selected model to settings sliders.
 *
 * @param {number|null} tokens - Recommended or detected context tokens.
 * @param {number|null} [modelMax] - Absolute model maximum context length.
 * @param {string} [source="model"] - Source of context recommendation ('hardware' or 'model').
 */
export function applyDetectedContext(tokens, modelMax = tokens, source = "model") {
  state.detectedContextTokens = tokens;
  state.modelContextTokens = modelMax;
  state.contextSource = source;
  if (modelMax) {
    el.context.max = String(modelMax);
    if (Number(el.context.value) > modelMax) {
      el.context.value = String(modelMax);
    }
  } else {
    el.context.removeAttribute("max");
  }
  updateSettingRanges();
}

/**
 * Persist current settings values to localStorage under the preferences storage key.
 */
export function savePreferences() {
  const prefs = {
    temperature: el.temperature.value,
    contextMode: el.contextMode.value,
    context: el.context.value,
    systemPrompt: el.systemPrompt.value,
  };
  try {
    localStorage.setItem(
      "ollama-console-preferences",
      JSON.stringify(prefs)
    );
  } catch (e) {
    console.warn("Could not persist preferences:", e);
  }
}

/**
 * Load persisted preferences from localStorage and apply to settings UI.
 * Returns boolean indicating whether preferences were loaded.
 *
 * @returns {boolean} Whether preferences were successfully loaded.
 */
export function loadPreferences() {
  try {
    const stored = localStorage.getItem("ollama-console-preferences");
    if (!stored) {
      return false;
    }
    const prefs = JSON.parse(stored);
    if (prefs.temperature) {
      el.temperature.value = String(prefs.temperature);
    }
    if (prefs.contextMode) {
      el.contextMode.value = prefs.contextMode;
    }
    if (prefs.context) {
      el.context.value = String(prefs.context);
    }
    if (prefs.systemPrompt) {
      el.systemPrompt.value = prefs.systemPrompt;
    }
    updateSettingRanges();
    return true;
  } catch (e) {
    console.warn("Could not load preferences:", e);
    return false;
  }
}
