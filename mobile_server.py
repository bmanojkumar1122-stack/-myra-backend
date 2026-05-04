import os
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

print(f"✅ GEMINI_API_KEY loaded: {bool(GEMINI_API_KEY)}")

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
            
            # Simple response logic
            response = get_response(data)
            
            await websocket.send_text(json.dumps({
                "type": "response",
                "content": response,
                "timestamp": datetime.now().isoformat()
            }))
            
    except WebSocketDisconnect:
        print(f"🔴 Client {client_id} disconnected")
    finally:
        connected_clients.discard(websocket)

def get_response(text: str) -> str:
    """Simple response function - no async complications"""
    text_lower = text.lower().strip()
    
    print(f"Processing: {text_lower}")
    
    # Time
    if "time" in text_lower:
        return f"Current time is {datetime.now().strftime('%I:%M %p')}"
    
    # Date
    if "date" in text_lower:
        return f"Today is {datetime.now().strftime('%B %d, %Y')}"
    
    # Hello
    if "hello" in text_lower or "hi" in text_lower:
        return "Hello! Namaste! How can I help you today?"
    
    # How are you
    if "how are you" in text_lower:
        return "I'm doing great! Thanks for asking!"
    
    # Name
    if "your name" in text_lower or "who are you" in text_lower:
        return "I'm Myra AI, your voice assistant!"
    
    # Bye
    if "bye" in text_lower or "goodbye" in text_lower:
        return "Goodbye! Have a wonderful day!"
    
    # Thank you
    if "thank" in text_lower:
        return "You're welcome! Happy to help!"
    
    # Help
    if "help" in text_lower:
        return "I can tell you time, date, have conversations, and answer questions! Try saying 'hello', 'what is the time?', or 'how are you?'"
    
    # Default response for everything else
    return f"I heard: '{text}'. How can I help you?"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)