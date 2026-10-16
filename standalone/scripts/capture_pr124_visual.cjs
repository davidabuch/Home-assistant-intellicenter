const { chromium } = require("playwright");
const fs = require("fs");

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 393, height: 852 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();

  await page.route("**/api/state", async route => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        pool: { state: "heat", attributes: { current_temperature: 83, temperature: 88 } },
        spa: { state: "off", attributes: { current_temperature: 83, temperature: 101 } },
        jets: { state: "off", attributes: {} },
        spillway: { state: "off", attributes: {} },
        slide: { state: "off", attributes: {} },
        light: { state: "on", attributes: { effect: "Light Show", effect_list: ["Light Show"] } },
        pool_sanitation: { state: "off", attributes: {} },
        spa_sanitation: { state: "off", attributes: {} },
        "binary_sensor.solar_heating_active": { state: "off", attributes: {} },
        "binary_sensor.gas_heater_active": { state: "off", attributes: {} }
      })
    });
  });

  await page.route("**/api/permissions", async route => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ pool_control: true, light_control: true })
    });
  });

  await page.goto("http://127.0.0.1:8765/", { waitUntil: "networkidle" });
  await page.waitForSelector("#controls:not([hidden])");
  await page.screenshot({ path: "standalone/visual-acceptance-pr124.png", fullPage: true });
  await browser.close();

  if (!fs.existsSync("standalone/visual-acceptance-pr124.png")) {
    throw new Error("visual acceptance screenshot was not created");
  }
})();