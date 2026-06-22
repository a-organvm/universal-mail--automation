// Visual proof for the provider brand-theming on web/index.html (PR #35).
//
// Verifies, against the real rendered page, that:
//   1. each theme dial dot swaps the html[data-provider] attribute,
//   2. the --accent custom property resolves to the provider's brand color,
//   3. the #provider triage select stays in sync with the dial, and
//   4. the chosen theme persists across a reload (localStorage).
//
// Usage:  npx playwright install chromium   # once
//         node tests/theme_proof.mjs [output-dir]
// Writes theme-<name>.png screenshots to output-dir (default: os tmpdir).
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const FILE = 'file://' + join(HERE, '..', 'web', 'index.html');
const OUT = process.argv[2] ?? tmpdir();

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 820 } });
await page.goto(FILE);
await page.evaluate(() => localStorage.clear());

const accent = () => page.evaluate(() =>
  getComputedStyle(document.documentElement).getPropertyValue('--accent').trim());

console.log('universal accent:', await accent());
await page.screenshot({ path: `${OUT}/theme-universal.png` });

for (const theme of ['gmail', 'outlook', 'icloud', 'imap']) {
  await page.click(`.theme-dial .dot[data-theme="${theme}"]`);
  await page.waitForTimeout(900); // let the phase shift settle
  const a = await accent();
  const attr = await page.evaluate(() => document.documentElement.getAttribute('data-provider'));
  const sel = await page.evaluate(() => document.getElementById('provider').value);
  console.log(`${theme} accent: ${a} | data-provider=${attr} | select=${sel}`);
  await page.screenshot({ path: `${OUT}/theme-${theme}.png` });
}

// persistence check
await page.reload();
const persisted = await page.evaluate(() => document.documentElement.getAttribute('data-provider'));
console.log('persisted after reload:', persisted);

await browser.close();
