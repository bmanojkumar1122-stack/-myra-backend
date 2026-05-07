import os
import subprocess
import webbrowser
import logging
import urllib.parse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SystemAgent:
    COMMON_APPS = {
        'notepad': 'notepad.exe',
        'paint': 'mspaint.exe',
        'calculator': 'calc.exe',
        'chrome': 'chrome.exe',
    }

    def __init__(self):
        logger.info("System Agent initialized")

    def open_app(self, app_name: str) -> dict:
        app_lower = app_name.lower().strip()
        print(f"[SYSTEM_AGENT DEBUG] Received: '{app_name}' -> lower: '{app_lower}'")
        logger.info(f"Opening: {app_name}")
        
        # ========== OPEN YOUTUBE IN CHROME ==========
        if 'youtube' in app_lower:
            print(f"[SYSTEM_AGENT DEBUG] YouTube detected!")
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
            for chrome_path in chrome_paths:
                print(f"[SYSTEM_AGENT DEBUG] Checking Chrome path: {chrome_path}")
                if os.path.exists(chrome_path):
                    print(f"[SYSTEM_AGENT DEBUG] Chrome found! Opening YouTube...")
                    subprocess.Popen([chrome_path, "https://www.youtube.com"])
                    return {'success': True, 'message': "Opening YouTube in Chrome..."}
            print(f"[SYSTEM_AGENT DEBUG] Chrome not found, using default browser")
            webbrowser.open('https://www.youtube.com')
            return {'success': True, 'message': "Opening YouTube..."}
        
        # ========== PLAY SONG ==========
        if 'play' in app_lower and ('song' in app_lower or 'music' in app_lower):
            print(f"[SYSTEM_AGENT DEBUG] Play song detected")
            words = app_lower.split()
            song = ""
            for i, word in enumerate(words):
                if word == 'play' and i+1 < len(words):
                    song = ' '.join(words[i+1:])
                    break
            
            if not song or song in ['song', 'music']:
                song = "Tum Hi Ho"
            
            search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(song)}"
            webbrowser.open(search_url)
            return {'success': True, 'message': f"Searching for {song} on YouTube"}
        
        # ========== OPEN WHATSAPP DESKTOP APP ==========
        if 'whatsapp' in app_lower or 'whats app' in app_lower:
            print(f"[SYSTEM_AGENT DEBUG] WhatsApp detected")
            
            # Try to open WhatsApp Desktop app
            whatsapp_paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
                r"C:\Program Files\WindowsApps\WhatsAppDesktop.exe",
                r"C:\Program Files (x86)\WhatsApp\WhatsApp.exe",
                r"C:\Program Files\WhatsApp\WhatsApp.exe",
            ]
            
            for path in whatsapp_paths:
                if os.path.exists(path):
                    try:
                        subprocess.Popen(path)
                        return {'success': True, 'message': "Opening WhatsApp Desktop..."}
                    except Exception as e:
                        logger.warning(f"Failed to open {path}: {e}")
            
            # Try WhatsApp protocol
            try:
                subprocess.Popen(["start", "whatsapp:"], shell=True)
                return {'success': True, 'message': "Opening WhatsApp..."}
            except Exception as e:
                logger.warning(f"WhatsApp protocol failed: {e}")
            
            # Fallback to WhatsApp Web
            webbrowser.open('https://web.whatsapp.com')
            return {'success': True, 'message': "Opening WhatsApp Web..."}
        
        # ========== OPEN COMMON APPS ==========
        for key, exe in self.COMMON_APPS.items():
            if key in app_lower:
                print(f"[SYSTEM_AGENT DEBUG] Common app detected: {key}")
                subprocess.Popen(exe)
                return {'success': True, 'message': f"Opening {key}"}
        
        print(f"[SYSTEM_AGENT DEBUG] No match found for: {app_lower}")
        return {'success': False, 'error': f"'{app_name}' not found"}

    def capture_screen(self):
        return {'success': False}

    def control_volume(self, level):
        return {'success': False}

    def control_brightness(self, level):
        return {'success': False}

    def type_text(self, text):
        return {'success': False}

    def press_key(self, key):
        return {'success': False}

    def open_file(self, path):
        return {'success': False}

    def open_folder(self, path):
        return {'success': False}

    def find_file(self, name):
        return {'success': False}

    def get_system_capabilities(self):
        return {}

    def get_common_apps(self):
        return self.COMMON_APPS


_system_agent = None

def get_system_agent():
    global _system_agent
    if _system_agent is None:
        _system_agent = SystemAgent()
    return _system_agent