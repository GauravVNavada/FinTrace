import { readdir, readFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("../", import.meta.url)));
const uiSource = join(root, "packages", "ui", "src");
const webSource = join(root, "apps", "web");
const requiredPrimitives = ["alert", "badge", "button", "card", "input", "progress", "select", "separator", "skeleton", "table"];
const forbiddenColors = /#[0-9a-f]{3,8}\b|\b(?:rgb|hsl)a?\s*\(|\b(?:bg|text|border|ring|from|to|via)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|white|black)(?:-[0-9]+|\/|\b)/i;

const failures = [];
const fail = message => failures.push(message);

const globals = (await readFile(join(webSource, "app", "globals.css"), "utf8")).trim();
if (!/^@import\s+["'][^"']+["'];$/.test(globals) || globals.split(/\r?\n/).length !== 1) {
  fail("apps/web/app/globals.css must contain exactly one import and no declarations");
}

const uiFiles = await filesUnder(uiSource);
for (const primitive of requiredPrimitives) {
  const path = join(uiSource, `${primitive}.tsx`);
  if (!uiFiles.includes(path)) fail(`Missing shared primitive: packages/ui/src/${primitive}.tsx`);
  const barrel = await readFile(join(uiSource, "index.ts"), "utf8");
  if (!barrel.includes(`./${primitive}`)) fail(`Primitive is not exported from packages/ui/src/index.ts: ${primitive}`);
}

const uiScanFiles = uiFiles.filter(path => !path.endsWith("global.css") && !path.endsWith("tailwind.preset.ts") && !requiredPrimitives.some(primitive => path.endsWith(`${primitive}.tsx`)));
const webScanFiles = (await filesUnder(webSource)).filter(path => !path.includes(`${join("apps", "web", ".next")}`) && !path.includes(`${join("apps", "web", "node_modules")}`));
for (const path of [...uiScanFiles, ...webScanFiles]) {
  const source = await readFile(path, "utf8");
  if (forbiddenColors.test(source)) fail(`Forbidden literal/palette color in ${relative(root, path)}`);
  if (webScanFiles.includes(path) && /<\/?(?:button|input|select|table)\b/.test(source)) fail(`Native reusable primitive markup remains in ${relative(root, path)}; compose @fintrace/ui instead`);
}

const appPrimitiveFiles = (await filesUnder(join(webSource, "components"))).filter(path => /[\\/](button|card|badge|input|select|table|dialog|tabs|tooltip|dropdown-menu|alert|skeleton)\.tsx$/.test(path));
for (const path of appPrimitiveFiles) fail(`App-local primitive duplicate: ${relative(root, path)}`);

if (failures.length) {
  console.error(failures.map(message => `✗ ${message}`).join("\n"));
  process.exitCode = 1;
} else {
  console.log(`UI architecture checks passed (${requiredPrimitives.length} primitives, semantic token scan, stylesheet boundary, and duplicate scan).`);
}

async function filesUnder(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async entry => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return filesUnder(path);
    return /\.(css|ts|tsx|mjs)$/.test(entry.name) ? [path] : [];
  }));
  return nested.flat();
}
