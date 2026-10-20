// Renders sketches/*.svg to PNG (1080x1080) + comparison.png using Playwright Chromium.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const dir = path.join(__dirname, 'sketches');
const items = [['style1_flat','1 Flat'],['style2_cartoon','2 Cartoon'],['style3_sticker','3 Sticker']];
(async () => {
  const browser = await chromium.launch(process.env.CHROMIUM_PATH ? {executablePath: process.env.CHROMIUM_PATH} : {});
  const page = await browser.newPage({ viewport: { width: 1080, height: 1080 } });
  for (const [n] of items) {
    await page.goto('file://' + path.join(dir, n + '.svg'));
    await page.screenshot({ path: path.join(dir, n + '.png') });
  }
  const cards = items.map(([n,l]) => `<div class=c><img src="data:image/png;base64,${fs.readFileSync(path.join(dir,n+'.png')).toString('base64')}"><b>${l}</b></div>`).join('');
  const cmp = await browser.newPage({ viewport: { width: 2160, height: 720 } });
  await cmp.setContent(`<style>body{margin:0;display:flex;background:#fff}.c{position:relative;width:720px;height:720px}img{width:720px;height:720px}b{position:absolute;left:24px;top:20px;font:700 40px sans-serif;color:#3a2a25;background:#ffffffcc;padding:6px 18px;border-radius:30px}</style>${cards}`);
  await cmp.screenshot({ path: path.join(dir, 'comparison.png') });
  await browser.close();
})();
