from dotenv import load_dotenv
load_dotenv()

import os
from google import genai
from google.genai import types

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

response = client.models.generate_content(
    model="gemini-2.5-flash-preview-tts",

    contents="Hello Manoj, I am Myra",

    config=types.GenerateContentConfig(

        response_modalities=["AUDIO"],

        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Kore"
                )
            )
        )
    )
)

audio_data = response.candidates[0].content.parts[0].inline_data.data

with open("myra_voice.wav", "wb") as f:
    f.write(audio_data)

print("Kore voice generated successfully")