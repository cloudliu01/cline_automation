import time
from playwright.sync_api import sync_playwright


##########################################################################################
## This script is designed to automate interactions with the Jimeng AI tool for image generation.
## It only works in non-WSL environments due to Playwright's limitations (Unable to start browser in WSL, which
## in turn causes issues with file downloads).
##########################################################################################

##########################################################################################
## Run this section to obtain auth.json. this file is needed to authenticate with the Jimeng AI tool.
##########################################################################################
#with sync_playwright() as p:
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
        self.playwright = sync_playwright().start()
        # Launch a new browser context with download support!
        self.browser = self.playwright.chromium.launch(headless=False)


        self.context = self.browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 900},
            storage_state="auth.json"
        )

        self.page = self.get_or_open_page(self.target_url)
        
        #input("Please complete login in the browser, then press ENTER to continue...")

        # Common selectors
        self.prompt_selector = 'textarea.lv-textarea[placeholder^="请输入图片生成的提示词"]'
        self.button_selector = ('button.lv-btn.lv-btn-primary.lv-btn-size-default.lv-btn-shape-circle.'
                                'lv-btn-icon-only[type="button"]')

    def _find_target_page(self):
        for p_ in self.context.pages:
            if "jimeng.jianying.com/ai-tool/generate" in p_.url:
                return p_
        return None

    def get_or_open_page(self, target_url, wait_timeout=10000, extra_wait=5):
        # Try to find existing page/tab
        for p in self.context.pages:
            if target_url in p.url:
                self.page = p
                p.bring_to_front()
                print(f"Switched to existing tab: {p.url}, refreshing...")
                p.reload(wait_until="load", timeout=wait_timeout)
                time.sleep(extra_wait)
                return p
        # Not found: open new tab and wait for load
        print(f"Opening new tab for: {target_url}")
        new_page = self.context.new_page()
        new_page.goto(target_url, wait_until="load", timeout=wait_timeout)
        time.sleep(extra_wait)
        self.page = new_page
        return new_page

    def clean_prompt(self):
        locator = self.page.locator(self.prompt_selector)
        locator.wait_for(state="visible", timeout=5000)
        locator.fill("")

    def add_prompt(self, content):
        locator = self.page.locator(self.prompt_selector)
        locator.wait_for(state="visible", timeout=5000)
        locator.fill(content)

    def click_submit(self):
        self.page.locator(self.button_selector).first.click()

    def download_images(self, index=0):
        img_selector = 'img.image-C3mkAg'
        img_locator = self.page.locator(img_selector).nth(index)
        img_locator.hover()
        download_icon_selector = 'span[class*="action-button-"]'
        download_icon_locator = self.page.locator(download_icon_selector).first
        download_icon_locator.wait_for(state='visible', timeout=3000)
        # Start waiting for the download before you click!
        with self.page.expect_download() as download_info:
            download_icon_locator.click()
        download = download_info.value
        # Save download with original filename (or you can specify a path)
        save_path = f"{self.download_dir}\\{download.suggested_filename}"
        download.save_as(save_path)
        print(f"Downloaded image to {save_path}")

    def close(self):
        self.context.close()
        self.browser.close()
        self.playwright.stop()

if __name__ == "__main__":
    gen = JimengAIGenerator()
    gen.clean_prompt()
    gen.download_images()
    gen.add_prompt("一只小狗在冬天的阳光下打盹，背景为四川小镇的街道，画面色调柔和，风格为儿童填色画。")
    gen.click_submit()
    # ...wait for images to generate as needed...
    # gen.close()  # Close when done