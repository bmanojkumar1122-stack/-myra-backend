import os
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

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
    return {"message": "Myra AI Backend", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy", "clients": len(connected_clients)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    print(f"✅ Client {id(websocket)} connected")
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"📝 From client: {data}")
            
            # Process message and generate response
            text = data.lower().strip()
            
            if any(word in text for word in ["hello", "hi", "namaste"]):
                response = "Hello! Namaste! How can I help you today?"
            elif "time" in text:
                response = f"The current time is {datetime.now().strftime('%I:%M %p')}"
            elif "date" in text:
                response = f"Today's date is {datetime.now().strftime('%B %d, %Y')}"
            elif "your name" in text or "who are you" in text:
                response = "I'm Myra AI, your voice assistant!"
            elif "how are you" in text:
                response = "I'm doing great! Thanks for asking!"
            elif "bye" in text or "goodbye" in text:
                response = "Goodbye! Have a wonderful day!"
            elif "thank" in text:
                response = "You're welcome! Happy to help!"
            elif "help" in text:
                response = "I can tell you time, date, and answer your questions! Try saying 'hello', 'what is the time?', or 'how are you?'"
            else:
                response = f"I heard: '{data}'. How can I help you?"
            
            print(f"📤 Sending: {response}")
            await websocket.send_text(response)
            
    except WebSocketDisconnect:
        print(f"🔴 Client disconnected")
    finally:
        connected_clients.discard(websocket)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)