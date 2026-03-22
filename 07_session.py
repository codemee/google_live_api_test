import asyncio
from google import genai
from dotenv import load_dotenv
# 搭配非同步機制讓使用者輸入提示
from aioconsole import ainput

load_dotenv()

client = genai.Client()

# handle = None
handle="CihybTViNHprYndpeDdheGs3czZpaWZyb2lmaW14YXV1M252bjBtdHo2"

MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": "使用繁體中文回答。",
    "output_audio_transcription": {}, # 取得生成語音的文字
    "session_resumption" :{
        "handle": handle
    }
}

async def input_loop(live_session: genai.live.AsyncSession):
    while True:
        prompt = await ainput("")
        await live_session.send_realtime_input(text=prompt)

async def message_loop(live_session: genai.live.AsyncSession):
    global handle
    while True:
        async for message in live_session.receive():
            if message.go_away is not None:
                print(f"即將斷線，剩餘時間：{message.go_away.time_left}")
                continue
            if message.session_resumption_update:
                update = message.session_resumption_update
                if update.resumable and update.new_handle:
                    print(f"交談階段識別碼：{update.new_handle}")
                    handle = update.new_handle
                continue

            content = message.server_content
            if not content:
                continue

            if content.output_transcription:
                print(
                    f"{content.output_transcription.text}", 
                    end="", 
                    flush=True
                )            
            elif (
                content.generation_complete or # 完成生成
                content.interrupted            # 中斷生成
            ):
                # 顯示輸入提示符號，讓使用者可以繼續輸入
                print("\n\n> ", end="", flush=True)

async def main():
    try:
        async with client.aio.live.connect(
            model=MODEL, config=CONFIG
        ) as live_session:
            print("已連線。\n> ", end="", flush=True)
            async with asyncio.TaskGroup() as tg:
                tg.create_task(message_loop(live_session))
                tg.create_task(input_loop(live_session))
    except asyncio.CancelledError:
        pass
    finally:
        print("\n\n程式結束")

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        # except genai.errors.APIError as e:
        except Exception as e:
            print(f"程式錯誤：{e}")
            continue
        break