import asyncio

from tools.echo import EchoTool
from tools.registry import DuplicateToolError, ToolNotFoundError, ToolRegistry
from tools.search.tool import SearchTool


async def main() -> None:
    registry = ToolRegistry()

    print("\n[1] Register search tool")
    registry.register(SearchTool())
    print(registry.list_tools())

    print("\n[2] Invoke search tool")
    ok_result = await registry.invoke("search", {"query": "langgraph tutorial"})
    print(ok_result)

    print("\n[3] Invoke search tool with invalid payload")
    invalid_result = await registry.invoke("search", {"query": "  "})
    print(invalid_result)

    print("\n[4] Duplicate register check")
    try:
        registry.register(SearchTool())
    except DuplicateToolError as e:
        print({"error": str(e)})

    print("\n[5] Tool not found check")
    try:
        await registry.invoke("python", {"code": "print('hello')"})
    except ToolNotFoundError as e:
        print({"error": str(e)})

    # registry echo tool
    print("\n[6] Register echo tool")
    registry.register(EchoTool())
    print(registry.list_tools())

    print("\n[7] Invoke echo tool")
    ok_result = await registry.invoke("echo", {"query": "hello world"})
    print(ok_result)

    print("\n[8] Invoke echo tool with invalid payload")
    invalid_result = await registry.invoke("echo", {"query": " "})
    print(invalid_result)

    print("\n[9] Duplicate register check")
    try:
        registry.register(EchoTool())
    except DuplicateToolError as e:
        print({"error": str(e)})

if __name__ == "__main__":
    asyncio.run(main())
