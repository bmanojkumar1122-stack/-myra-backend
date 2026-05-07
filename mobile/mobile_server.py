import os
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ========== ADD THIS SECTION FOR .env ==========
from dotenv import load_dotenv
load_dotenv()

# API keys from .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

print(f"✅ GEMINI_API_KEY loaded: {bool(GEMINI_API_KEY)}")
print(f"✅ WEATHER_API_KEY loaded: {bool(WEATHER_API_KEY)}")
print(f"✅ NEWS_API_KEY loaded: {bool(NEWS_API_KEY)}")
# ==============================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients = set()

@app.get("/")
async def root():
    return {"message": "Myra AI Mobile Backend", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy", "clients": len(connected_clients)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    client_id = id(websocket)
    
    print(f"✅ Mobile client {client_id} connected")
    
    try:
        
        while True:
            data = await websocket.receive_text()
            print(f"📝 From mobile: {data}")
            
            response = await process_command(data)
            
            await websocket.send_text(json.dumps({
                "type": "response",
                "content": response,
                "timestamp": datetime.now().isoformat()
            }))
            
    except WebSocketDisconnect:
        print(f"🔴 Client {client_id} disconnected")
    finally:
        connected_clients.discard(websocket)

# ========== UPDATED process_command with async ==========
async def process_command(text: str) -> str:
    import aiohttp
    text_lower = text.lower()
    
    # Time
    if "time" in text_lower:
        return f"Current time is {datetime.now().strftime('%I:%M %p')}"
    
    # Date
    elif "date" in text_lower:
        return f"Today is {datetime.now().strftime('%B %d, %Y')}"
    
    # Weather with API key
    elif "weather" in text_lower:
        if WEATHER_API_KEY:
            city = extract_city(text) or "Delhi"
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        temp = data['main']['temp']
                        condition = data['weather'][0]['description']
                        return f"Temperature in {city} is {temp}°C with {condition}"
                    else:
                        return f"Could not fetch weather for {city}"
        return "Weather feature needs API key. Please check .env file"
    
    # Hello
    elif any(word in text_lower for word in ["hello", "hi", "namaste"]):
        return "Hello! Namaste! How can I help you today?"
    
    # How are you
    elif "how are you" in text_lower:
        return "I'm doing great! Thanks for asking!"
    
    # Name
    elif "your name" in text_lower or "who are you" in text_lower:
        return "I'm Myra AI, your voice assistant!"
    
    # Bye
    elif "bye" in text_lower or "goodbye" in text_lower:
        return "Goodbye! Have a wonderful day!"
    
    # Help
    elif "help" in text_lower:
        return "I can tell you time, date, weather, have conversations, and answer your questions!"
    
    # Default
    else:
        return f"I heard: '{text}'. How can I help you?"

def extract_city(text: str) -> str:
    words = text.split()
    for i, word in enumerate(words):
        if word == "weather" and i + 1 < len(words):
            return words[i + 1]
    return None

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
