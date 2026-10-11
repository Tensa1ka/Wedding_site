// Рендер графики из tools/art/*.html в PNG с прозрачным фоном.
// Запуск: node tools/render.js [имя ...]   (без аргументов – все файлы)
const path = require('path');
const fs = require('fs');
const { chromium } = require(require('child_process').execSync('npm root -g').toString().trim() + '/playwright');

const artDir = path.join(__dirname, 'art');
const outDir = path.join(__dirname, 'out');
fs.mkdirSync(outDir, { recursive: true });

(async () => {
  const names = process.argv.slice(2).length
    ? process.argv.slice(2)
    : fs.readdirSync(artDir).filter(f => f.endsWith('.html')).map(f => f.replace('.html', ''));
  const browser = await chromium.launch();
  for (const name of names) {
    const file = path.join(artDir, name + '.html');
    const html = fs.readFileSync(file, 'utf8');
    const scale = Number((html.match(/data-scale="([\d.]+)"/) || [])[1] || 2);
    const page = await browser.newPage({ deviceScaleFactor: scale, viewport: { width: 1600, height: 1600 } });
    page.on('pageerror', e => console.error('  ! ' + name + ': ' + e.message));
    await page.goto('file://' + file);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(300);
    const art = await page.$('#art');
    await art.screenshot({ path: path.join(outDir, name + '.png'), omitBackground: true });
    const box = await art.boundingBox();
    console.log(name, Math.round(box.width * scale) + 'x' + Math.round(box.height * scale));
    await page.close();
  }
  await browser.close();
})();
