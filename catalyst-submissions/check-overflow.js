// Reports any page in the built report whose content overflows its A4 box.
//
// Why this exists: the pages are fixed-size with overflow:hidden, so content
// that does not fit is CLIPPED SILENTLY. Nothing errors, the PDF still has the
// right page count, and the only symptom is a sentence that stops mid-word
// several pages in. Editing the text is exactly when that happens, so the
// check belongs in the build rather than in a proofread.
//
// Usage: node check-overflow.js   (after build-report.js)
// Exits 1 if any page overflows.

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const DIR = path.join(__dirname, "report");
const SRC = path.join(DIR, "report.html");
const TMP = path.join(DIR, ".overflow-check.html");

const probe = `
<script>
window.addEventListener('load', () => {
  // Let the webfonts settle first: text reflows when they land, and a page
  // that fits in a fallback face can overflow in the real one.
  const go = () => {
    const out = [];
    document.querySelectorAll('.page').forEach((p, i) => {
      const label = p.getAttribute('data-screen-label') || ('page ' + (i + 1));
      // scrollHeight is no good here: the design bleeds decorative shapes
      // deliberately off the page edge, and every one of those would read as
      // an overflow. Only in-flow content can be clipped in a way that loses
      // meaning, so measure the lowest in-flow element instead. Absolutely
      // positioned subtrees are decoration by construction in this document.
      const box = p.getBoundingClientRect();
      let lowest = box.top;
      p.querySelectorAll('*').forEach((el) => {
        if (el.closest('[style*="position:absolute"]')) return;
        const r = el.getBoundingClientRect();
        if (r.height && r.bottom > lowest) lowest = r.bottom;
      });
      const over = Math.round(lowest - box.bottom);
      if (over > 1) out.push(label + ' overflows by ' + over + 'px');
    });
    document.title = 'OVERFLOW_REPORT:' + (out.length ? out.join(' | ') : 'none');
  };
  document.fonts && document.fonts.ready ? document.fonts.ready.then(go) : go();
});
</script>`;

fs.writeFileSync(TMP, fs.readFileSync(SRC, "utf8").replace("</body>", probe + "\n</body>"));

const chrome = process.env.CHROME || "google-chrome";
const dom = execFileSync(
  chrome,
  ["--headless", "--disable-gpu", "--no-sandbox", "--virtual-time-budget=15000", "--dump-dom", TMP],
  { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 }
);
fs.unlinkSync(TMP);

const m = dom.match(/OVERFLOW_REPORT:([^<]*)</);
if (!m) {
  console.error("could not read the overflow report (did the page load?)");
  process.exit(2);
}
if (m[1].trim() === "none") {
  console.log("no page overflows");
  process.exit(0);
}
console.error("CLIPPED CONTENT:\n  " + m[1].split(" | ").join("\n  "));
process.exit(1);
