import { el } from "./elements.js";
import { state } from "../state.js";
import { renderMarkdown, renderMath } from "./markdown.js";
export function renderMessages() {
  el.chat.innerHTML = "";
  if (!state.messages.length) { el.chat.append(el.emptyState); return; }
  state.messages.forEach((message) => {
    const node = document.createElement("article"), meta = document.createElement("span"), content = document.createElement("div");
    node.className = `message ${message.role}`; meta.className = "meta"; meta.textContent = message.role === "user" ? "You" : "Ollama";
    content.className = "message-content"; content.innerHTML = renderMarkdown(message.displayContent || message.content); node.append(meta, content); el.chat.append(node); renderMath(content);
  });
  el.chat.scrollTop = el.chat.scrollHeight;
}
