
"""
Simple demonstration of the CDP feature.

To test this locally, follow these steps:
1. Create a shortcut for the executable Chrome file.
2. Add the following argument to the shortcut:
   - On Windows: `--remote-debugging-port=9222`
3. Open a web browser and navigate to `http://localhost:9222/json/version` to verify that the Remote Debugging Protocol (CDP) is running.
4. Launch this example.

@dev You need to set the `GOOGLE_API_KEY` environment variable before proceeding.
"""

import asyncio
import os
import sys
import builtins
import aioconsole  # pip install aioconsole
from IPython import embed  # pip install ipython


sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()


from browser_use import Agent, Controller
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.llm import ChatGoogle, ChatOpenAI


#api_key = os.getenv('GOOGLE_API_KEY')
api_key = os.getenv('OPENAI_API_KEY')


if not api_key:
	raise ValueError('OPENAI_API_KEY or GOOGLE_API_KEY is not set')

browser_session = BrowserSession(
	browser_profile=BrowserProfile(
		headless=False,
	),
	cdp_url='http://192.168.1.227:9229',
)
controller = Controller()


async def main():
    
    #task = 'Navigate to https://jimeng.jianying.com/ai-tool/home'
    #task = 'Navigate to https://www.google.com and search for "Python programming". Click on the first result and extract the title of the page.'
    prompt= '''以儿童填色画风格创作：黑色粗线条勾勒，无阴影或色块，造型简洁、易于辨认。\n
场景
画面中，年轻坚定的巴恩斯自信地站在爱迪生面前，地点是爱迪生的工作室。工作室内有早期电气发明的简化标志，如台上的灯泡、大号简化发电机和基础工具，整体氛围充满希望与创新火花。
人物
巴恩斯：眼神明亮、充满期待和决心，嘴角带着坚定微笑。形象略显疲惫但整洁，穿着简单、有点皱的裤子和衬衫，袖子卷起，姿态挺拔直接，直视爱迪生。
爱迪生：年长、睿智且善于观察，表情和蔼又有分辨力，典型的胡须，发型简洁。身穿工装或简洁西装，手持简单工具或做出手势，专注看着巴恩斯，嘴角微笑，认可对方意志。
背景
工作室：空间整洁实用，白色墙面与地面突出“涂色画”风格。发明物以粗线简化勾勒，例如灯泡画成带波纹的圆，发电机是带轮子的简化圆柱。工具如锤子、扳手也是简单实心造型，整体展现专注与创新氛围。'''
    task = f'1,Navigate to https://jimeng.jianying.com/ai-tool/generate, in the prompt field (it should be on the bottom of the page, has a plus sign in its left'
    task += f'2, if it has content, go to step 3; otherwise go to step 3'
    task += f'3, select all text inside, hit "delete" key to clear the content'
    task += f'4, in the prompt form, type in “{prompt}”.'
    task += f'5, click the "send" button (on the right side of the input form, with up arrary on it) ' 
    task += f'6, wait 1 minute for the images (there will be 4 on the top) to be generated. ' 
    task += f'''7, Once all images become available, move the cursor to the first image(hover on it but don't click), then a download button will appear on the top of the image , click the button to download the image. '''
    task += f'''8, move the cursor to the first image(hover on it but don't click), then a download button will appear on the top of the image , click the button to download the image. '''
    # Assert api_key is not None to satisfy type checker
    assert api_key is not None, 'API_KEY must be set'
    #model = ChatGoogle(model='gemini-2.5-flash', api_key=api_key)
    model = ChatOpenAI(model='gpt-4.1-mini', api_key=api_key)
    agent = Agent(
    	task=task,
    	llm=model,
    	controller=controller,
    	browser_session=browser_session,
    )

    await agent.run()
    #await browser_session.close()

    #input('Press Enter to close...')


if __name__ == '__main__':
    asyncio.run(main())

