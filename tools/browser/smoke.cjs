'use strict';
const assert = require('node:assert/strict');
const {chromium} = require('playwright-core');
const binary = require('@sparticuz/chromium');
(async () => {
  const browser = await chromium.launch({args:binary.args.filter(arg=>!arg.includes("disable-web-security") && !arg.includes("allow-running-insecure-content")),executablePath:await binary.executablePath(),headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1200,height:900}});
    const errors = [];
    page.on('pageerror',error=>errors.push(String(error)));
    await page.goto(process.argv[2]);
    assert.equal(await page.title(),'UCL Design Studio');
    assert.equal(await page.locator('#workspace').evaluate(node=>getComputedStyle(node).display),'grid');
    assert.equal(await page.locator('#save').evaluate(node=>getComputedStyle(node).borderRadius),'8px');
    await page.locator('#save').hover();
    // Wait for the advertised 200 ms CSS transition to finish.
    await page.waitForFunction(()=>getComputedStyle(document.querySelector('#save')).backgroundColor==='rgb(139, 92, 246)');
    await page.getByLabel('Project name').fill('Chromium verified');
    await Promise.all([page.waitForNavigation({waitUntil:'load'}),page.locator('#save').click()]);
    assert.equal(await page.locator('body').innerText().then(text=>text.includes('Saved: Chromium verified')),true,await page.locator('body').innerText());
    await page.waitForFunction(()=>document.querySelector('#status')?.textContent==='Saved: Chromium verified');
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.locator('#workspace').evaluate(node=>getComputedStyle(node).display),'block');
    await page.emulateMedia({reducedMotion:'reduce'});
    assert.equal(await page.locator('#headline').evaluate(node=>getComputedStyle(node).animationName),'none');
    assert.deepEqual(errors,[]);
    console.log('Chromium: Tailwind, hover, responsive panels, CSRF form postback, input, animation and reduced motion passed.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
