import { post, postWithRetry } from "../api/client.js";
import { state } from "../state.js";
import { el } from "../ui/elements.js";
import { setBusy, setStatus } from "../ui/status.js";
import { effectiveContextSize } from "../ui/settings.js";
import { renderAttachments, buildDisplayContent, buildMessageContent } from "./files.js";
import { renderMessages } from "../ui/chat.js";
import { saveCurrentConversation } from "../ui/conversations.js";
import { loadRunningModels } from "./models.js";

/**
 * Sends a chat prompt to Ollama with streaming response, concurrency locking,
 * and robust reader cleanup (CR-002, CR-005, PE-003).
 */
export async function sendPrompt() {
  const prompt = el.prompt.value.trim();
  // Concurrency guard: prevent multiple parallel sends to the same conversation (CR-005)
  if ((!prompt && !state.attachments.length) || state.busy || !el.model.value) {
    return;
  }

  setBusy(true);

  // FG-004: Offline detection - show status on network errors
  window.addEventListener("offline", () => setStatus("warning", "Network disconnected"), { once: true });

  // Push user message
  const userDisplay = buildDisplayContent(prompt);
  state.messages.push({
    id: `${Date.now()}-user`,
    role: "user",
    content: buildMessageContent(prompt),
    displayContent: userDisplay,
  });

  // Clear input and attachments
  el.prompt.value = "";
  state.attachments = [];
  renderAttachments();
  renderMessages();
  saveCurrentConversation();

  // Prepare full message history for upstream
  const messages = el.systemPrompt.value.trim()
    ? [
        { role: "system", content: el.systemPrompt.value.trim() },
        ...state.messages.map(({ role, content }) => ({ role, content })),
      ]
    : state.messages.map(({ role, content }) => ({ role, content }));

  // Create assistant placeholder message
  const assistant = { id: `${Date.now()}-assistant`, role: "assistant", content: "" };
  state.messages.push(assistant);

  let reader = null;
  try {
    // FG-004: Use retry wrapper for chat requests
    const response = await postWithRetry("/api/chat", {
      model: el.model.value,
      messages,
      stream: true,
      options: {
        temperature: Number(el.temperature.value || 0.7),
        num_ctx: effectiveContextSize(),
      },
    });

    if (!response) {
      assistant.content = assistant.content
        ? `${assistant.content}\n\n[Generation interrupted: Network unavailable after retries]`
        : "Network unavailable - request failed after retries";
      renderMessages();
      saveCurrentConversation();
      setBusy(false);
      return;
    }

    if (!response.body) {
      throw new Error("No response body received from server");
    }

    reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      // Keep unfinished fragment in buffer
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
          const part = JSON.parse(trimmed);
          if (part.message?.content) {
            assistant.content += part.message.content;
          }
        } catch {
          // Ignore malformed partial chunks without crashing stream
        }
      }

      renderMessages();
      saveCurrentConversation();
    }

    // Process any remaining bytes in buffer
    if (buffer.trim()) {
      try {
        const part = JSON.parse(buffer.trim());
        if (part.message?.content) {
          assistant.content += part.message.content;
        }
      } catch {
        // Ignore malformed trailing chunk
      }
    }
    renderMessages();
    saveCurrentConversation();

  } catch (error) {
    console.error("Chat generation failed:", error);
    assistant.content = assistant.content
      ? `${assistant.content}\n\n[Generation interrupted: ${error.message || error}]`
      : `Request failed: ${error.message || error}`;
    renderMessages();
    saveCurrentConversation();
  } finally {
    if (reader) {
      try {
        reader.releaseLock();
      } catch {
        // Reader already released
      }
    }
    setBusy(false);
    loadRunningModels();
  }
}
