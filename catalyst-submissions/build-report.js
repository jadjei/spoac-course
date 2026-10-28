// Converts the Claude Design document (.dc.html) into standalone printable
// HTML, then Chrome prints it to PDF.
//
// The design file is authored against the Claude Design runtime: an <x-dc>
// wrapper, a <helmet> head block, <sc-if> variant switches, and the
// <doc-page> web component. None of that needs to ship in the repo. The
// document is explicitly paginated, one <section class="page"> per page, so
// the only behaviour worth keeping is the page box itself: A4, full bleed,
// overflow hidden, a break between pages. That is the CSS below, and it
// removes a 30 KB runtime dependency from a document we have to archive.
//
// Variant switches are resolved at build time from VARIANTS.
//
// Usage:
//   node build-report.js
//   google-chrome --headless --print-to-pdf=out.pdf --no-pdf-header-footer report.html

const fs = require("fs");
const path = require("path");

const DIR = __dirname;
const SRC = path.join(DIR, "report", "SPO Academy Completion Report.dc.html");
const OUT = path.join(DIR, "report", "report.html");
// The PDF is published from the docs site, so the print step writes straight
// into its static tree. One copy, tracked in one repo: a second copy sitting
// here would drift the moment either was rebuilt. Assumes the docs repo is
// checked out next to this one; PCR_PDF overrides.
const PDF = process.env.PCR_PDF ||
  path.join(DIR, "..", "..", "spoacademydocs", "static", "downloads", "SPO-Academy-PCR.pdf");

// Which cover the document uses. Mirrors the hint values in the design file.
const VARIANTS = { coverNavy: true, coverOrange: false };

let src = fs.readFileSync(SRC, "utf8");

// Resolve <sc-if value="{{ name }}"> blocks: keep the body when the variant
// is on, drop the whole block when it is off.
src = src.replace(
  /<sc-if value="\{\{\s*(\w+)\s*\}\}"[^>]*>([\s\S]*?)<\/sc-if>/g,
  (_, name, body) => (VARIANTS[name] ? body : "")
);

const helmet = (src.match(/<helmet>([\s\S]*?)<\/helmet>/) || [, ""])[1];
const docPage = src.match(/<doc-page[^>]*>([\s\S]*?)<\/doc-page>/);
if (!docPage) throw new Error("no <doc-page> found in the design file");

// Keep the font links and the author's own style block; drop the runtime
// script tags, which the page box CSS below replaces.
const head = helmet
  .replace(/<script[^>]*><\/script>/g, "")
  .replace(/<script[\s\S]*?<\/script>/g, "")
  .trim();

const pageBox = `
<style>
  /* A4 page box, matching doc-page's explicit-pagination behaviour. */
  html, body { margin: 0; padding: 0; background: #f5f5f4; }
  .page {
    position: relative;
    width: 210mm;
    height: 297mm;
    margin: 0 auto 1rem;
    overflow: hidden;
    box-sizing: border-box;
    background: #fff;
    box-shadow: 0 2px 10px rgba(0,0,0,.25);
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
    break-inside: avoid;
  }
  @page { size: 210mm 297mm; margin: 0; }
  @media print {
    html, body { background: none; }
    .page {
      margin: 0 !important;
      box-shadow: none !important;
      border-radius: 0 !important;
    }
    .page:not(:first-child) { break-before: page !important; }
    * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  }
</style>`;

// The design renders transaction hashes and document names as plain text.
// In a PDF whose entire evidence model is "go and check this yourself", a
// reference you cannot click is a reference most readers will not follow, and
// Catalyst asks that every link be tested. Linkify them at build time rather
// than hand-editing the design, so a re-import does not lose the work.
const SITE = "https://catalyst.pages.fluid7.co.uk/spoacademydocs/docs";
const DOCS = {
  "feedback report": SITE + "/cohort/feedback-report",
  "action plan": SITE + "/cohort/improvements-and-actions",
  "improvements and action plan": SITE + "/cohort/improvements-and-actions",
  "pricing strategy": SITE + "/milestones/pricing-strategy",
  "session 4 write-up": SITE + "/cohort/2026-10-26-session4",
};

let bodyHtml = docPage[1].trim();

// Cardano transaction hashes: 64 hex characters standing alone in a text node.
bodyHtml = bodyHtml.replace(
  />([^<>]*?)\b([0-9a-f]{64})\b([^<>]*?)</g,
  (m, before, hash, after) =>
    `>${before}<a href="https://adastat.net/transactions/${hash}" style="color:inherit;text-decoration:none">${hash}</a>${after}<`
);

// Named supporting documents, matched only inside plain text.
for (const [label, href] of Object.entries(DOCS)) {
  const re = new RegExp(`>([^<>]*?)\\b(${label})\\b([^<>]*?)<`, "gi");
  bodyHtml = bodyHtml.replace(
    re,
    (m, before, text, after) =>
      m.includes("</a>") ? m : `>${before}<a href="${href}">${text}</a>${after}<`
  );
}

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SPO Academy - Project Completion Report</title>
${head}
${pageBox}
</head>
<body>
${bodyHtml}
</body>
</html>
`;

fs.writeFileSync(OUT, html);
const pages = (html.match(/class="page"/g) || []).length;
console.log(`wrote ${OUT} (${pages} pages, ${(html.length / 1024).toFixed(0)} KB)`);

// Print here rather than leaving it as a separate command. The PDF is the
// published artefact, so a build that updates the HTML and not the PDF leaves
// the docs site serving a stale download, which nobody would notice.
const { execFileSync } = require("child_process");
execFileSync(process.env.CHROME || "google-chrome", [
  "--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
  "--virtual-time-budget=20000", `--print-to-pdf=${PDF}`, OUT,
], { stdio: ["ignore", "ignore", "ignore"] });
console.log(`printed ${PDF} (${(fs.statSync(PDF).size / 1024).toFixed(0)} KB)`);
