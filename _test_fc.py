#!/usr/bin/env python3
"""Minimal function-calling test against bailian API."""
import asyncio, json, httpx

API_KEY = "sk"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

async def test():
    tools = [{
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "add two numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["a", "b"]
            }
        }
    }]

    messages = [
        {"role": "user", "content": "What is 2+2? Use the calculator tool."}
    ]

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "qwen-plus",
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto"
            }
        )
        print("Status:", resp.status_code)
        data = resp.json()
        print("Response:", json.dumps(data.get("choices", [{}])[0].get("message", {}), indent=2, ensure_ascii=False))

        # Now send back the tool result
        tc = data["choices"][0]["message"]["tool_calls"][0]
        messages.append(data["choices"][0]["message"])
        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "tool_call_type": "function",
            "content": "4"  # result of 2+2
        })

        resp2 = await client.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "qwen-plus",
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto"
            }
        )
        print("\nTurn 2 Status:", resp2.status_code)
        data2 = resp2.json()
        print("Turn 2 Response:", json.dumps(data2.get("choices", [{}])[0].get("message", {}), indent=2, ensure_ascii=False))

asyncio.run(test())
