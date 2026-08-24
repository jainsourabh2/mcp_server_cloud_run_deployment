# test_client.py
"""
Test client to verify local or remote SSE Model Context Protocol Server.
"""
import asyncio
import os
import sys
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:8080/sse")


async def test_server():
    print(f"Connecting to Resy MCP SSE Server at: {SERVER_URL}")
    try:
        async with sse_client(SERVER_URL) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print(" Successfully initialized MCP session!")

                # List tools
                tools_response = await session.list_tools()
                print(f"\n Discovered {len(tools_response.tools)} MCP Tools:")
                for tool in tools_response.tools:
                    first_line = tool.description.strip().split("\n")[0] if tool.description else ""
                    print(f"  • {tool.name}: {first_line}")

                # Test search_restaurants
                print("\n Invoking tool 'search_restaurants' for 'Carbone' in 'nyc'...")
                result = await session.call_tool(
                    "search_restaurants",
                    arguments={
                        "query": "Carbone",
                        "city": "nyc",
                        "date": "2026-06-15",
                        "party_size": 2,
                    },
                )
                print("\n Tool Result:")
                for content in result.content:
                    print(content.text)

    except Exception as e:
        print(f"❌ Connection or test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_server())
