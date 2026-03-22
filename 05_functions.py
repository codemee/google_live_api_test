import asyncio
import pyaudio
from google import genai
from dotenv import load_dotenv
from typing import Callable
# 搭配非同步機制讓使用者輸入提示
from aioconsole import ainput

from lib.city import get_current_city_name
from lib.weather import get_feels_like_celsius

load_dotenv()

client = genai.Client()

functions = [ # 要當成工具的自訂函式
    get_current_city_name,
    get_feels_like_celsius,
]

MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": "使用繁體中文回答。",
    "output_audio_transcription": {}, # 取得生成語音的文字 
    "input_audio_transcription": {},  # 取得音訊輸入轉文字
    "tools": functions + [{'google_search': {}}],
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

async def send_realtime(live_session):
    """從輸入音訊佇列取出資料送出"""

    while True:
        msg = await audio_queue_mic.get()
        await live_session.send_realtime_input(audio=msg)

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

async def input_loop(live_session: genai.live.AsyncSession):
    while True:
        prompt = await ainput("")
        await live_session.send_realtime_input(text=prompt)

async def call_tools(
    functions: list[Callable[[dict], str]],
    live_session: genai.live.AsyncSession, 
    tool_call: genai.types.ToolCall
):
    fn_responses = []
    # Live API 不支援自動叫用函式，因此需要手動叫用
    for fn in tool_call.function_calls:
        fn_name = fn.name
        fn_args = fn.args
        print(f"\n{fn_name}(**{fn_args})", end="", flush=True)
        for function in functions:
            if function.__name__ == fn_name:
                result = function(**fn_args)
                fn_responses.append(
                    genai.types.FunctionResponse(
                        id=fn.id,
                        name=fn_name,
                        response={
                            "result": result,
                        },
                    )
                )
                break
    if fn_responses:
        await live_session.send_tool_response(
            function_responses=fn_responses,
        )
    
async def message_loop(live_session: genai.live.AsyncSession):
    while True:
        text = ""
        async for message in live_session.receive():
            if message.tool_call:
                await call_tools(
                    functions, 
                    live_session, 
                    message.tool_call
                )
                continue

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
            elif content.input_transcription: # 音訊輸入轉文字
                print(
                    content.input_transcription.text,
                    end="",
                    flush=True
                )
            elif content.output_transcription:
                if not text: print("\n") # 輸出生成內容前先換行
                text += content.output_transcription.text
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
                text = ""

async def main():
    try:
        async with client.aio.live.connect(
            model=MODEL, config=CONFIG
        ) as live_session:
            print("已連線。\n> ", end="", flush=True)
            async with asyncio.TaskGroup() as tg:
                tg.create_task(message_loop(live_session))
                tg.create_task(input_loop(live_session))
                tg.create_task(play_audio())
                tg.create_task(listen_audio())
                tg.create_task(send_realtime(live_session))
    except asyncio.CancelledError:
        pass
    finally:
        if audio_stream:
            audio_stream.close()
        pya.terminate()
        print("\n\n程式結束")

if __name__ == "__main__":
    asyncio.run(main())