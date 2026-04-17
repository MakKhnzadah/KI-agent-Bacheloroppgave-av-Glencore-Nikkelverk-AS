export function stripYamlFrontMatter(markdown: string): string {
  const raw = markdown || "";
  const text = raw.replace(/^\ufeff/, "").replace(/\r\n/g, "\n").replace(/^\s+/, "");
  if (!text.startsWith("---\n")) return text;
  const end = text.indexOf("\n---\n", 4);
  if (end === -1) return text;
  return text.slice(end + "\n---\n".length).replace(/^\n+/, "");
}

export function extractTitleFromDraft(markdown: string): string | null {
  const text = (markdown || "").replace(/^\ufeff/, "").replace(/\r\n/g, "\n");
  if (!text.startsWith("---\n")) return null;
  const end = text.indexOf("\n---\n", 4);
  if (end === -1) return null;

  const front = text.slice(4, end);
  for (const line of front.split("\n")) {
    const m = line.match(/^title\s*:\s*(.*)$/i);
    if (!m) continue;
    const raw = (m[1] || "").trim();
    if (!raw) return null;
    return raw.replace(/^"(.*)"$/, "$1").replace(/^'(.*)'$/, "$1").trim() || null;
  }
  return null;
}

export function applyTitleToDraft(markdown: string, nextTitle: string): string {
  const cleanTitle = (nextTitle || "").trim();
  if (!cleanTitle) return markdown;

  const text = (markdown || "").replace(/^\ufeff/, "").replace(/\r\n/g, "\n");
  const escaped = cleanTitle.replace(/"/g, '\\"');
  const yamlTitleLine = `title: "${escaped}"`;

  if (!text.startsWith("---\n")) {
    return `---\n${yamlTitleLine}\n---\n\n# ${cleanTitle}\n\n${text}`.trim();
  }

  const end = text.indexOf("\n---\n", 4);
  if (end === -1) return text;

  const front = text.slice(4, end);
  let body = text.slice(end + "\n---\n".length);

  const frontLines = front.split("\n");
  let replaced = false;
  const nextFront = frontLines.map((line) => {
    if (/^title\s*:/i.test(line)) {
      replaced = true;
      return yamlTitleLine;
    }
    return line;
  });

  if (!replaced) {
    nextFront.unshift(yamlTitleLine);
  }

  if (/^\s*#\s+.+$/m.test(body)) {
    body = body.replace(/^\s*#\s+.+$/m, `# ${cleanTitle}`);
  }

  return `---\n${nextFront.join("\n")}\n---\n${body}`;
}

export function looksLikeMarkdown(content: string): boolean {
  const raw = content || "";
  const text = raw.replace(/^\ufeff/, "").replace(/\r\n/g, "\n").trim();
  return (
    /^#{1,6}\s+\S/m.test(text) ||
    /^\s*([-*+]\s+\S|\d+\.\s+\S)/m.test(text) ||
    /^>\s+\S/m.test(text) ||
    /^```/m.test(text) ||
    /\|/.test(text)
  );
}

export function looksLikeGluedText(content: string): boolean {
  const text = (content || "").replace(/\r\n/g, "\n");
  const sample = text.replace(/\s+/g, " ").trim();
  if (sample.length < 400) return false;
  const words = sample.split(" ").filter(Boolean);
  if (words.length === 0) return false;
  const avgLen = words.reduce((sum, w) => sum + w.length, 0) / words.length;
  const longTokens = words.filter((w) => w.length >= 40).length;
  const spaceRatio = sample.split("").filter((ch) => ch === " ").length / sample.length;
  return longTokens >= 8 || (spaceRatio < 0.055 && avgLen > 11);
}

export function looksLikeDocumentDraft(content: string): boolean {
  const text = (content || "").replace(/\r\n/g, "\n").trim();
  if (!text) return false;
  if (text.startsWith("---\n")) return true;
  if (/^#{1,6}\s+\S/m.test(text)) return true;
  if (/^\d+(?:\.\d+)*\s+\S/m.test(text)) return true;
  if (text.split("\n").length >= 14 && text.length >= 1200) return true;
  return false;
}

export function looksLikeChattyReply(content: string): boolean {
  const text = (content || "").trim();
  if (!text) return false;
  if (/\b(i\s*['’]d\s+be\s+happy\s+to\s+help|before\s+we\s+begin|please\s+confirm|is\s+that\s+correct)\b/i.test(text)) return true;
  if (/\b(før\s+vi\s+begynner|har\s+du\s+noen\s+preferanser|er\s+det\s+korrekt)\b/i.test(text)) return true;
  const q = (text.match(/\?/g) || []).length;
  if (q >= 2 && text.length < 2500) return true;
  return false;
}

export function normalizeExtractedText(content: string): string {
  let text = (content || "").replace(/\r\n/g, "\n");

  text = text.replace(/h[\uE000-\uF8FF]ps:\/\//gi, "https://");
  text = text.replace(/h[\uE000-\uF8FF]p:\/\//gi, "http://");
  text = text.replace(/[\uE000-\uF8FF]/g, "");

  text = text.replace(/(\w)-\s+(\w)/g, "$1$2");
  text = text.replace(/([.,;:!?])(\S)/g, "$1 $2");
  text = text.replace(/(\))(\S)/g, "$1 $2");
  text = text.replace(/(\S)(\()/g, "$1 $2");

  text = text.replace(/[ \t\f\v]+/g, " ");
  text = text.replace(/\n{3,}/g, "\n\n");
  return text.trim();
}

export function coercePlainTextToMarkdown(content: string): string {
  const raw = (content || "").replace(/\r\n/g, "\n");
  if (!raw.trim()) return "";

  const stripDotLeadersAndPageNo = (s: string): { text: string; pageNo?: string } => {
    const noLeaders = s.replace(/(\s*\.(?:\s*\.)+\s*)/g, " ").replace(/\s{2,}/g, " ").trim();
    const m = noLeaders.match(/^(.*?)(?:\s+(\d+|[ivxlcdm]{1,6}))\s*$/i);
    if (!m) return { text: noLeaders };
    const text = (m[1] || "").trim();
    const pageNo = (m[2] || "").trim();
    if (!text) return { text: noLeaders };
    return { text, pageNo };
  };

  const isLikelyStandalonePageMarker = (line: string): boolean => {
    if (/^page\s+\d+$/i.test(line)) return true;
    if (/^[ivxlcdm]{1,6}$/i.test(line)) return true;
    return false;
  };

  const normalizeDuplicateNumberedHeading = (line: string): string | null => {
    const m = line.match(/^\s*(\d+(?:\.\d+)*)\s+(.+?)\s+\1\s+(.+?)\s*$/);
    if (!m) return null;
    const numbering = m[1];
    const partA = m[2].trim();
    const partB = m[3].trim();
    const pick = /[a-zæøå]/.test(partB) ? partB : partA;
    return `${numbering} ${pick}`;
  };

  const lines = raw.split("\n");
  const out: string[] = [];

  const pushBlank = () => {
    if (out.length === 0) return;
    if (out[out.length - 1] !== "") out.push("");
  };

  let tocMode: "none" | "toc" | "lof" | "lot" = "none";

  for (let i = 0; i < lines.length; i += 1) {
    const original = lines[i] ?? "";
    let line = original.replace(/[ \t\f\v]+/g, " ").trim();
    if (!line) {
      if (out.length > 0 && out[out.length - 1] !== "") out.push("");
      continue;
    }

    const combined = line.match(/^(contents|list of figures|list of tables|nomenclature)\s+(.+)$/i);
    if (combined) {
      const head = combined[1];
      const rest = (combined[2] || "").trim();
      if (rest) {
        lines.splice(i + 1, 0, rest);
      }
      line = head;
    }

    if (isLikelyStandalonePageMarker(line)) {
      continue;
    }

    if (/^contents$/i.test(line)) {
      pushBlank();
      out.push("## Contents");
      pushBlank();
      tocMode = "toc";
      continue;
    }
    if (/^list of figures$/i.test(line)) {
      pushBlank();
      out.push("## List of Figures");
      pushBlank();
      tocMode = "lof";
      continue;
    }
    if (/^list of tables$/i.test(line)) {
      pushBlank();
      out.push("## List of Tables");
      pushBlank();
      tocMode = "lot";
      continue;
    }

    if (tocMode !== "none") {
      if (/^\d+\s+[A-Z][A-Z\s]{3,}$/i.test(line) && !/\s\d+$/i.test(line)) {
        tocMode = "none";
      } else {
        const cleaned = stripDotLeadersAndPageNo(line);

        const tocEntry = cleaned.text.match(/^(\d+(?:\.\d+)*)\s+(.+)$/);
        if (tocEntry && tocMode === "toc") {
          const numbering = tocEntry[1];
          const title = tocEntry[2].trim();
          const depth = numbering.split(".").length;
          const indent = " ".repeat(Math.max(0, (depth - 1) * 2));
          out.push(`${indent}- ${numbering} ${title}`);
          continue;
        }

        const listEntry = cleaned.text.match(/^(\d+)\s+(.+)$/);
        if (listEntry && (tocMode === "lof" || tocMode === "lot")) {
          const n = listEntry[1];
          const caption = listEntry[2].trim();
          const label = tocMode === "lof" ? "Figure" : "Table";
          out.push(`- ${label} ${n}: ${caption}`);
          continue;
        }

        out.push(cleaned.text);
        continue;
      }
    }

    const normalizedDupHeading = normalizeDuplicateNumberedHeading(line);
    if (normalizedDupHeading) {
      line = normalizedDupHeading;
    }

    if (line.startsWith("• ") || line === "•") {
      out.push(line === "•" ? "-" : `- ${line.slice(2).trim()}`);
      continue;
    }

    const figOrTable = line.match(/^(figure|table)\s+(\d+)\s*:\s*(.+)$/i);
    if (figOrTable) {
      pushBlank();
      const label = figOrTable[1][0].toUpperCase() + figOrTable[1].slice(1).toLowerCase();
      out.push(`**${label} ${figOrTable[2]}:** ${figOrTable[3].trim()}`);
      pushBlank();
      continue;
    }

    const numbered = line.match(/^(\d+(?:\.\d+)*)\s+(.+?)$/);
    if (numbered) {
      const numbering = numbered[1];
      const title = numbered[2].trim();
      if (/\s(\d+|[ivxlcdm]{1,6})$/i.test(title) && !/[.:;!?]/.test(title)) {
        const cleaned = stripDotLeadersAndPageNo(line);
        out.push(cleaned.text);
        continue;
      }

      const depth = numbering.split(".").length;
      const level = Math.min(6, Math.max(2, 1 + depth));
      pushBlank();
      out.push(`${"#".repeat(level)} ${numbering} ${title}`);
      pushBlank();
      continue;
    }

    if (/^[A-Z][A-Z\s]{6,}$/.test(line) && line.length <= 80) {
      pushBlank();
      out.push(`## ${line}`);
      pushBlank();
      continue;
    }

    out.push(line);
  }

  const collapsed: string[] = [];
  for (const l of out) {
    if (l === "" && collapsed[collapsed.length - 1] === "") continue;
    collapsed.push(l);
  }

  return collapsed.join("\n").trim();
}

export function autoParagraphPlainText(content: string): string {
  const text = (content || "").replace(/\r\n/g, "\n").trim();
  if (!text) return "";
  if (/\n\n+/.test(text)) return text;

  const targetMin = 450;
  const targetMax = 900;
  const out: string[] = [];
  let i = 0;
  while (i < text.length) {
    const maxEnd = Math.min(i + targetMax, text.length);
    const windowText = text.slice(i, maxEnd);

    let cut = -1;
    for (let j = windowText.length - 1; j >= 0; j -= 1) {
      const ch = windowText[j];
      if (ch === "." || ch === "!" || ch === "?") {
        const next = windowText[j + 1];
        if (next === undefined || /\s/.test(next)) {
          cut = j + 1;
          break;
        }
      }
    }

    if (cut === -1) {
      const space = windowText.lastIndexOf(" ");
      cut = space > targetMin ? space : windowText.length;
    }

    if (cut < targetMin) {
      cut = Math.min(windowText.length, targetMax);
    }

    const chunk = text.slice(i, i + cut).trim();
    if (chunk) out.push(chunk);
    i += cut;

    while (i < text.length && /\s/.test(text[i])) i += 1;
  }

  return out.join("\n\n");
}
