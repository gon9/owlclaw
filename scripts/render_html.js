#!/usr/bin/env node
// HTML ファイルを Puppeteer でレンダリングして PNG に保存する。
// 使い方: node scripts/render_html.js <html-path> <png-path>

const path = require('path');
const fs = require('fs');

(async () => {
  const htmlPath = process.argv[2];
  const outPath = process.argv[3];
  if (!htmlPath || !outPath) {
    console.error('Usage: node render_html.js <html> <out.png>');
    process.exit(1);
  }

  // /tmp/puppeteer_test に PoC でインストール済みなのでそこから読む
  let puppeteer;
  const candidates = [
    path.join(__dirname, '..', 'node_modules', 'puppeteer'),
    '/tmp/puppeteer_test/node_modules/puppeteer',
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) {
      puppeteer = require(c);
      break;
    }
  }
  if (!puppeteer) {
    console.error('puppeteer not found. install: npm install puppeteer --prefix /tmp/puppeteer_test');
    process.exit(1);
  }

  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
  await page.goto('file://' + path.resolve(htmlPath), { waitUntil: 'networkidle0' });
  await page.screenshot({
    path: outPath,
    type: 'png',
    clip: { x: 0, y: 0, width: 1920, height: 1080 },
  });
  await browser.close();
  console.log('saved:', outPath);
})();
