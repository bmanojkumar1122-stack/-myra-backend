import asyncio
import websockets
import json

async def test():
    try:
        uri = "ws://localhost:8001/ws"
        print(f"Connecting to {uri}...")
        
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            
            # Send message
            await websocket.send("Hello")
            print("📤 Sent: Hello")
            
            # Receive response
            response = await websocket.recv()
            print(f"📥 Received: {response}")
            
            # Parse JSON
            data = json.loads(response)
            print(f"💬 Response: {data.get('content')}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(test())