import os
import sys
import json
from mcp import ClientSession
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from contextlib import AsyncExitStack
from typing import Callable
from google import genai
import httpx

async_exit_stack = AsyncExitStack()

async def get_remote_mcp_session(info:dict) -> ClientSession:
    if info.pop("type", None) == "http":
        # 如果有 headers，要客製 HTTP 用戶端物件(參考 4-6 節)
        if "headers" in info:
            headers = info.pop("headers")
            async_client = httpx.AsyncClient(headers=headers)
            info["http_client"] = async_client
        read, write, _ = (
            await async_exit_stack.enter_async_context(
                streamable_http_client(**info)
            )
        )
    elif "url" in info:
        read, write = (
            await async_exit_stack.enter_async_context(
                sse_client(**info)
            )
        )
    elif "command" in info:
        stdio_server_params = StdioServerParameters(**info)
        read, write = (
            await async_exit_stack.enter_async_context(
                stdio_client(stdio_server_params)
            )
        )
    else:
        raise ValueError(f"未知的 MCP 伺服器類型: {info}")
    session = await async_exit_stack.enter_async_context(
        ClientSession(read, write)
    )
    await session.initialize()
    return session

async def load_mcp():
    sessions = []

    if (not os.path.exists("mcp_servers.json") or
        not os.path.isfile("mcp_servers.json")):
        return sessions

    with open('mcp_servers.json', 'r') as f:
        mcp_servers = json.load(f)
        try:
            server_infos = mcp_servers['mcp_servers'].items()
        except (KeyError, TypeError) as e:
            print(
                f"Error: mcp_servers.json 格式錯誤 - {e}",
                file=sys.stderr
            )
            return sessions

    for name, info in server_infos:
        print(f"啟動 MCP 伺服器 {name}...", end="")
        session = await get_remote_mcp_session(info)
        sessions.append(session)
        print(f"OK")
    return sessions

# Interactions API 專用，把 ClientSession 的物件
# 轉換成 FunctionParam 類別的字典
async def sessions_to_functions(
    sessions: list[ClientSession]
) -> list[dict]:
    functions = []
    for session in sessions:
        tools = await session.list_tools()
        for tool in tools.tools:
            print("工具：" + tool.name)
            functions.append({
                "type": "function", 
                "name": tool.name, 
                "description": tool.description, 
                "parameters": tool.inputSchema
            })
    return functions

# Interactions API 專用，把自訂函式
# 轉換成 FunctionParam 類別的字典
def tools_to_functions(
    client: genai.Client,
    tools: list[Callable[[dict], str]]
) -> list[dict]:
    functions = []
    for tool in tools:
        tool_decl = (
            genai.types.FunctionDeclaration.from_callable(
                client=client,
                callable=tool,
            )
        )
        tool_dict = tool_decl.to_json_dict()
        tool_dict["type"] = "function"
        functions.append(tool_dict)
    return functions

async def close_mcp():
    await async_exit_stack.aclose()

async def call_function(
    event: genai.interactions.InteractionSSEEvent,
    tools: list[Callable[[dict], str]],
    sessions: list[ClientSession],
):
    results = []

    # 不需要叫用函式
    if not (
        event.event_type == "content.delta" and
        event.delta.type == "function_call"
    ):
        return results
    name = event.delta.name
    args = event.delta.arguments
    result = None
    # 先檢查工具清單
    for tool in tools:
        if tool.__name__ == name:
            result = tool(**args)
            break
    # 如果沒有找到，再檢查 MCP 清單
    if result == None:
        for session in sessions:
            tool_list = await session.list_tools()
            for tool in tool_list.tools:
                if tool.name == name:
                    result = (await session.call_tool(
                        name, 
                        args
                    )).content[0].text                    
                    break
            if not result == None:
                break
    if not result == None:
        results.append({
            "type": "function_result",
            "call_id": event.delta.id,
            "name": name,
            "result": result
        })

    return results


# Live API 專用，叫用函式
async def call_tools(
    functions: list[Callable[[dict], str]],
    mcp_sessions: list[ClientSession],
    live_session: genai.live.AsyncSession, 
    tool_call: genai.types.ToolCall
):
    fn_responses = []
    # Live API 不支援自動叫用函式，因此需要手動叫用
    for fn in tool_call.function_calls:
        fn_name = fn.name
        fn_args = fn.args
        print(f"\n{fn_name}(**{fn_args})", end="", flush=True)
        result = None
        for function in functions:
            if function.__name__ == fn_name:
                result = function(**fn_args)
                break
        else:
            for mcp_session in mcp_sessions:
                tool_list = await mcp_session.list_tools()
                for tool in tool_list.tools:
                    if tool.name == fn_name:
                        result = (
                            await mcp_session.call_tool(
                                fn_name, 
                                fn_args
                        )).content[0].text
                        break
                if not result == None:
                    break
        if result == None: continue
        fn_responses.append(
            genai.types.FunctionResponse(
                id=fn.id,
                name=fn_name,
                response={
                    "output": result,
                },
            )
        )

    if fn_responses:
        await live_session.send_tool_response(
            function_responses=fn_responses,
        )

