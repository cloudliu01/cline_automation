import time
import asyncio
from playwright.async_api import async_playwright


##########################################################################################
## This script is designed to automate interactions with the Jimeng AI tool for image generation.
## It only works in non-WSL environments due to Playwright's limitations (Unable to start browser in WSL, which
## in turn causes issues with file downloads).
##########################################################################################

##########################################################################################
## Run this section to obtain auth.json. this file is needed to authenticate with the Jimeng AI tool.
##########################################################################################
#with async_playwright() as p:
#    browser = p.chromium.launch(headless=False)
#    context = browser.new_context()
#    page = context.new_page()
#    page.goto("https://jimeng.jianying.com/ai-tool/generate")
#    input("Please log in fully, then press ENTER to save auth state...")
#    context.storage_state(path="auth.json")
#    print("Auth state saved!")


class JimengAIGenerator:
    def __init__(self, target_url="https://jimeng.jianying.com/ai-tool/generate", download_dir="C:\\Users\\cloud\\Downloads"):
        self.target_url = target_url
        self.download_dir = download_dir
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.prompt_selector = 'textarea.lv-textarea[placeholder^="请输入图片生成的提示词"]'
        self.button_selector = ('button.lv-btn.lv-btn-primary.lv-btn-size-default.lv-btn-shape-circle.'
                                'lv-btn-icon-only[type="button"]')
        self.all_images = []
        self.all_images_src = []

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context(
            accept_downloads=True,
            storage_state="auth.json"
        )
        self.page = await self.get_or_open_page(self.target_url)
        await self.get_all_available_images()

    async def get_or_open_page(self, target_url, wait_timeout=10000, extra_wait=5):
        for p in self.context.pages:
            if target_url in p.url:
                self.page = p
                await p.bring_to_front()
                print(f"Switched to existing tab: {p.url}, refreshing...")
                await p.reload(wait_until="load", timeout=wait_timeout)
                await asyncio.sleep(extra_wait)
                return p
        print(f"Opening new tab for: {target_url}")
        new_page = await self.context.new_page()
        await new_page.goto(target_url, wait_until="load", timeout=wait_timeout)
        await asyncio.sleep(extra_wait)
        self.page = new_page
        return new_page

    async def clean_prompt(self):
        locator = self.page.locator(self.prompt_selector)
        await locator.wait_for(state="visible", timeout=5000)
        await locator.fill("")

    async def add_prompt(self, content):
        locator = self.page.locator(self.prompt_selector)
        await locator.wait_for(state="visible", timeout=5000)
        await locator.fill(content)

    async def click_submit(self):
        await self.page.locator(self.button_selector).first.click()

    async def get_all_available_images(self):
        img_selector = 'img[class^="image-"]'
        new_images = []
        img_locators = self.page.locator(img_selector)
        count = await img_locators.count()
        for i in range(count):
            src = await img_locators.nth(i).get_attribute('src')
            if src in self.all_images_src:
                continue
            self.all_images.append(img_locators.nth(i))
            self.all_images_src.append(src)
            new_images.append(img_locators.nth(i))
        return new_images

    async def download_images(self, index=0):
        try:
            img_selector = 'img[class^="image-"]'
            img_locator = self.page.locator(img_selector).nth(index)
            await img_locator.hover()
            download_icon_selector = 'span[class*="action-button-"]'
            download_icon_locator = self.page.locator(download_icon_selector).first
            await download_icon_locator.wait_for(state='visible', timeout=3000)
            async with self.page.expect_download() as download_info:
                await download_icon_locator.click()
            download = await download_info.value
            save_path = f"{self.download_dir}\\{download.suggested_filename}"
            await download.save_as(save_path)
            print(f"Downloaded image to {save_path}")
        except Exception as e:
            print(f"Error downloading image at index {index}: {e}")
    
    async def download_new_images(self, timeout=10):
        n = 0
        new_images = []
        try:
            while n < 10:
                new_images = await self.get_all_available_images()
                if new_images:
                    print(f"Found {len(new_images)} new images.")
                    for idx in range(0, len(new_images)):
                        await self.download_images(index=idx)
                    break
                else:
                    print("No new images found, retrying in 10 seconds...")
                await asyncio.sleep(10)
                n += 2
        except Exception as e:
            print(f"Error in download_new_images: {e}")
        return new_images

    async def close(self):
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()

async def main_test():
    print("Starting JimengAIGenerator async test...")
    gen = JimengAIGenerator()
    await gen.start()
    
    print("Cleaning prompt...")
    await gen.clean_prompt()
    
    #test_prompt = "测试自动化生成：一只小狗在阳光下打盹"
    test_prompt = ("画面整体色调温暖，细节丰富，具有油画风格，兼具写实与艺术感，氛围安静、学术，充满希望与理想主义。"
              "画面描绘了年轻坚定的Edwin C. Barnes自信地站在著名发明家托马斯·爱迪生面前，地点在爱迪生的工作室。"
              "工作室内摆放着简洁但具有代表性的早期电气发明元素，比如桌上的风格化灯泡、大型简化发电机以及一些基本工具。"
              "整个画面营造出充满理想、灵感闪现的氛围，突出年轻人渴望成功、勇敢追梦的精神。")
    print(f"Adding prompt: {test_prompt}")
    await gen.add_prompt(test_prompt)
    
    print("Clicking submit button...")
    await gen.click_submit()
    
    print("Waiting for new images to appear...")
    await asyncio.sleep(8)  # 根据你平台响应速度调整
    
    images = await gen.get_all_available_images()
    print(f"Current found images: {len(images)}")
    if images:
        print("Attempting to download the first image...")
        await gen.download_images(index=0)
    else:
        print("No images found to download.")
    
    print("Closing JimengAIGenerator...")
    await gen.close()
    print("Test complete.")

if __name__ == "__main__":
    asyncio.run(main_test())
