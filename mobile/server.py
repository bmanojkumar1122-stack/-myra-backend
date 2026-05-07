import sys
import asyncio
import os
import json
import base64
import signal
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

# ================= WINDOWS ASYNCIO FIX =================
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsProactorEventLoopPolicy()
    )

# ================= IMPORTS =================
import socketio
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# ================= LOCAL IMPORTS =================
sys.path.append(
    os.path.dirname(os.path.abspath(__file__))
)

import ada
from authenticator import FaceAuthenticator
from kasa_agent import KasaAgent
from web_agent_view import router as web_agent_router
from command_view import router as command_router_view
from app_indexer import get_indexer
from command_router import get_command_router
from memory_initializer import MemoryInitializer
from memory_manager import get_memory_manager

# ================= SOCKET.IO =================
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"
)

# ================= GLOBALS =================
audio_loop = None
loop_task = None
authenticator = None
memory_initializer = None
memory_manager = None

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "face_auth_enabled": False,
    "camera_flipped": False,
    "auto_confirm_tools": False,
    "printers": [],
    "kasa_devices": [],
    "tool_permissions": {
        "generate_cad": True,
        "run_web_agent": True,
        "write_file": True,
        "read_directory": True,
        "read_file": True,
        "create_project": True,
        "switch_project": True,
        "list_projects": True,
        "system_control": True,
        "screen_access": True,
        "file_access": True
    }
}

SETTINGS = DEFAULT_SETTINGS.copy()

# ================= LOAD SETTINGS =================
def load_settings():
    global SETTINGS

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(
                SETTINGS_FILE,
                "r",
                encoding="utf-8"
            ) as f:
                loaded = json.load(f)

            for k, v in loaded.items():
                if (
                    k == "tool_permissions"
                    and isinstance(v, dict)
                ):
                    SETTINGS["tool_permissions"].update(v)
                else:
                    SETTINGS[k] = v

            print("✅ Settings loaded")

        except Exception as e:
            print(f"❌ Settings load error: {e}")

# ================= SAVE SETTINGS =================
def save_settings():
    try:
        with open(
            SETTINGS_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                SETTINGS,
                f,
                indent=4
            )

        print("✅ Settings saved")

    except Exception as e:
        print(f"❌ Settings save error: {e}")

load_settings()

# ================= KASA =================
kasa_agent = KasaAgent(
    known_devices=SETTINGS.get(
        "kasa_devices",
        []
    )
)

# ================= SHUTDOWN HANDLER =================
def signal_handler(sig, frame):
    global audio_loop

    print("\n[SERVER] Shutdown signal received")

    try:
        if audio_loop:
            audio_loop.stop()
    except:
        pass

    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ================= FASTAPI LIFESPAN =================
@asynccontextmanager
async def lifespan(app: FastAPI):

    global memory_initializer
    global memory_manager

    print("🚀 MYRA Backend Starting")

    try:
        await kasa_agent.initialize()

        memory_initializer = MemoryInitializer()
        memory_manager = get_memory_manager()

        startup_info = (
            memory_initializer.initialize_on_startup()
        )

        print(
            f"✅ Memory Initialized: {startup_info}"
        )

    except Exception as e:
        print(f"❌ Startup error: {e}")

    try:
        await asyncio.to_thread(
            get_indexer().build_index
        )

        print("✅ App Index Built")

    except Exception as e:
        print(f"❌ App Index Error: {e}")

    try:
        get_command_router()
    except:
        pass

    yield

    print("🛑 Server shutting down")

# ================= FASTAPI APP =================
app = FastAPI(
    lifespan=lifespan
)

app_socketio = socketio.ASGIApp(
    sio,
    app
)

# ================= ROUTERS =================
app.include_router(web_agent_router)
app.include_router(command_router_view)

# ================= STATUS =================
@app.get("/status")
async def status():
    return {
        "status": "running",
        "service": "MYRA Backend"
    }

# ================= SOCKET CONNECT =================
@sio.event
async def connect(sid, environ):

    global authenticator

    print(f"✅ Client connected: {sid}")

    await sio.emit(
        "status",
        {
            "msg": "Connected to MYRA Backend"
        },
        room=sid
    )

    async def on_auth_status(is_auth):
        await sio.emit(
            "auth_status",
            {
                "authenticated": is_auth
            }
        )

    async def on_auth_frame(frame_b64):
        await sio.emit(
            "auth_frame",
            {
                "image": frame_b64
            }
        )

    if authenticator is None:
        authenticator = FaceAuthenticator(
            reference_image_path="reference.jpg",
            on_status_change=on_auth_status,
            on_frame=on_auth_frame
        )

    if authenticator.authenticated:
        await sio.emit(
            "auth_status",
            {
                "authenticated": True
            }
        )

    else:

        if SETTINGS.get(
            "face_auth_enabled",
            False
        ):

            await sio.emit(
                "auth_status",
                {
                    "authenticated": False
                }
            )

            asyncio.create_task(
                authenticator.start_authentication_loop()
            )

        else:

            await sio.emit(
                "auth_status",
                {
                    "authenticated": True
                }
            )

# ================= SOCKET DISCONNECT =================
@sio.event
async def disconnect(sid):
    print(f"❌ Client disconnected: {sid}")

# ================= START AUDIO =================
@sio.event
async def start_audio(sid, data=None):

    global audio_loop
    global loop_task

    print("🎤 Starting MYRA Audio")

    if audio_loop:
        await sio.emit(
            "status",
            {
                "msg": "MYRA already running"
            }
        )
        return

    device_index = None
    device_name = None

    if data:
        device_index = data.get("device_index")
        device_name = data.get("device_name")

    # ================= CALLBACKS =================
    def on_audio_data(data_bytes):
        asyncio.create_task(
            sio.emit(
                "audio_data",
                {
                    "data": list(data_bytes)
                }
            )
        )

    def on_transcription(data):

        sender = data.get("sender")
        text = data.get("text")

        if sender not in ["User", "ADA"]:
            return

        asyncio.create_task(
            sio.emit(
                "transcription",
                {
                    "sender": sender,
                    "text": text
                }
            )
        )

    def on_error(msg):
        asyncio.create_task(
            sio.emit(
                "error",
                {
                    "msg": msg
                }
            )
        )

    try:

        audio_loop = ada.AudioLoop(
            video_mode="none",
            on_audio_data=on_audio_data,
            on_transcription=on_transcription,
            on_error=on_error,
            input_device_index=device_index,
            input_device_name=device_name,
            kasa_agent=kasa_agent
        )

        audio_loop.update_permissions(
            SETTINGS["tool_permissions"]
        )

        loop_task = asyncio.create_task(
            audio_loop.run()
        )

        await sio.emit(
            "status",
            {
                "msg": "MYRA Started"
            }
        )

        print("✅ Audio loop started")

    except Exception as e:

        print(f"❌ Audio start error: {e}")

        await sio.emit(
            "error",
            {
                "msg": str(e)
            }
        )

# ================= STOP AUDIO =================
@sio.event
async def stop_audio(sid):

    global audio_loop

    if audio_loop:

        audio_loop.stop()
        audio_loop = None

        await sio.emit(
            "status",
            {
                "msg": "MYRA stopped"
            }
        )

# ================= USER INPUT =================
@sio.event
async def user_input(sid, data):

    text = data.get("text")

    if not text:
        return

    if not audio_loop:
        return

    if not audio_loop.session:
        return

    try:

        print(f"👤 User: {text}")

        await audio_loop.session.send(
            input=text,
            end_of_turn=True
        )

    except Exception as e:
        print(f"❌ User input error: {e}")

# ================= VIDEO FRAME =================
@sio.event
async def video_frame(sid, data):

    image_data = data.get("image")

    if image_data and audio_loop:
        asyncio.create_task(
            audio_loop.send_frame(image_data)
        )

# ================= SETTINGS =================
@sio.event
async def get_settings(sid):

    await sio.emit(
        "settings",
        SETTINGS
    )

@sio.event
async def update_settings(sid, data):

    if "tool_permissions" in data:

        SETTINGS["tool_permissions"].update(
            data["tool_permissions"]
        )

        if audio_loop:
            audio_loop.update_permissions(
                SETTINGS["tool_permissions"]
            )

    if "face_auth_enabled" in data:
        SETTINGS["face_auth_enabled"] = (
            data["face_auth_enabled"]
        )

    if "camera_flipped" in data:
        SETTINGS["camera_flipped"] = (
            data["camera_flipped"]
        )

    if "auto_confirm_tools" in data:
        SETTINGS["auto_confirm_tools"] = (
            data["auto_confirm_tools"]
        )

    save_settings()

    await sio.emit(
        "settings",
        SETTINGS
    )

# ================= MEMORY =================
@sio.event
async def save_memory(sid, data):

    global memory_manager

    if not memory_manager:
        return

    text = data.get("text")

    if not text:
        return

    try:

        memory_manager.add_fact(text)

        await sio.emit(
            "memory_saved",
            {
                "success": True,
                "text": text
            }
        )

    except Exception as e:

        await sio.emit(
            "error",
            {
                "msg": str(e)
            }
        )

# ================= GET MEMORY =================
@sio.event
async def get_memory(sid):

    global memory_manager

    if not memory_manager:
        return

    try:

        memory = (
            memory_manager.get_permanent_memory()
        )

        await sio.emit(
            "memory_data",
            memory
        )

    except Exception as e:

        await sio.emit(
            "error",
            {
                "msg": str(e)
            }
        )

# ================= ANDROID WEBSOCKET =================
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket
):

    await websocket.accept()

    print("✅ Android connected")

    try:

        while True:

            data = await websocket.receive_text()

            print(f"📩 Android: {data}")

            text_lower = data.lower()

            # ================= AI RESPONSES =================
            if (
                "hello" in text_lower
                or "hi" in text_lower
            ):

                response = (
                    "Hello! Namaste! "
                    "How are you?"
                )

            elif "how are you" in text_lower:

                response = (
                    "I'm doing great!"
                )

            elif "name" in text_lower:

                response = (
                    "I'm Myra AI from ADA V2"
                )

            elif "bye" in text_lower:

                response = (
                    "Goodbye! Have a great day!"
                )

            else:

                response = (
                    f"Myra AI received: {data}"
                )

            # ================= AUDIO =================
            audio_base64 = ""

            try:

                with open(
                    "kore_voice.wav",
                    "rb"
                ) as audio_file:

                    audio_base64 = (
                        base64.b64encode(
                            audio_file.read()
                        ).decode("utf-8")
                    )

            except Exception as e:
                print(f"Audio error: {e}")

            # ================= SEND RESPONSE =================
            await websocket.send_text(
                json.dumps({
                    "type": "response",
                    "content": response,
                    "audio": audio_base64
                })
            )

    except WebSocketDisconnect:

        print("❌ Android disconnected")

# ================= MAIN =================
if __name__ == "__main__":

    uvicorn.run(
        "server:app_socketio",
        host="127.0.0.1",
        port=8001,
        reload=False,
        loop="asyncio"
    )
