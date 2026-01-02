import asyncio
from google import genai
import pyaudio
from dotenv import load_dotenv
import os

# 測試 function calling 用的函式
from lib.city import get_current_city_name
from lib.weather import get_feels_like_celsius
from google.genai import types

# 載入環境變數
load_dotenv()

# 從環境變數讀取 Gemini API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("請設定 GEMINI_API_KEY 環境變數或在 .env 檔案中設定")

client = genai.Client(api_key=api_key)

# --- pyaudio config ---
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

pya = pyaudio.PyAudio()

# --- Live API config ---
MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": "使用繁體中文以及台灣慣用詞語回答。",
    "output_audio_transcription": {}, # 取得 GenAI 的音訊輸出轉文字
    "input_audio_transcription": {},  # 取得使用者音訊輸入轉文字,
    # 可以直接傳入函式，但 Live API 不支援自動叫用函式
    # 至少省掉建立函式宣告物件的麻煩，但仍需要手動叫用
    "tools": [
        get_current_city_name,
        get_feels_like_celsius,
        types.Tool(google_search=types.GoogleSearch())    ],
}

audio_queue_output = asyncio.Queue()
audio_queue_mic = asyncio.Queue(maxsize=5)
audio_stream = None

async def listen_audio():
    """監聽收取語音輸入並推入音訊佇列"""
    global audio_stream
    mic_info = pya.get_default_input_device_info()
    # 建立可用預設的輸入裝置讀取語音輸入的串流物件
    audio_stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=SEND_SAMPLE_RATE,
        input=True,
        input_device_index=mic_info["index"],
        frames_per_buffer=CHUNK_SIZE,
    )
    # 設定串流物件的讀取參數
    kwargs = {"exception_on_overflow": False} if __debug__ else {}

    while True:
        # 讀取串流物件的音訊資料
        data = await asyncio.to_thread(
            audio_stream.read, 
            CHUNK_SIZE, 
            **kwargs
        )
        # 將讀取到的音訊資料推入 mic 音訊佇列
        await audio_queue_mic.put(
            {
                "data": data, 
                "mime_type": "audio/pcm"
            }
        )

async def send_realtime(session):
    """從音訊佇列取出資料送至 GenAI ession"""
    while True:
        msg = await audio_queue_mic.get()
        await session.send_realtime_input(audio=msg)

async def receive_audio(session):
    """從 GenAI 收取音訊資料推入播放佇列"""
    while True:
        turn = session.receive()
        audio_input = None
        async for response in turn:
            if response.tool_call:
                fn_responses = []
                # Live API 不支援自動叫用函式，因此需要手動叫用
                for fn in response.tool_call.function_calls:
                    fn_name = fn.name
                    fn_args = fn.args
                    print(f"{fn_name}(**{fn_args})")
                    fn_responses.append(genai.types.FunctionResponse(
                        id=fn.id,
                        name=fn_name,
                        response={
                            "result": eval(f"{fn_name}(**{fn_args})"),
                        },
                    ))
                await session.send_tool_response(
                    function_responses=fn_responses,
                )
                continue
            content = response.server_content
            if not content:
                continue
            if content.model_turn:
                # 遍歷音訊資料的每一個部分並推入播放佇列
                for part in content.model_turn.parts:
                    if not part.inline_data:
                        continue
                    if isinstance(part.inline_data.data, bytes):
                        audio_input = part.inline_data.data
                        audio_queue_output.put_nowait(audio_input)
            elif content.output_transcription: # 收到 GenAI 音訊輸出轉文字
                print(f"{content.output_transcription.text}", end="", flush=True)
            elif content.input_transcription: # 收到使用者音訊輸入轉文字
                print(f"<-: {content.input_transcription.text}\n->:", end="", flush=True)
            if content.generation_complete or content.interrupted:
                print("\n", end="", flush=True)

        # 如果有新的音訊輸入就清空播放佇列停止播放尚未播完的音訊
        if audio_input:
            while not audio_queue_output.empty():
                audio_queue_output.get_nowait()

async def play_audio():
    """從播放佇列取出音訊資料播放"""
    # 建立可用預設的輸出裝置播放音訊輸出的串流物件
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

async def run():
    """連線至 GenAI 並建立個別任務執行"""
    try:
        async with client.aio.live.connect(
            model=MODEL, config=CONFIG
        ) as live_session:
            print("Connected to Gemini. Start speaking!")
            async with asyncio.TaskGroup() as tg:
                tg.create_task(send_realtime(live_session))
                tg.create_task(listen_audio())
                tg.create_task(receive_audio(live_session))
                tg.create_task(play_audio())
    except asyncio.CancelledError:
        pass
    finally:
        if audio_stream:
            audio_stream.close()
        pya.terminate()
        print("\nConnection closed.")

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Interrupted by user.")
