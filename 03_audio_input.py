import asyncio
import pyaudio
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
}

# 音訊格式
FORMAT = pyaudio.paInt16     # 16 位元深度
CHANNELS = 1                 # 單聲道
RECEIVE_SAMPLE_RATE = 24000  # 輸出音訊取樣率 24KHz
SEND_SAMPLE_RATE = 16000     # 輸入音訊取樣率 16KHz
CHUNK_SIZE = 1024            # 音訊區塊大小

pya = pyaudio.PyAudio()
audio_queue_output = asyncio.Queue()       # 儲存播放音訊的佇列
audio_queue_mic = asyncio.Queue(maxsize=5) # 儲存輸入音訊的佇列
audio_stream = None

async def listen_audio():
    """收取語音輸入推入音訊佇列"""
    global audio_stream
    
    # 取得預設的輸入裝置資訊
    mic_info = pya.get_default_input_device_info()
    
    # 在單獨的執行緒中建立讀取語音輸入的串流物件
    audio_stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=SEND_SAMPLE_RATE,
        input=True,
        # 使用預設的輸入裝置
        input_device_index=mic_info["index"],
        # 設定音訊區塊大小
        frames_per_buffer=CHUNK_SIZE,
    )
    while True:
        # 讀取音訊資料
        data = await asyncio.to_thread(
            audio_stream.read, 
            CHUNK_SIZE, 
        )
        # 將讀取到的音訊資料推入輸入音訊佇列
        await audio_queue_mic.put(
            {
                "data": data, 
                "mime_type": "audio/pcm"
            }
        )

async def send_realtime(session):
    """從輸入音訊佇列取出資料送出"""

    while True:
        msg = await audio_queue_mic.get()
        await session.send_realtime_input(audio=msg)

async def play_audio():
    """從播放佇列取出音訊資料播放"""
    
    # 在單獨的執行緒中建立播放音訊的串流物件
    stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=RECEIVE_SAMPLE_RATE,
        output=True,
    )
    while True:
        bytestream = await audio_queue_output.get()
        await asyncio.to_thread(stream.write, bytestream)

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
            content = message.server_content

            if not content:
                continue

            if content.model_turn:
                # 取得音訊資料的每個區塊並推入播放佇列
                for part in content.model_turn.parts:
                    if not part.inline_data:
                        continue
                    audio_input = part.inline_data.data
                    audio_queue_output.put_nowait(audio_input)
            elif content.output_transcription:
                print(
                    f"{content.output_transcription.text}", 
                    end="", 
                    flush=True
                )            
            elif (
                content.generation_complete or # 完成生成
                content.interrupted            # 中斷生成
            ):
                # 使用者插話，清空播放佇列中斷播放
                if content.interrupted:
                    while not audio_queue_output.empty():
                        audio_queue_output.get_nowait()
                # 顯示輸入提示符號，讓使用者可以繼續輸入
                print("\n\n> ", end="", flush=True)

async def main():
    stdin_task = asyncio.create_task(stdin_loop())

    try:
        async with client.aio.live.connect(
            model=MODEL, config=CONFIG
        ) as live_session:
            print("已連線。\n> ", end="", flush=True)
            async with asyncio.TaskGroup() as tg:
                tg.create_task(message_loop(live_session))
                tg.create_task(send_loop(live_session))
                tg.create_task(play_audio())
                tg.create_task(listen_audio())
                tg.create_task(send_realtime(live_session))
    except asyncio.CancelledError:
        pass
    finally:
        if audio_stream:
            audio_stream.close()
        pya.terminate()
        stdin_task.cancel()
        print("\n\n程式結束")

if __name__ == "__main__":
    asyncio.run(main())