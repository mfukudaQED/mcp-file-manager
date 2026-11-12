import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { marked } from "marked";
import markedKatex from "marked-katex-extension";

marked.use(markedKatex({
  output: "mathml", throwOnError: false, nonStandard: true, trust: false,
}));

const fixture = "Inline $\\zeta=\\frac12 \\operatorname{Re}(x)$ and （$x^2$）。\n"
  + "\n$$\n\\begin{pmatrix}a&b\\\\c&d\\end{pmatrix}\\tag{1}\n$$\n"
  + "\n" + String.fromCharCode(96).repeat(3) + "text\n$not math$\n"
  + String.fromCharCode(96).repeat(3) + "\n";
const html = marked.parse(fixture);
assert.equal((html.match(/<math\b/g) ?? []).length, 3);
assert(!html.includes("katex-error"));
assert(html.includes("$not math$"));

if (process.argv[2]) {
  const source = readFileSync(process.argv[2], "utf8");
  const rendered = marked.parse(source);
  const mathCount = (rendered.match(/<math\b/g) ?? []).length;
  const errors = rendered.match(/<span class="katex-error"[^>]*>[\s\S]*?<\/span>/g) ?? [];
  console.log("Document math expressions:", mathCount, "KaTeX errors:", errors.length);
  for (const error of errors.slice(0, 5)) console.error(error.slice(0, 300));
  assert(mathCount >= 89, "Some equations did not parse");
  assert.equal(errors.length, 0, "Invalid math input");
}
console.log("Math preview parsing passed");
