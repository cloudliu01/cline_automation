import time
from playwright.sync_api import sync_playwright

class JimengAIGenerator:
    def __init__(self, cdp_url="http://localhost:9222", target_url="https://jimeng.jianying.com/ai-tool/generate"):
        self.cdp_url = cdp_url
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)
        self.context = self.browser.contexts[0]

        self.get_or_open_page(target_url)
        self.page = self._find_target_page()
        if not self.page:
            raise Exception("Target page not found! Please open the target URL in Chrome.")

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
        """
        Ensure the target_url is loaded in one of the tabs.
        If found, switch to that tab and refresh; else, open a new one and wait for load.
        Returns: page (Playwright page object)
        """
        # Try to find existing page/tab
        for p in self.context.pages:
            if target_url in p.url:
                self.page = p
                p.bring_to_front()
                print(f"Switched to existing tab: {p.url}, refreshing...")
                p.reload(wait_until="load", timeout=wait_timeout)
                time.sleep(extra_wait)  # Wait for any JS to settle
                return p

        # Not found: open new tab and wait for load
        print(f"Opening new tab for: {target_url}")
        new_page = self.context.new_page()
        new_page.goto(target_url, wait_until="load", timeout=wait_timeout)
        time.sleep(extra_wait)  # Wait for any JS to settle
        self.page = new_page
        return new_page



    def clean_prompt(self):
        """Clear the prompt textarea."""
        locator = self.page.locator(self.prompt_selector)
        locator.wait_for(state="visible", timeout=5000)
        locator.fill("")

    def add_prompt(self, content):
        """Fill the prompt textarea with given content."""
        locator = self.page.locator(self.prompt_selector)
        locator.wait_for(state="visible", timeout=5000)
        locator.fill(content)

    def click_submit(self):
        """Click the submit ('生成') button."""
        self.page.locator(self.button_selector).first.click()
    
    def download_images(self):
        """Download images after they are generated."""
        # 1. Hover over the image (adjust selector as needed)
        img_selector = 'img.image-C3mkAg'  # or nth(i) for a specific image
        img_locator = self.page.locator(img_selector).first
        img_locator.hover()

        # 2. Wait for the download icon to appear
        # Suppose its class always includes "action-button-"
        download_icon_selector = 'span[class*="action-button-"]'
        download_icon_locator = self.page.locator(download_icon_selector).first

        download_icon_locator.wait_for(state='visible', timeout=3000)

        # 3. Click the download icon
        download_icon_locator.click()




    def close(self):
        """Cleanup browser and playwright."""
        self.browser.close()
        self.playwright.stop()

if __name__ == "__main__":
    # Example usage:
    gen = JimengAIGenerator(cdp_url="http://192.168.1.227:9229", target_url="https://jimeng.jianying.com/ai-tool/generate")
    gen.download_images()
    gen.clean_prompt()
    gen.add_prompt("一只小狗在冬天的阳光下打盹，背景为四川小镇的街道，画面色调柔和，风格为儿童填色画。")
    gen.click_submit()
    # ...do other actions or wait for results...
    # gen.close()  # Call this when completely done