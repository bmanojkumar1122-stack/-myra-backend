# =========================
# MYRA SERVER - FIXED VERSION
# =========================

import sys
import os
import json
import signal
import asyncio
import socketio
import uvicorn
import traceback

from fastapi import FastAPI
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime

# =========================
# WINDOWS ASYNCIO FIX
# =========================
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# =========================
# IMPORTS
# =========================
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import ada

from authenticator import FaceAuthenticator
from kasa_agent import KasaAgent
from web_agent_view import router as web_agent_router
from command_view import router as command_router_view
from app_indexer import get_indexer
from command_router import get_command_router
from memory_initializer import MemoryInitializer
from memory_manager import get_memory_manager

# =========================
# SOCKET SERVER
# =========================
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"
)

# =========================
# GLOBALS
# =========================
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
    },

    "printers": [],
    "kasa_devices": []
}

SETTINGS = DEFAULT_SETTINGS.copy()

# =========================
# SETTINGS
# =========================
def load_settings():
    global SETTINGS

    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                loaded = json.load(f)

            for k, v in loaded.items():

                if k == "tool_permissions":
                    SETTINGS["tool_permissions"].update(v)

                else:
                    SETTINGS[k] = v

            print("[SETTINGS] Loaded")

    except Exception as e:
        print(f"[SETTINGS] Load Error: {e}")


def save_settings():
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(SETTINGS, f, indent=4)

        print("[SETTINGS] Saved")

    except Exception as e:
        print(f"[SETTINGS] Save Error: {e}")


load_settings()

# =========================
# KASA
# =========================
kasa_agent = KasaAgent(
    known_devices=SETTINGS.get("kasa_devices", [])
)

# =========================
# SIGNAL HANDLER
# =========================
def signal_handler(sig, frame):
    global audio_loop

    print(f"\n[SERVER] Signal {sig}")

    try:
        if audio_loop:
            audio_loop.stop()

    except:
        pass

    os._exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# =========================
# FASTAPI LIFESPAN
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):

    global memory_initializer
    global memory_manager

    print("[SERVER] Starting...")

    try:
        await kasa_agent.initialize()
        print("[SERVER] Kasa Initialized")

    except Exception as e:
        print(f"[KASA] Init Error: {e}")

    try:
        memory_initializer = MemoryInitializer()
        memory_manager = get_memory_manager()

        startup_info = memory_initializer.initialize_on_startup()

        print("[MEMORY] Initialized")
        print(startup_info)

    except Exception as e:
        print(f"[MEMORY] Error: {e}")

    try:
        get_command_router()
    except:
        pass

    yield

    print("[SERVER] Shutdown")


# =========================
# APP
# =========================
app = FastAPI(lifespan=lifespan)

app_socketio = socketio.ASGIApp(
    sio,
    app
)

# =========================
# ROUTERS
# =========================
app.include_router(web_agent_router)
app.include_router(command_router_view)

# =========================
# STATUS
# =========================
@app.get("/status")
async def status():
    return {
        "status": "running",
        "service": "MYRA Backend"
    }

# =========================
# CONNECT
# =========================
@sio.event
async def connect(sid, environ):

    global authenticator

    print(f"[CLIENT] Connected: {sid}")

    await sio.emit(
        "status",
        {"msg": "Connected to MYRA"},
        room=sid
    )

    async def on_auth_status(is_auth):
        await sio.emit(
            "auth_status",
            {"authenticated": is_auth}
        )

    async def on_auth_frame(frame):
        await sio.emit(
            "auth_frame",
            {"image": frame}
        )

    if authenticator is None:

        authenticator = FaceAuthenticator(
            reference_image_path="reference.jpg",
            on_status_change=on_auth_status,
            on_frame=on_auth_frame
        )

    if SETTINGS["face_auth_enabled"]:

        if authenticator.authenticated:

            await sio.emit(
                "auth_status",
                {"authenticated": True}
            )

        else:

            await sio.emit(
                "auth_status",
                {"authenticated": False}
            )

            asyncio.create_task(
                authenticator.start_authentication_loop()
            )

    else:

        await sio.emit(
            "auth_status",
            {"authenticated": True}
        )

# =========================
# DISCONNECT
# =========================
@sio.event
async def disconnect(sid):
    print(f"[CLIENT] Disconnected: {sid}")

# =========================
# START AUDIO
# =========================
@sio.event
async def start_audio(sid, data=None):

    global audio_loop
    global loop_task

    try:

        if SETTINGS["face_auth_enabled"]:

            if authenticator and not authenticator.authenticated:

                await sio.emit(
                    "error",
                    {"msg": "Authentication Required"}
                )

                return

        if audio_loop:

            if loop_task and (
                loop_task.done() or loop_task.cancelled()
            ):

                audio_loop = None
                loop_task = None

            else:

                await sio.emit(
                    "status",
                    {"msg": "MYRA Already Running"}
                )

                return

        device_index = None
        device_name = None

        if data:

            device_index = data.get("device_index")
            device_name = data.get("device_name")

        print(f"[AUDIO] Device: {device_name}")

        # =========================
        # CALLBACKS
        # =========================

        def on_audio_data(data_bytes):
            asyncio.create_task(
                sio.emit(
                    "audio_data",
                    {"data": list(data_bytes)}
                )
            )

        def on_transcription(data):

            sender = data.get("sender")
            text = data.get("text")

            if sender not in ["User", "ADA"]:
                return

            if not text:
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
                    {"msg": msg}
                )
            )

        def on_tool_confirmation(data):

            if SETTINGS["auto_confirm_tools"]:

                try:
                    audio_loop.resolve_tool_confirmation(
                        data.get("id"),
                        True
                    )

                except Exception as e:
                    print(e)

            else:

                asyncio.create_task(
                    sio.emit(
                        "tool_confirmation_request",
                        data
                    )
                )

        # =========================
        # AUDIO LOOP
        # =========================
        audio_loop = ada.AudioLoop(
            video_mode="none",

            on_audio_data=on_audio_data,
            on_transcription=on_transcription,
            on_tool_confirmation=on_tool_confirmation,
            on_error=on_error,

            input_device_index=device_index,
            input_device_name=device_name,

            kasa_agent=kasa_agent
        )

        audio_loop.update_permissions(
            SETTINGS["tool_permissions"]
        )

        if data and data.get("muted", False):
            audio_loop.set_paused(True)

        loop_task = asyncio.create_task(
            audio_loop.run()
        )

        def loop_done(task):

            try:
                task.result()

            except asyncio.CancelledError:
                print("[AUDIO] Cancelled")

            except Exception as e:
                print(f"[AUDIO] Crash: {e}")
                traceback.print_exc()

        loop_task.add_done_callback(loop_done)

        await sio.emit(
            "status",
            {"msg": "MYRA Started"}
        )

    except Exception as e:

        traceback.print_exc()

        await sio.emit(
            "error",
            {"msg": str(e)}
        )

        audio_loop = None

# =========================
# STOP AUDIO
# =========================
@sio.event
async def stop_audio(sid):

    global audio_loop

    try:

        if audio_loop:

            audio_loop.stop()
            audio_loop = None

            await sio.emit(
                "status",
                {"msg": "MYRA Stopped"}
            )

    except Exception as e:
        print(e)

# =========================
# PAUSE
# =========================
@sio.event
async def pause_audio(sid):

    if audio_loop:

        audio_loop.set_paused(True)

        await sio.emit(
            "status",
            {"msg": "Audio Paused"}
        )

# =========================
# RESUME
# =========================
@sio.event
async def resume_audio(sid):

    if audio_loop:

        audio_loop.set_paused(False)

        await sio.emit(
            "status",
            {"msg": "Audio Resumed"}
        )

# =========================
# USER INPUT
# =========================
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

        print(f"[USER] {text}")

        await audio_loop.session.send(
            input=text,
            end_of_turn=True
        )

    except Exception as e:
        print(f"[INPUT ERROR] {e}")

# =========================
# VIDEO FRAME
# =========================
@sio.event
async def video_frame(sid, data):

    image_data = data.get("image")

    if image_data and audio_loop:

        asyncio.create_task(
            audio_loop.send_frame(image_data)
        )

# =========================
# TOOL CONFIRM
# =========================
@sio.event
async def confirm_tool(sid, data):

    request_id = data.get("id")
    confirmed = data.get("confirmed", False)

    if audio_loop:

        audio_loop.resolve_tool_confirmation(
            request_id,
            confirmed
        )

# =========================
# SETTINGS
# =========================
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

        SETTINGS["face_auth_enabled"] = data[
            "face_auth_enabled"
        ]

    if "camera_flipped" in data:

        SETTINGS["camera_flipped"] = data[
            "camera_flipped"
        ]

    if "auto_confirm_tools" in data:

        SETTINGS["auto_confirm_tools"] = data[
            "auto_confirm_tools"
        ]

    save_settings()

    await sio.emit(
        "settings",
        SETTINGS
    )

# =========================
# SHUTDOWN
# =========================
@sio.event
async def shutdown(sid, data=None):

    global audio_loop
    global loop_task
    global authenticator

    print("[SERVER] Shutdown Request")

    try:

        if audio_loop:
            audio_loop.stop()

        if loop_task and not loop_task.done():
            loop_task.cancel()

        if authenticator:
            authenticator.stop()

    except:
        pass

    os._exit(0)

# =========================
# RUN
# =========================
if __name__ == "__main__":

    uvicorn.run(
        "server:app_socketio",

        host="127.0.0.1",
        port=8000,

        reload=False,
        loop="asyncio",

        reload_excludes=[
            "temp_cad_gen.py",
            "*.stl"
        ]
    )
