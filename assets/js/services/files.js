import { post } from "../api/client.js";
import { state, allowedExtensions, officeExtensions } from "../state.js";
import { el } from "../ui/elements.js";
import { formatBytes, formatLargeBytes, getExtension } from "../utils/format.js";

/**
 * Render the current list of staged file attachments in the composer.
 */
export function renderAttachments() {
  el.attachments.innerHTML = "";
  state.attachments.forEach((attachment) => {
    const row = document.createElement("div");
    const details = document.createElement("div");
    const name = document.createElement("strong");
    const meta = document.createElement("span");
    const remove = document.createElement("button");

    row.className = "attachment";
    name.textContent = attachment.name;
    meta.textContent = `${formatBytes(attachment.size)} text`;
    details.append(name, meta);

    remove.className = "icon-button";
    remove.type = "button";
    remove.textContent = "x";
    remove.onclick = () => {
      state.attachments = state.attachments.filter((item) => item.id !== attachment.id);
      renderAttachments();
    };

    row.append(details, remove);
    el.attachments.append(row);
  });

  el.attachmentNote.textContent = state.attachments.length
    ? `${state.attachments.length} file${state.attachments.length === 1 ? "" : "s"} will be sent with your next message.`
    : "";
}

/**
 * Convert a File object to a base64 encoded string.
 *
 * @param {File} file - Browser File object.
 * @returns {Promise<string>} Base64 data string.
 */
const base64 = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",").pop());
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });

/**
 * Extract plain text content from a file (reading directly for text or calling backend for Office docs).
 *
 * @param {File} file - Browser File object.
 * @param {string} extension - File extension.
 * @returns {Promise<string>} Extracted text.
 */
async function textFromFile(file, extension) {
  if (!officeExtensions.has(extension)) {
    return file.text();
  }
  const response = await post("/api/extract", {
    filename: file.name,
    contentBase64: await base64(file),
  });
  const data = await response.json();
  return data.content || "";
}

/**
 * Validate and add files to active prompt attachments.
 *
 * @param {File[]} files - List of selected files from file input or drag-and-drop.
 */
export async function addFiles(files) {
  const notes = [];
  for (const file of files) {
    const extension = getExtension(file.name);
    if (!allowedExtensions.has(extension)) {
      notes.push(`${file.name}: unsupported type`);
      continue;
    }
    if (file.size > state.maxFileBytes) {
      notes.push(`${file.name}: larger than ${formatLargeBytes(state.maxFileBytes)}`);
      continue;
    }
    try {
      state.attachments.push({
        id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
        name: file.name,
        extension,
        size: file.size,
        content: await textFromFile(file, extension),
      });
    } catch {
      notes.push(`${file.name}: could not read file`);
    }
  }
  el.fileInput.value = "";
  renderAttachments();
  if (notes.length) {
    el.attachmentNote.textContent = notes.join("; ");
  }
}

/**
 * Build the prompt payload sent to LLM, embedding file text as Markdown code blocks.
 *
 * @param {string} prompt - Raw prompt string typed by the user.
 * @returns {string} Augmented message content.
 */
export function buildMessageContent(prompt) {
  if (!state.attachments.length) return prompt;
  const files = state.attachments
    .map(
      (file) =>
        `File: ${file.name}\nType: ${file.extension || "text"}\n\n\`\`\`\n${file.content}\n\`\`\``
    )
    .join("\n\n");
  return `Use the following uploaded file contents as context.\n\n${files}\n\nUser request:\n${
    prompt || "Please analyze the uploaded file contents."
  }`;
}

/**
 * Build the message content for UI display, showing human-readable attachment list.
 *
 * @param {string} prompt - Raw prompt string.
 * @returns {string} Formatted display text.
 */
export function buildDisplayContent(prompt) {
  return state.attachments.length
    ? `${prompt || "Please analyze the uploaded file contents."}\n\nAttached files:\n${state.attachments
        .map((file) => `- ${file.name} (${formatBytes(file.size)})`)
        .join("\n")}`
    : prompt;
}
