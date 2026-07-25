    function escapeHtml(value) {
      return value.replace(/[&<>"']/g, (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#039;"
      }[character]));
    }

    function renderInlineMarkdown(value) {
      const math = [];
      const protectedValue = protectInlineMath(normalizeMarkdownSource(value), math);
      return restoreInlineMath(escapeHtml(protectedValue)
        .replace(/&lt;br\s*\/?&gt;/gi, "<br>")
        .replace(/!\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g, '<img src="$2" alt="$1" loading="lazy">')
        .replace(/!\[([^\]]*)\]\[([^\]]+)\]/g, (match, alt, id) => {
          const url = markdownReferences[id.toLowerCase()];
          return url ? `<img src="${url}" alt="${alt}" loading="lazy">` : match;
        })
        .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
        .replace(/\[([^\]]+)\]\[([^\]]+)\]/g, (match, text, id) => {
          const url = markdownReferences[id.toLowerCase()];
          return url ? `<a href="${url}" target="_blank" rel="noreferrer">${text}</a>` : match;
        })
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/__([^_]+)__/g, "<strong>$1</strong>")
        .replace(/\*([^*]+)\*/g, "<em>$1</em>")
        .replace(/_([^_]+)_/g, "<em>$1</em>"), math);
    }

    const markdownReferences = {};

    export function renderMarkdown(markdown) {
      const source = String(markdown || "").replace(/\r\n/g, "\n");
      const referencePattern = /^\s*\[([^\]]+)\]:\s*(https?:\/\/\S+)\s*$/gm;
      for (const key of Object.keys(markdownReferences)) delete markdownReferences[key];

      let referenceMatch;
      while ((referenceMatch = referencePattern.exec(source)) !== null) {
        markdownReferences[referenceMatch[1].toLowerCase()] = escapeHtml(referenceMatch[2]);
      }

      const cleaned = source.replace(referencePattern, "");
      const parts = cleaned.split(/```/);
      return parts.map((part, index) => {
        if (index % 2 === 1) {
          const lines = part.replace(/^\n/, "").split("\n");
          const language = (lines[0] || "").trim();
          const hasLanguage = /^[A-Za-z0-9_+#.-]+$/.test(language);
          const code = hasLanguage ? lines.slice(1).join("\n") : part;
          const className = hasLanguage ? ` class="language-${escapeHtml(language)}"` : "";
          const label = hasLanguage ? `<span class="code-language">${escapeHtml(language)}</span>` : "";
          return `<pre>${label}<code${className}>${highlightCode(code.trim(), language)}</code></pre>`;
        }

        const lines = normalizeMarkdownSource(part).split("\n");
        const blocks = [];
        let list = null;
        let paragraph = [];

        function flushList() {
          if (list && list.items.length) {
            const tag = list.type === "ol" ? "ol" : "ul";
            blocks.push(`<${tag}>${list.items.join("")}</${tag}>`);
            list = null;
          }
        }

        function flushParagraph() {
          if (paragraph.length) {
            blocks.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
            paragraph = [];
          }
        }

        for (let index = 0; index < lines.length; index += 1) {
          const line = lines[index];
          const trimmed = line.trim();
          if (!trimmed) {
            flushList();
            flushParagraph();
            continue;
          }

          if (isHorizontalRule(trimmed)) {
            flushList();
            flushParagraph();
            blocks.push("<hr>");
            continue;
          }

          if (isDisplayMathStart(trimmed)) {
            flushList();
            flushParagraph();
            const math = collectDisplayMath(lines, index);
            index = math.endIndex;
            blocks.push(`<div class="math-display">\\[${escapeHtml(math.content)}\\]</div>`);
            continue;
          }

          if (isTableStart(lines, index)) {
            flushList();
            flushParagraph();
            const tableRows = [lines[index], lines[index + 1]];
            index += 2;
            while (index < lines.length && isTableRow(lines[index])) {
              tableRows.push(lines[index]);
              index += 1;
            }
            index -= 1;
            blocks.push(renderTable(tableRows));
            continue;
          }

          if (isEmptyPipeRow(trimmed)) {
            flushList();
            flushParagraph();
            continue;
          }

          if (isLoosePipeRow(trimmed)) {
            flushList();
            flushParagraph();
            const looseRows = [];
            while (index < lines.length && isLoosePipeRow(lines[index].trim())) {
              const cells = splitTableRow(lines[index]).filter((cell) => cell.trim());
              if (cells.length >= 2) looseRows.push(cells);
              index += 1;
            }
            index -= 1;
            if (looseRows.length) blocks.push(renderLooseRows(looseRows));
            continue;
          }

          const quote = trimmed.match(/^>\s?(.*)$/);
          if (quote) {
            flushList();
            flushParagraph();
            const quoteLines = [quote[1]];
            while (index + 1 < lines.length) {
              const next = lines[index + 1].trim().match(/^>\s?(.*)$/);
              if (!next) break;
              quoteLines.push(next[1]);
              index += 1;
            }
            blocks.push(`<blockquote>${renderQuoteLines(quoteLines)}</blockquote>`);
            continue;
          }

          const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
          if (heading) {
            flushList();
            flushParagraph();
            const level = heading[1].length;
            blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
            continue;
          }

          const task = trimmed.match(/^[-*]\s+\[([ xX])\]\s+(.+)$/);
          if (task) {
            flushParagraph();
            if (!list || list.type !== "ul") {
              flushList();
              list = { type: "ul", items: [] };
            }
            const checked = task[1].toLowerCase() === "x" ? " checked" : "";
            list.items.push(`<li class="task-item"><input type="checkbox" disabled${checked}> ${renderInlineMarkdown(task[2])}</li>`);
            continue;
          }

          const unordered = trimmed.match(/^[-*]\s+(.+)$/);
          if (unordered) {
            flushParagraph();
            if (!list || list.type !== "ul") {
              flushList();
              list = { type: "ul", items: [] };
            }
            list.items.push(`<li>${renderInlineMarkdown(unordered[1])}</li>`);
            continue;
          }

          const ordered = trimmed.match(/^\d+[.)]\s+(.+)$/);
          if (ordered) {
            flushParagraph();
            if (!list || list.type !== "ol") {
              flushList();
              list = { type: "ol", items: [] };
            }
            list.items.push(`<li>${renderInlineMarkdown(ordered[1])}</li>`);
            continue;
          }

          flushList();
          paragraph.push(trimmed);
        }

        flushList();
        flushParagraph();
        return blocks.join("");
      }).join("");
    }

    function normalizeMarkdownSource(value) {
      return String(value || "")
        .replace(/\\\\\[/g, "\\[")
        .replace(/\\\\\]/g, "\\]")
        .replace(/\\\\\(/g, "\\(")
        .replace(/\\\\\)/g, "\\)");
    }

    function protectInlineMath(value, math) {
      return String(value || "")
        .replace(/\\\[([\s\S]+?)\\\]/g, (match, formula) => {
          return stashMath(math, formula);
        })
        .replace(/\\\(([\s\S]+?)\\\)/g, (match, formula) => {
          return stashMath(math, formula);
        })
        .replace(/(^|[^$])\$([^$\n]+?)\$(?!\$)/g, (match, prefix, formula) => {
          return `${prefix}${stashMath(math, formula)}`;
        });
    }

    function stashMath(math, formula) {
      const token = `@@MATH${math.length}@@`;
      math.push(`<span class="math-inline">\\(${escapeHtml(formula.trim())}\\)</span>`);
      return token;
    }

    function restoreInlineMath(value, math) {
      return math.reduce((result, formula, index) => {
        return result.replace(`@@MATH${index}@@`, formula);
      }, value);
    }

    export function renderMath(node) {
      if (window.MathJax && window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise([node]).catch(() => {});
      }
    }

    function highlightCode(code, language) {
      let highlighted = escapeHtml(code);
      const normalized = String(language || "").toLowerCase();
      if (["js", "javascript", "ts", "typescript", "python", "py", "json", "sh", "bash"].includes(normalized)) {
        highlighted = highlighted.replace(/\b(const|let|var|function|return|if|else|for|while|class|import|from|def|try|except|with|as|true|false|null|none|and|or|not|await|async)\b/g, '<span class="code-keyword">$1</span>');
        highlighted = highlighted.replace(/(&quot;.*?&quot;|'.*?')/g, '<span class="code-string">$1</span>');
        highlighted = highlighted.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="code-number">$1</span>');
      }
      return highlighted;
    }

    function renderQuoteLines(lines) {
      return lines
        .join("\n")
        .split(/\n\s*\n/)
        .map((paragraph) => `<p>${renderInlineMarkdown(paragraph.replace(/\n/g, " ").trim())}</p>`)
        .join("");
    }

    function isHorizontalRule(trimmed) {
      return /^([-*_])(?:\s*\1){2,}$/.test(trimmed);
    }

    function isDisplayMathStart(trimmed) {
      return trimmed === "$$" || trimmed.startsWith("$$") || trimmed === "\\[" || trimmed.startsWith("\\[");
    }

    function collectDisplayMath(lines, startIndex) {
      const start = lines[startIndex].trim();
      const isDollar = start.startsWith("$$");
      const close = isDollar ? "$$" : "\\]";
      const openingLength = isDollar ? 2 : 2;
      const chunks = [];
      let first = start.slice(openingLength).trim();

      if (first.endsWith(close) && first.length > close.length) {
        return {
          content: first.slice(0, -close.length).trim(),
          endIndex: startIndex
        };
      }

      if (first && first !== close) {
        chunks.push(first);
      }

      for (let index = startIndex + 1; index < lines.length; index += 1) {
        const line = lines[index];
        const trimmed = line.trim();
        if (trimmed.endsWith(close)) {
          const beforeClose = line.slice(0, line.lastIndexOf(close)).trim();
          if (beforeClose) chunks.push(beforeClose);
          return {
            content: chunks.join("\n"),
            endIndex: index
          };
        }
        chunks.push(line);
      }

      return {
        content: chunks.join("\n"),
        endIndex: lines.length - 1
      };
    }

    function isTableRow(line) {
      return /^\s*\|.+\|\s*$/.test(line);
    }

    function isEmptyPipeRow(trimmed) {
      return /^\|+\s*$/.test(trimmed);
    }

    function isLoosePipeRow(trimmed) {
      return isTableRow(trimmed) && !isEmptyPipeRow(trimmed);
    }

    function isTableStart(lines, index) {
      if (!isTableRow(lines[index] || "") || !isTableRow(lines[index + 1] || "")) return false;
      return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1]);
    }

    function renderTable(rows) {
      const headers = splitTableRow(rows[0]);
      const bodyRows = rows.slice(2).map(splitTableRow);
      const headerHtml = headers.map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`).join("");
      const bodyHtml = bodyRows.map((row) => {
        return `<tr>${row.map((cell) => `<td>${renderInlineMarkdown(cell)}</td>`).join("")}</tr>`;
      }).join("");
      return `<div class="table-wrap"><table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`;
    }

    function renderLooseRows(rows) {
      const rowHtml = rows.map((row) => {
        const label = row[0] || "";
        const detail = row.slice(1).join(" | ");
        return `<div class="loose-row"><div class="loose-label">${renderInlineMarkdown(label)}</div><div>${renderInlineMarkdown(detail)}</div></div>`;
      }).join("");
      return `<div class="loose-table">${rowHtml}</div>`;
    }

    function splitTableRow(row) {
      return row.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
    }

