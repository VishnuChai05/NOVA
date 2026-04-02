function sanitizeFileNamePart(value) {
  return String(value || "document")
    .trim()
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, " ")
    .slice(0, 80) || "document";
}

function buildWordHtml(title, content) {
  const safeTitle = String(title || "Document");
  const safeContent = String(content || "").replace(/\r\n/g, "\n");
  const htmlBody = safeContent
    .split("\n")
    .map((line) => {
      const escapedLine = line
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

      if (!escapedLine.trim()) {
        return "<p>&nbsp;</p>";
      }

      if (escapedLine.startsWith("# ")) {
        return `<h1>${escapedLine.slice(2).trim()}</h1>`;
      }

      if (escapedLine.startsWith("## ")) {
        return `<h2>${escapedLine.slice(3).trim()}</h2>`;
      }

      if (escapedLine.startsWith("### ")) {
        return `<h3>${escapedLine.slice(4).trim()}</h3>`;
      }

      if (/^\d+\.\s+/.test(escapedLine)) {
        return `<p>${escapedLine.replace(/^(\d+\.\s+)/, "<strong>$1</strong>")}</p>`;
      }

      if (escapedLine.startsWith("- ")) {
        return `<li>${escapedLine.slice(2).trim()}</li>`;
      }

      return `<p>${escapedLine}</p>`;
    })
    .join("");

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>${safeTitle.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</title>
  <style>
    body { font-family: Georgia, 'Times New Roman', serif; line-height: 1.5; color: #222; }
    h1, h2, h3 { color: #1f1f1f; }
    p { margin: 0 0 10px; }
    ul { margin: 0 0 10px 20px; }
    li { margin: 0 0 6px; }
  </style>
</head>
<body>
${htmlBody}
</body>
</html>`;
}

export function downloadAsWordDocument({ title, content, fileNamePrefix = "document" }) {
  const fileName = `${sanitizeFileNamePart(fileNamePrefix)}-${sanitizeFileNamePart(title)}.doc`;
  const html = buildWordHtml(title, content);
  const blob = new Blob([html], { type: "application/msword;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}