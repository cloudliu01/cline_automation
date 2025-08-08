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
            #viewport={"width": 1280, "height": 900},
            storage_state="auth.json"
        )

        self.page = self.get_or_open_page(self.target_url)
        
        #input("Please complete login in the browser, then press ENTER to continue...")

        # Common selectors
        self.prompt_selector = 'textarea.lv-textarea[placeholder^="请输入图片生成的提示词"]'
        self.button_selector = ('button.lv-btn.lv-btn-primary.lv-btn-size-default.lv-btn-shape-circle.'
                                'lv-btn-icon-only[type="button"]')

        self.all_images = []
        self.all_images_src = []
        self.get_all_available_images()

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

    def get_all_available_images(self):
        img_selector = 'img[class^="image-"]'
        new_images = []
        img_locators = self.page.locator(img_selector)
        for i in range(img_locators.count()):
            if img_locators.nth(i).get_attribute('src') in self.all_images_src:
                continue
            self.all_images.append(img_locators.nth(i))
            self.all_images_src.append(img_locators.nth(i).get_attribute('src'))
            new_images.append(img_locators.nth(i))
        return new_images

    def download_images(self, index=0):
        try:
            img_selector = 'img[class^="image-"]'
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
        except Exception as e:
            print(f"Error downloading image at index {index}: {e}")
    
    def download_new_images(self, timeout=10):
        n = 0
        new_images = []
        try:
            while n < 10:
                new_images = self.get_all_available_images()
                if new_images:
                    print(f"Found {len(new_images)} new images.")
                    for idx in range(0, len(new_images)):
                        self.download_images(index=idx)
                    break
                else:
                    print("No new images found, retrying in 10 seconds...")
                time.sleep(10)
                n += 2
        except Exception as e:
            print(f"Error in download_new_images: {e}")
        return new_images

    def close(self):
        self.context.close()
        self.browser.close()
        self.playwright.stop()

if __name__ == "__main__":
    prompt = ("画面整体色调温暖，细节丰富，具有油画风格，兼具写实与艺术感，氛围安静、学术，充满希望与理想主义。"
              "画面描绘了年轻坚定的Edwin C. Barnes自信地站在著名发明家托马斯·爱迪生面前，地点在爱迪生的工作室。"
              "工作室内摆放着简洁但具有代表性的早期电气发明元素，比如桌上的风格化灯泡、大型简化发电机以及一些基本工具。"
              "整个画面营造出充满理想、灵感闪现的氛围，突出年轻人渴望成功、勇敢追梦的精神。")
    gen = JimengAIGenerator()
    gen.clean_prompt()
    gen.add_prompt(prompt)
    gen.click_submit()
    gen.download_new_images()
    # ...wait for images to generate as needed...
    gen.close()  # Close when done