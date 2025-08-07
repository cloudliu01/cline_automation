import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.baidu.com")
        print(await page.title())
        await browser.close()

asyncio.run(run())
