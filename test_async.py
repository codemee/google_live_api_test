import asyncio

async def message_loop():
    while True:
        await asyncio.sleep(5)
        print("Hello, World!")

async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(message_loop())
    except asyncio.CancelledError:
        print("使用者中斷程式:1")
    finally:
        print("程式結束")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("使用者中斷程式:0")
    finally:
        print("程式結束")