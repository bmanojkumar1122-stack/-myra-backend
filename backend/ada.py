import asyncio
import base64
import io
import os
import sys
import traceback
from dotenv import load_dotenv
import cv2
import pyaudio
import PIL.Image
import mss
import argparse
import math
import struct
import time
from datetime import datetime, timedelta

from google import genai
from google.genai import types

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

from tools import tools_list
from system_agent import get_system_agent
from trusted_permissions import get_trusted_manager
from voice_intent_parser import handle_voice_intent
from whatsapp_agent import get_whatsapp_agent
from media_controller import MediaController
from camera_module import get_camera_module
from emotion.emotion_engine import EmotionEngine
from emotion.response_adapter import ResponseStyleAdapter

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_MODE = "camera"

load_dotenv()
client = genai.Client(http_options={"api_version": "v1beta"}, api_key=os.getenv("GEMINI_API_KEY"))

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# ================= FASTAPI =================

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.get("/")
async def root():
    return {
        "status": "MYRA Backend Running"
    }

@app.get("/health")
async def health():
    return {
        "status": "OK"
    }

@app.post("/chat")
async def chat(req: ChatRequest):

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=req.message
        )

        return {
            "reply": response.text
        }

    except Exception as e:
        return {
            "error": str(e)
        }
# ========== TOOL: Get Current Time in IST ==========
get_current_time_tool = {
    "name": "get_current_time",
    "description": "Returns the current time in Indian Standard Time (IST, UTC+5:30). Use this when user asks for the time.",
    "parameters": {"type": "OBJECT", "properties": {}, "required": []}
}

# ========== ALL TOOLS ==========
generate_cad = {
    "name": "generate_cad",
    "description": "Generates a 3D CAD model based on a prompt.",
    "parameters": {"type": "OBJECT", "properties": {"prompt": {"type": "STRING"}}, "required": ["prompt"]},
    "behavior": "NON_BLOCKING"
}

run_web_agent = {
    "name": "run_web_agent",
    "description": "Opens a web browser and performs a task.",
    "parameters": {"type": "OBJECT", "properties": {"prompt": {"type": "STRING"}}, "required": ["prompt"]},
    "behavior": "NON_BLOCKING"
}

create_project_tool = {
    "name": "create_project",
    "description": "Creates a new project folder.",
    "parameters": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}}, "required": ["name"]}
}

switch_project_tool = {
    "name": "switch_project",
    "description": "Switches the current active project context.",
    "parameters": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}}, "required": ["name"]}
}

list_projects_tool = {
    "name": "list_projects",
    "description": "Lists all available projects.",
    "parameters": {"type": "OBJECT", "properties": {}}
}

list_smart_devices_tool = {
    "name": "list_smart_devices",
    "description": "Lists all available smart home devices.",
    "parameters": {"type": "OBJECT", "properties": {}}
}

control_light_tool = {
    "name": "control_light",
    "description": "Controls a smart light device.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {"type": "STRING"},
            "action": {"type": "STRING"},
            "brightness": {"type": "INTEGER"},
            "color": {"type": "STRING"}
        },
        "required": ["target", "action"]
    }
}

discover_printers_tool = {
    "name": "discover_printers",
    "description": "Discovers 3D printers on the local network.",
    "parameters": {"type": "OBJECT", "properties": {}}
}

print_stl_tool = {
    "name": "print_stl",
    "description": "Prints an STL file to a 3D printer.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "stl_path": {"type": "STRING"},
            "printer": {"type": "STRING"},
            "profile": {"type": "STRING"}
        },
        "required": ["stl_path", "printer"]
    }
}

get_print_status_tool = {
    "name": "get_print_status",
    "description": "Gets the current status of a 3D printer.",
    "parameters": {"type": "OBJECT", "properties": {"printer": {"type": "STRING"}}, "required": ["printer"]}
}

iterate_cad_tool = {
    "name": "iterate_cad",
    "description": "Modifies the current CAD design.",
    "parameters": {"type": "OBJECT", "properties": {"prompt": {"type": "STRING"}}, "required": ["prompt"]},
    "behavior": "NON_BLOCKING"
}

whatsapp_control_tool = {
    "name": "whatsapp_control",
    "description": "Controls WhatsApp messaging and calls.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING"},
            "contact": {"type": "STRING"},
            "message": {"type": "STRING"}
        },
        "required": ["action", "contact"]
    },
    "behavior": "NON_BLOCKING"
}

media_play_tool = {
    "name": "media_play",
    "description": "Controls media playback on YouTube and Spotify.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "platform": {"type": "STRING"},
            "query": {"type": "STRING"}
        },
        "required": ["platform", "query"]
    },
    "behavior": "NON_BLOCKING"
}

screen_read_tool = {
    "name": "screen_read",
    "description": "Capture camera view and describe what MYRA sees.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "analyze_details": {"type": "BOOLEAN"},
            "read_aloud": {"type": "BOOLEAN"}
        },
        "required": []
    },
    "behavior": "NON_BLOCKING"
}

# Tools list
tools = [{'google_search': {}}, {"function_declarations": [
    get_current_time_tool, generate_cad, run_web_agent, create_project_tool,
    switch_project_tool, list_projects_tool, list_smart_devices_tool,
    control_light_tool, discover_printers_tool, print_stl_tool,
    get_print_status_tool, iterate_cad_tool, whatsapp_control_tool,
    media_play_tool, screen_read_tool
] + tools_list[0]['function_declarations'][1:]}]

# Config
config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    output_audio_transcription={},
    input_audio_transcription={},
    system_instruction="""
Your name is MYRA.
Created by MANOJ BEHERA.

Address Manoj randomly using affectionate names like:
'jaan', 'babu', 'baby', 'boss'.

Do NOT repeat the same nickname every time.
Use a natural conversational style.

Always use Indian Standard Time (IST).
""",

    tools=tools,
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
        )
    )
)

pya = pyaudio.PyAudio()

from cad_agent import CadAgent
from web_agent import WebAgent
from kasa_agent import KasaAgent
from printer_agent import PrinterAgent

class AudioLoop:
    def __init__(self, video_mode=DEFAULT_MODE, on_audio_data=None, on_video_frame=None,
                 on_cad_data=None, on_web_data=None, on_transcription=None,
                 on_tool_confirmation=None, on_cad_status=None, on_cad_thought=None,
                 on_project_update=None, on_device_update=None, on_assistant_speaking=None,
                 on_error=None, input_device_index=None, input_device_name=None,
                 output_device_index=None, kasa_agent=None, on_system_data=None,
                 on_emotion_update=None):
        
        self.video_mode = video_mode
        self.on_audio_data = on_audio_data
        self.on_video_frame = on_video_frame
        self.on_cad_data = on_cad_data
        self.on_web_data = on_web_data
        self.on_transcription = on_transcription
        self.on_tool_confirmation = on_tool_confirmation
        self.on_cad_status = on_cad_status
        self.on_cad_thought = on_cad_thought
        self.on_project_update = on_project_update
        self.on_device_update = on_device_update
        self.on_assistant_speaking = on_assistant_speaking
        self.on_error = on_error
        self.on_system_data = on_system_data
        self.on_emotion_update = on_emotion_update
        self.input_device_index = input_device_index
        self.input_device_name = input_device_name
        self.output_device_index = output_device_index

        self.audio_in_queue = None
        self.out_queue = None
        self.paused = False
        self.chat_buffer = {"sender": None, "text": ""}
        self._last_input_transcription = ""
        self._last_output_transcription = ""
        self._last_assistant_spoken_text = ""
        self._assistant_speak_timestamp = 0
        self._echo_protection_cooldown = 2.0
        self.assistant_speaking = False
        self._ada_output_started = False
        self._ada_output_text = ""
        self.session = None
        self.permissions = {}
        self._pending_confirmations = {}
        self._latest_image_payload = None
        self._is_speaking = False
        self._silence_start_time = None

        def handle_cad_thought(thought_text):
            if self.on_cad_thought:
                self.on_cad_thought(thought_text)
        
        def handle_cad_status(status_info):
            if self.on_cad_status:
                self.on_cad_status(status_info)

        self.cad_agent = CadAgent(on_thought=handle_cad_thought, on_status=handle_cad_status)
        self.web_agent = WebAgent()
        self.kasa_agent = kasa_agent if kasa_agent else KasaAgent()
        self.printer_agent = PrinterAgent()
        self.send_text_task = None
        self.stop_event = asyncio.Event()
        
        from project_manager import ProjectManager
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        self.project_manager = ProjectManager(project_root)
        self.emotion_engine = None
        self.response_adapter = None

    def flush_chat(self):
        if self.chat_buffer["sender"] and self.chat_buffer["text"].strip():
            self.project_manager.log_chat(self.chat_buffer["sender"], self.chat_buffer["text"])
            self.chat_buffer = {"sender": None, "text": ""}

    def safe_emit_transcription(self, sender, text):
        if sender not in ['User', 'ADA']:
            print(f"[ADA DEBUG] [ROLE GUARD] REJECTED: Invalid sender '{sender}'")
            return False
        if not text or not isinstance(text, str):
            print(f"[ADA DEBUG] [ROLE GUARD] REJECTED: Invalid text type {type(text)}")
            return False
        print(f"[ADA DEBUG] [ROLE VALIDATION] Emitting {sender}: '{text[:40]}...'")
        if self.on_transcription:
            self.on_transcription({"sender": sender, "text": text})
        return True

    def set_assistant_speaking(self, speaking):
        if speaking and not self.assistant_speaking:
            self.assistant_speaking = True
            self.set_paused(True)
            if self.on_assistant_speaking:
                self.on_assistant_speaking({"speaking": True})
        elif not speaking and self.assistant_speaking:
            self.assistant_speaking = False
            self.set_paused(False)
            if self.on_assistant_speaking:
                self.on_assistant_speaking({"speaking": False})

    def set_paused(self, paused):
        self.paused = paused

    def stop(self):
        self.stop_event.set()

    def update_permissions(self, new_perms):
        self.permissions.update(new_perms or {})
        for k in ["system_control", "screen_access", "file_access", "generate_cad", "run_web_agent", "write_file"]:
            if k not in self.permissions:
                self.permissions[k] = True

    async def send_frame(self, frame_data):
        if isinstance(frame_data, bytes):
            b64_data = base64.b64encode(frame_data).decode('utf-8')
        else:
            b64_data = frame_data
        self._latest_image_payload = {"mime_type": "image/jpeg", "data": b64_data}

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send(input=msg, end_of_turn=False)

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()
        resolved_input_device_index = None
        
        if self.input_device_name:
            count = pya.get_device_count()
            for i in range(count):
                try:
                    info = pya.get_device_info_by_index(i)
                    if info['maxInputChannels'] > 0 and self.input_device_name.lower() in info.get('name', '').lower():
                        resolved_input_device_index = i
                        break
                except:
                    continue

        try:
            self.audio_stream = await asyncio.to_thread(
                pya.open, format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE,
                input=True, input_device_index=resolved_input_device_index or mic_info["index"],
                frames_per_buffer=CHUNK_SIZE
            )
        except OSError as e:
            print(f"[ADA] [ERR] Failed to open audio input stream: {e}")
            return

        VAD_THRESHOLD = 800
        SILENCE_DURATION = 0.5
        
        while True:
            if self.paused:
                await asyncio.sleep(0.1)
                continue
            try:
                data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE)
                if self.out_queue:
                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
                
                count = len(data) // 2
                if count > 0:
                    shorts = struct.unpack(f"<{count}h", data)
                    sum_squares = sum(s**2 for s in shorts)
                    rms = int(math.sqrt(sum_squares / count))
                else:
                    rms = 0
                
                if rms > VAD_THRESHOLD:
                    self._silence_start_time = None
                    if not self._is_speaking:
                        self._is_speaking = True
                        if self._latest_image_payload and self.out_queue:
                            await self.out_queue.put(self._latest_image_payload)
                else:
                    if self._is_speaking:
                        if self._silence_start_time is None:
                            self._silence_start_time = time.time()
                        elif time.time() - self._silence_start_time > SILENCE_DURATION:
                            self._is_speaking = False
                            self._silence_start_time = None
            except Exception as e:
                await asyncio.sleep(0.1)

    async def handle_cad_request(self, prompt):
        if self.on_cad_status:
            self.on_cad_status("generating")
        cad_output_dir = str(self.project_manager.get_current_project_path() / "cad")
        cad_data = await self.cad_agent.generate_prototype(prompt, output_dir=cad_output_dir)
        if cad_data and self.on_cad_data:
            self.on_cad_data(cad_data)

    async def handle_web_agent_request(self, prompt):
        async def update_frontend(image_b64, log_text):
            if self.on_web_data:
                self.on_web_data({"image": image_b64, "log": log_text})
        await self.web_agent.run_task(prompt, update_callback=update_frontend)

    async def receive_audio(self):
        try:
            while True:
                turn = self.session.receive()
                async for response in turn:
                    if data := response.data:
                        self.audio_in_queue.put_nowait(data)
                    
                    if response.server_content:
                        if response.server_content.input_transcription:
                            transcript = response.server_content.input_transcription.text
                            if transcript and transcript != self._last_input_transcription:
                                delta = transcript[len(self._last_input_transcription):] if transcript.startswith(self._last_input_transcription) else transcript
                                self._last_input_transcription = transcript
                                if delta:
                                    self.clear_audio_queue()
                                    self.safe_emit_transcription("User", delta)
                                    if self.chat_buffer["sender"] != "User":
                                        if self.chat_buffer["sender"] and self.chat_buffer["text"].strip():
                                            self.project_manager.log_chat(self.chat_buffer["sender"], self.chat_buffer["text"])
                                        self.chat_buffer = {"sender": "User", "text": delta}
                                    else:
                                        self.chat_buffer["text"] += delta
                        
                        if response.server_content.output_transcription:
                            transcript = response.server_content.output_transcription.text
                            if transcript and transcript != self._last_output_transcription:
                                delta = transcript[len(self._last_output_transcription):] if transcript.startswith(self._last_output_transcription) else transcript
                                self._last_output_transcription = transcript
                                if delta:
                                    if not self._ada_output_started:
                                        self.set_assistant_speaking(True)
                                        self._ada_output_started = True
                                    self._ada_output_text += delta
                                    self.safe_emit_transcription("ADA", delta)
                                    if self.chat_buffer["sender"] != "ADA":
                                        if self.chat_buffer["sender"] and self.chat_buffer["text"].strip():
                                            self.project_manager.log_chat(self.chat_buffer["sender"], self.chat_buffer["text"])
                                        self.chat_buffer = {"sender": "ADA", "text": delta}
                                    else:
                                        self.chat_buffer["text"] += delta
                    
                    if response.tool_call:
                        function_responses = []
                        for fc in response.tool_call.function_calls:
                            # ========== GET CURRENT TIME ==========
                            if fc.name == "get_current_time":
                                utc_now = datetime.utcnow()
                                ist_time = utc_now + timedelta(hours=5, minutes=30)
                                formatted_time = ist_time.strftime("%I:%M %p, %A, %B %d, %Y")
                                result_str = f"The current time in India is {formatted_time}"
                                function_response = types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str})
                                function_responses.append(function_response)
                            
                            # ========== SYSTEM CONTROL (FIXED - NO CRASH) ==========
                            elif fc.name == "system_control":
                                print("[ADA DEBUG] [TOOL] Tool Call: 'system_control'")
                                action = fc.args.get("action", "")
                                params = fc.args.get("params", {})
                                print(f"[ADA DEBUG] [SYSTEM] Action: '{action}', Params: {params}")
                                
                                try:
                                    if action == "open_app":
                                        app_name = params.get("app_name", "")
                                        print(f"[ADA DEBUG] Opening app: {app_name}")
                                        
                                        from system_agent import get_system_agent
                                        system_agent = get_system_agent()
                                        result = system_agent.open_app(app_name)
                                        
                                        print(f"[ADA DEBUG] Result: {result}")
                                        
                                        function_response = types.FunctionResponse(
                                            id=fc.id,
                                            name=fc.name,
                                            response={"result": result.get("message", "Done")}
                                        )
                                        function_responses.append(function_response)
                                        
                                    elif action == "capture_screen":
                                        from system_agent import get_system_agent
                                        system_agent = get_system_agent()
                                        result = system_agent.capture_screen()
                                        function_response = types.FunctionResponse(
                                            id=fc.id, name=fc.name,
                                            response={"result": result.get("message", "Screenshot taken")}
                                        )
                                        function_responses.append(function_response)
                                        
                                    elif action == "control_volume":
                                        level = params.get("level", 50)
                                        from system_agent import get_system_agent
                                        system_agent = get_system_agent()
                                        result = system_agent.control_volume(level)
                                        function_response = types.FunctionResponse(
                                            id=fc.id, name=fc.name,
                                            response={"result": result.get("message", f"Volume set to {level}%")}
                                        )
                                        function_responses.append(function_response)
                                        
                                    elif action == "control_brightness":
                                        level = params.get("level", 50)
                                        from system_agent import get_system_agent
                                        system_agent = get_system_agent()
                                        result = system_agent.control_brightness(level)
                                        function_response = types.FunctionResponse(
                                            id=fc.id, name=fc.name,
                                            response={"result": result.get("message", f"Brightness set to {level}%")}
                                        )
                                        function_responses.append(function_response)
                                        
                                    else:
                                        function_response = types.FunctionResponse(
                                            id=fc.id, name=fc.name,
                                            response={"result": f"Unsupported action: {action}"}
                                        )
                                        function_responses.append(function_response)
                                        
                                except Exception as e:
                                    print(f"[ADA DEBUG] [SYSTEM_CTRL ERROR] {e}")
                                    import traceback
                                    traceback.print_exc()
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name,
                                        response={"result": f"Error: {str(e)}"}
                                    )
                                    function_responses.append(function_response)
                            
                            # ========== MEDIA PLAY ==========
                            elif fc.name == "media_play":
                                platform = fc.args.get("platform", "").lower()
                                query = fc.args.get("query", "")
                                media_controller = MediaController()
                                try:
                                    if platform == "spotify":
                                        result = media_controller.spotify_play(query)
                                        result_str = result.get("message", f"Playing {query} on Spotify")
                                    elif platform == "youtube":
                                        result = media_controller.youtube_play(query)
                                        result_str = result.get("message", f"Playing {query} on YouTube")
                                    else:
                                        result_str = f"Unknown platform: {platform}"
                                except Exception as e:
                                    result_str = f"Media error: {str(e)}"
                                function_response = types.FunctionResponse(
                                    id=fc.id, name=fc.name,
                                    response={"result": result_str}
                                )
                                function_responses.append(function_response)
                            
                            # ========== OTHER TOOLS ==========
                            elif fc.name == "create_project":
                                name = fc.args.get("name", "")
                                success, msg = self.project_manager.create_project(name)
                                if success:
                                    self.project_manager.switch_project(name)
                                    if self.on_project_update:
                                        self.on_project_update(name)
                                function_response = types.FunctionResponse(
                                    id=fc.id, name=fc.name,
                                    response={"result": msg}
                                )
                                function_responses.append(function_response)
                            
                            elif fc.name == "switch_project":
                                name = fc.args.get("name", "")
                                success, msg = self.project_manager.switch_project(name)
                                if success and self.on_project_update:
                                    self.on_project_update(name)
                                function_response = types.FunctionResponse(
                                    id=fc.id, name=fc.name,
                                    response={"result": msg}
                                )
                                function_responses.append(function_response)
                            
                            elif fc.name == "list_projects":
                                projects = self.project_manager.list_projects()
                                function_response = types.FunctionResponse(
                                    id=fc.id, name=fc.name,
                                    response={"result": f"Available projects: {', '.join(projects)}"}
                                )
                                function_responses.append(function_response)
                            
                            elif fc.name == "list_smart_devices":
                                dev_summaries = []
                                for ip, d in self.kasa_agent.devices.items():
                                    dev_type = "bulb" if d.is_bulb else "plug" if d.is_plug else "unknown"
                                    info = f"{d.alias} (IP: {ip}, Type: {dev_type}) - {'ON' if d.is_on else 'OFF'}"
                                    dev_summaries.append(info)
                                result_str = "\n".join(dev_summaries) if dev_summaries else "No devices found"
                                function_response = types.FunctionResponse(
                                    id=fc.id, name=fc.name,
                                    response={"result": result_str}
                                )
                                function_responses.append(function_response)
                            
                            elif fc.name == "control_light":
                                target = fc.args.get("target", "")
                                action = fc.args.get("action", "")
                                brightness = fc.args.get("brightness")
                                color = fc.args.get("color")
                                
                                if action == "turn_on":
                                    await self.kasa_agent.turn_on(target)
                                    result_msg = f"Turned ON {target}"
                                elif action == "turn_off":
                                    await self.kasa_agent.turn_off(target)
                                    result_msg = f"Turned OFF {target}"
                                else:
                                    result_msg = f"Action {action} on {target}"
                                
                                if brightness is not None:
                                    await self.kasa_agent.set_brightness(target, brightness)
                                if color is not None:
                                    await self.kasa_agent.set_color(target, color)
                                
                                function_response = types.FunctionResponse(
                                    id=fc.id, name=fc.name,
                                    response={"result": result_msg}
                                )
                                function_responses.append(function_response)
                            
                            elif fc.name == "discover_printers":
                                printers = await self.printer_agent.discover_printers()
                                result_str = "\n".join([f"{p['name']} ({p['host']})" for p in printers]) if printers else "No printers found"
                                function_response = types.FunctionResponse(
                                    id=fc.id, name=fc.name,
                                    response={"result": result_str}
                                )
                                function_responses.append(function_response)
                            
                            elif fc.name == "get_print_status":
                                printer = fc.args.get("printer", "")
                                status = await self.printer_agent.get_print_status(printer)
                                if status:
                                    result_str = f"State: {status.state}, Progress: {status.progress_percent}%"
                                else:
                                    result_str = f"Could not get status for {printer}"
                                function_response = types.FunctionResponse(
                                    id=fc.id, name=fc.name,
                                    response={"result": result_str}
                                )
                                function_responses.append(function_response)
                            
                            elif fc.name == "iterate_cad":
                                prompt = fc.args.get("prompt", "")
                                if self.on_cad_status:
                                    self.on_cad_status("generating")
                                cad_output_dir = str(self.project_manager.get_current_project_path() / "cad")
                                cad_data = await self.cad_agent.iterate_prototype(prompt, output_dir=cad_output_dir)
                                if cad_data and self.on_cad_data:
                                    self.on_cad_data(cad_data)
                                function_response = types.FunctionResponse(
                                    id=fc.id, name=fc.name,
                                    response={"result": "CAD iteration complete"}
                                )
                                function_responses.append(function_response)
                            
                            elif fc.name == "screen_read":
                                camera = get_camera_module()
                                try:
                                    scene_analysis = camera.describe_scene()
                                    if scene_analysis.get("success"):
                                        result_str = scene_analysis.get("description", "Camera view analyzed")
                                    else:
                                        result_str = "Failed to read camera"
                                except Exception as e:
                                    result_str = f"Camera error: {str(e)}"
                                function_response = types.FunctionResponse(
                                    id=fc.id, name=fc.name,
                                    response={"result": result_str}
                                )
                                function_responses.append(function_response)
                        
                        if function_responses:
                            await self.session.send_tool_response(function_responses=function_responses)
                
                self.flush_chat()
                if self.assistant_speaking:
                    self.set_assistant_speaking(False)
                    self._ada_output_started = False
                    self._ada_output_text = ""
                while not self.audio_in_queue.empty():
                    self.audio_in_queue.get_nowait()
        except Exception as e:
            print(f"Error in receive_audio: {e}")
            traceback.print_exc()
            raise e

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open, format=FORMAT, channels=CHANNELS, rate=RECEIVE_SAMPLE_RATE,
            output=True, output_device_index=self.output_device_index
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            if self.on_audio_data:
                self.on_audio_data(bytestream)
            await asyncio.to_thread(stream.write, bytestream)

    async def get_frames(self):
        cap = await asyncio.to_thread(cv2.VideoCapture, 0, cv2.CAP_AVFOUNDATION)
        while True:
            if self.paused:
                await asyncio.sleep(0.1)
                continue
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break
            await asyncio.sleep(1.0)
            if self.out_queue:
                await self.out_queue.put(frame)
        cap.release()

    def _get_frame(self, cap):
        ret, frame = cap.read()
        if not ret:
            return None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)
        img.thumbnail([1024, 1024])
        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)
        image_bytes = image_io.read()
        return {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode()}

    def clear_audio_queue(self):
        try:
            count = 0
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()
                count += 1
            if count > 0:
                print(f"[ADA DEBUG] [AUDIO] Cleared {count} chunks")
        except Exception as e:
            print(f"[ADA DEBUG] [ERR] Failed to clear audio queue: {e}")

    async def run(self, start_message=None):
        retry_delay = 1
        is_reconnect = False
        
        while not self.stop_event.is_set():
            try:
                print(f"[ADA DEBUG] [CONNECT] Connecting to Gemini Live API...")
                async with (
                    client.aio.live.connect(model=MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session = session
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue = asyncio.Queue(maxsize=10)

                    tg.create_task(self.send_realtime())
                    tg.create_task(self.listen_audio())
                    if self.video_mode == "camera":
                        tg.create_task(self.get_frames())
                    tg.create_task(self.receive_audio())
                    tg.create_task(self.play_audio())

                    if not is_reconnect:
                        if start_message:
                            await self.session.send(input=start_message, end_of_turn=True)
                        if self.on_project_update and self.project_manager:
                            self.on_project_update(self.project_manager.current_project)
                    else:
                        print(f"[ADA DEBUG] [RECONNECT] Connection restored.")
                        history = self.project_manager.get_recent_chat_history(limit=10)
                        context_msg = "System Notification: Connection restored. Recent history:\n\n"
                        for entry in history:
                            context_msg += f"[{entry.get('sender', 'Unknown')}]: {entry.get('text', '')}\n"
                        await self.session.send(input=context_msg, end_of_turn=True)

                    retry_delay = 1
                    await self.stop_event.wait()

            except asyncio.CancelledError:
                print(f"[ADA DEBUG] [STOP] Main loop cancelled.")
                break
            except Exception as e:
                print(f"[ADA DEBUG] [ERR] Connection Error: {e}")
                if self.stop_event.is_set():
                    break
                print(f"[ADA DEBUG] [RETRY] Reconnecting in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10)
                is_reconnect = True
            finally:
                if hasattr(self, 'audio_stream') and self.audio_stream:
                    try:
                        self.audio_stream.close()
                    except:
                        pass


def get_input_devices():
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    devices = []
    for i in range(numdevices):
        if p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels') > 0:
            devices.append((i, p.get_device_info_by_host_api_device_index(0, i).get('name')))
    p.terminate()
    return devices


def get_output_devices():
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    devices = []
    for i in range(numdevices):
        if p.get_device_info_by_host_api_device_index(0, i).get('maxOutputChannels') > 0:
            devices.append((i, p.get_device_info_by_host_api_device_index(0, i).get('name')))
    p.terminate()
    return devices


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default=DEFAULT_MODE,
                        choices=["camera", "screen", "none"])
    parser.add_argument("--api", action="store_true")

    args = parser.parse_args()

    # Run FastAPI Server
    if args.api:
        uvicorn.run(app, host="0.0.0.0", port=10000)

    # Run Voice Assistant
    else:
        main = AudioLoop(video_mode=args.mode)
        asyncio.run(main.run())