import asyncio
from google import genai
from dotenv import load_dotenv
# 搭配非同步機制讓使用者輸入提示
from aioconsole import ainput

load_dotenv()

client = genai.Client()

MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": "使用繁體中文回答。",
    "output_audio_transcription": {}, # 取得生成語音的文字
    "session_resumption" :{"handle": None}
}

input_queue = asyncio.Queue()

async def stdin_loop():
    """全程式生命週期的 stdin 讀取 task，不隨連線重啟。"""
    while True:
        prompt = await ainput("")
        await input_queue.put(prompt)


async def send_loop(live_session: genai.live.AsyncSession):
    """從共用 queue 取出輸入後送往伺服端。"""
    while True:
        prompt = await input_queue.get()
        await live_session.send_realtime_input(text=prompt)


async def message_loop(live_session: genai.live.AsyncSession):
    while True:
        async for message in live_session.receive():
            if message.go_away is not None:
                print(
                    "即將斷線，剩餘時間："
                    f"{message.go_away.time_left}"
                )
                continue
            if message.session_resumption_update:
                update = message.session_resumption_update
                if update.resumable and update.new_handle:
                    print(
                        "交談階段識別碼："
                        f"{update.new_handle}"
                    )
                    CONFIG["session_resumption"]["handle"] = (
                        update.new_handle
                    )
                continue

            content = message.server_content
            if not content:
                continue

            if content.output_transcription:
                print(
                    f"{content.output_transcription.text}",
                    end="",
                    flush=True,
                )
            elif (
                content.generation_complete or  # 完成生成
                content.interrupted             # 中斷生成
            ):
                # 顯示輸入提示符號，讓使用者可以繼續輸入
                print("\n\n> ", end="", flush=True)

async def main():
    # 在整個程式生命週期內只啟動一次，不隨連線斷開重啟，
    # 避免孤立的 stdin 執行緒在重連後吃掉第一次 Enter 輸入。
    stdin_task = asyncio.create_task(stdin_loop())

    try:
        while True:
            try:
                async with client.aio.live.connect(
                    model=MODEL, config=CONFIG
                ) as live_session:
                    print("已連線。\n> ", end="", flush=True)
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(
                            message_loop(live_session)
                        )
                        tg.create_task(send_loop(live_session))
            except ExceptionGroup as e:
                print(f"強制斷線：{e.message}")
                continue
            except asyncio.CancelledError:
                pass
            break
    finally:
        stdin_task.cancel()
        print("\n\n程式結束")

if __name__ == "__main__":
    asyncio.run(main())