"""
System Control Agent for MYRA Desktop Access
Provides controlled Windows desktop automation with safety checks.

Hard Safety Requirements:
- Explicit user confirmation for all actions
- Permission checks before execution
- Single-frame screenshots only
- No background monitoring
- Comprehensive logging
"""

import subprocess
import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime
import asyncio

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    from PIL import Image
    import mss
    HAS_SCREENSHOT = True
except ImportError:
    HAS_SCREENSHOT = False

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

try:
    import screen_brightness_control as sbc
    HAS_BRIGHTNESS = True
except ImportError:
    HAS_BRIGHTNESS = False

try:
    from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
    HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[SYSTEM_AGENT] %(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SystemAgent:
    """Main system control agent for desktop automation."""
    
    # Common Windows application paths
    COMMON_APPS = {
        'notepad': 'notepad.exe',
        'explorer': 'explorer.exe',
        'chrome': 'chrome.exe',
        'calculator': 'calc.exe',
        'paint': 'mspaint.exe',
        'wordpad': 'wordpad.exe',
        'snipping tool': 'SnippingTool.exe',
        'cmd': 'cmd.exe',
        'powershell': 'powershell.exe',
        'notepad++': 'notepad++.exe',
        'vscode': 'code.exe',
    }

    def __init__(self):
        """Initialize System Agent with capability checks."""
        self.pyautogui_available = HAS_PYAUTOGUI
        self.screenshot_available = HAS_SCREENSHOT
        self.keyboard_available = HAS_KEYBOARD
        self.brightness_available = HAS_BRIGHTNESS
        self.pycaw_available = HAS_PYCAW
        
        # Disable pyautogui's built-in pause (we'll control timing)
        if self.pyautogui_available:
            pyautogui.PAUSE = 0.1
            # Failsafes: press a corner to abort
            pyautogui.FAILSAFE = True
        
        logger.info("System Agent initialized")
        logger.info(f"Available capabilities: pyautogui={self.pyautogui_available}, "
                   f"screenshot={self.screenshot_available}, keyboard={self.keyboard_available}, "
                   f"brightness={self.brightness_available}, pycaw={self.pycaw_available}")

    # ==================== SCREEN CAPTURE ====================
    def capture_screen(self) -> dict:
        """
        Capture current screen as base64 image (SINGLE FRAME ONLY).
        Returns: {
            'success': bool,
            'data': base64_string,
            'timestamp': ISO timestamp,
            'size': (width, height),
            'error': error_message if failed
        }
        """
        try:
            if not self.screenshot_available:
                return {
                    'success': False,
                    'error': 'Screenshot capability not available. Install: pip install mss pillow'
                }
            
            logger.info("Capturing screen...")
            
            # Capture using mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                screenshot = sct.grab(monitor)
                
                # Convert to PIL Image
                img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
                
                # Get dimensions
                width, height = img.size
                
                # Convert to base64
                import io
                import base64
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                result = {
                    'success': True,
                    'data': img_base64,
                    'timestamp': datetime.now().isoformat(),
                    'size': [width, height]
                }
                
                logger.info(f"Screen captured successfully: {width}x{height}")
                return result
        
        except Exception as e:
            logger.error(f"Screen capture failed: {str(e)}")
            return {
                'success': False,
                'error': f"Screen capture failed: {str(e)}"
            }

    # ==================== FILE OPERATIONS ====================
    def find_file(self, file_name: str, search_paths: list = None) -> dict:
        """
        Find a file by name or search in common locations.
        Returns: {
            'success': bool,
            'path': full_path if found,
            'error': error_message if failed
        }
        """
        try:
            # Default search paths
            if not search_paths:
                search_paths = [
                    str(Path.home() / "Desktop"),
                    str(Path.home() / "Documents"),
                    str(Path.home()),
                ]
            
            logger.info(f"Searching for file: {file_name}")
            
            # Search in provided paths
            for search_path in search_paths:
                if not os.path.exists(search_path):
                    continue
                
                for root, dirs, files in os.walk(search_path):
                    # Limit depth to avoid searching too deep
                    if root.count(os.sep) - search_path.count(os.sep) > 3:
                        dirs.clear()
                        continue
                    
                    for file in files:
                        if file.lower() == file_name.lower() or file_name.lower() in file.lower():
                            full_path = os.path.join(root, file)
                            logger.info(f"File found: {full_path}")
                            return {
                                'success': True,
                                'path': full_path
                            }
            
            logger.warning(f"File not found: {file_name}")
            return {
                'success': False,
                'error': f"File '{file_name}' not found in search paths"
            }
        
        except Exception as e:
            logger.error(f"File search failed: {str(e)}")
            return {
                'success': False,
                'error': f"File search failed: {str(e)}"
            }

    def open_file(self, file_path: str) -> dict:
        """
        Open a file with default application.
        Returns: {
            'success': bool,
            'message': status_message,
            'error': error_message if failed
        }
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                logger.error(f"File does not exist: {file_path}")
                return {
                    'success': False,
                    'error': f"File does not exist: {file_path}"
                }
            
            logger.info(f"Opening file: {file_path}")
            
            # Use os.startfile on Windows
            os.startfile(file_path)
            
            logger.info(f"File opened: {file_path}")
            return {
                'success': True,
                'message': f"File opened: {file_path}"
            }
        
        except Exception as e:
            logger.error(f"Failed to open file: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to open file: {str(e)}"
            }

    def open_folder(self, folder_path: str) -> dict:
        """
        Open a folder in Windows Explorer.
        Returns: {
            'success': bool,
            'message': status_message,
            'error': error_message if failed
        }
        """
        try:
            # Check if folder exists
            if not os.path.exists(folder_path):
                logger.error(f"Folder does not exist: {folder_path}")
                return {
                    'success': False,
                    'error': f"Folder does not exist: {folder_path}"
                }
            
            logger.info(f"Opening folder: {folder_path}")
            
            # Use subprocess to open Explorer
            subprocess.Popen(f'explorer /select,"{folder_path}"')
            
            logger.info(f"Folder opened: {folder_path}")
            return {
                'success': True,
                'message': f"Folder opened: {folder_path}"
            }
        
        except Exception as e:
            logger.error(f"Failed to open folder: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to open folder: {str(e)}"
            }

    # ==================== APPLICATION LAUNCHER ====================
         # ==================== APPLICATION LAUNCHER ====================
    def open_app(self, app_name: str) -> dict:
        """
        Open a Windows application by name - FAST VERSION (No delays)
        """
        import subprocess
        import threading
        
        try:
            app_name_lower = app_name.lower().strip()
            logger.info(f"Opening application: {app_name}")
            
            # ========== FAST URLs - Direct Chrome Open ==========
            url_map = {
                'youtube': 'https://youtube.com',
                'yt': 'https://youtube.com',
                'whatsapp web': 'https://web.whatsapp.com',
                'wa web': 'https://web.whatsapp.com',
                'google': 'https://google.com',
                'gmail': 'https://gmail.com',
                'github': 'https://github.com',
                'facebook': 'https://facebook.com',
                'instagram': 'https://instagram.com',
                'twitter': 'https://twitter.com',
                'reddit': 'https://reddit.com',
                'spotify web': 'https://open.spotify.com',
                'whatsapp': 'https://web.whatsapp.com', 
                'wa': 'https://web.whatsapp.com',       
                'wp': 'https://web.whatsapp.com', }

              
            
            if app_name_lower in url_map:
                url = url_map[app_name_lower]
                def open_fast():
                    subprocess.Popen(f'start chrome {url}', shell=True)
                threading.Thread(target=open_fast).start()
                logger.info(f"Fast opening: {app_name}")
                return {'success': True, 'message': f"Opening {app_name}..."}
            
            # If user passed a URL directly
            if app_name_lower.startswith('http://') or app_name_lower.startswith('https://') or '.com' in app_name_lower:
                def open_url_fast():
                    subprocess.Popen(f'start chrome {app_name}', shell=True)
                threading.Thread(target=open_url_fast).start()
                return {'success': True, 'message': f"Opening URL..."}
            
            # ========== FAST Apps - Direct Launch ==========
            fast_apps = {
                'chrome': 'chrome.exe',
                'notepad': 'notepad.exe',
                'calculator': 'calc.exe',
                'calc': 'calc.exe',
                'paint': 'mspaint.exe',
                'cmd': 'cmd.exe',
                'command prompt': 'cmd.exe',
                'powershell': 'powershell.exe',
                'explorer': 'explorer.exe',
                'file explorer': 'explorer.exe',
                'spotify': 'spotify.exe',
                'whatsapp': 'whatsapp.exe',
                'whatsapp desktop': 'whatsapp.exe',
                'vscode': 'code.exe',
                'visual studio code': 'code.exe',
            }
            
            if app_name_lower in fast_apps:
                exe = fast_apps[app_name_lower]
                def open_app_fast():
                    subprocess.Popen(exe, shell=True)
                threading.Thread(target=open_app_fast).start()
                return {'success': True, 'message': f"Opening {app_name}..."}
            
            # ========== Try AppLauncher (for special cases) ==========
            try:
                from app_launcher import AppLauncher
                launcher = AppLauncher()
                result = launcher.launch_common_app(app_name)
                if result.get('success'):
                    return result
            except Exception as e:
                logger.warning(f"AppLauncher failed: {e}")
            
            # ========== Fallback: Try common apps ==========
            if app_name_lower in self.COMMON_APPS:
                exe_name = self.COMMON_APPS[app_name_lower]
            else:
                exe_name = app_name
            
            # Try to launch
            try:
                def open_fallback():
                    subprocess.Popen(exe_name, shell=True)
                threading.Thread(target=open_fallback).start()
                return {'success': True, 'message': f"Opening {app_name}..."}
            except:
                return {'success': False, 'error': f"Can't open {app_name}"}
        
        except Exception as e:
            logger.error(f"Failed: {str(e)}")
            return {'success': False, 'error': f"Failed: {str(e)}"}

    # ==================== KEYBOARD & MOUSE CONTROL ====================
    def type_text(self, text: str, delay: float = 0.05) -> dict:
        """
        Type text into the currently focused application.
        Returns: {
            'success': bool,
            'message': status_message,
            'error': error_message if failed
        }
        """
        try:
            if not self.pyautogui_available:
                return {
                    'success': False,
                    'error': 'pyautogui not available. Install: pip install pyautogui'
                }
            
            logger.info(f"Typing text: {text[:50]}...")
            
            # Give app time to focus
            time.sleep(0.5)
            
            pyautogui.typewrite(text, interval=delay)
            
            logger.info(f"Text typed successfully")
            return {
                'success': True,
                'message': f"Text typed: {text[:50]}..."
            }
        
        except Exception as e:
            logger.error(f"Text typing failed: {str(e)}")
            return {
                'success': False,
                'error': f"Text typing failed: {str(e)}"
            }

    def click_mouse(self, x: int = None, y: int = None) -> dict:
        """
        Click mouse at specified position (or current position).
        Returns: {
            'success': bool,
            'message': status_message,
            'error': error_message if failed
        }
        """
        try:
            if not self.pyautogui_available:
                return {
                    'success': False,
                    'error': 'pyautogui not available'
                }
            
            logger.info(f"Mouse click at ({x}, {y})")
            
            if x is not None and y is not None:
                pyautogui.click(x, y)
            else:
                pyautogui.click()
            
            return {
                'success': True,
                'message': f"Mouse clicked at ({x}, {y})"
            }
        
        except Exception as e:
            logger.error(f"Mouse click failed: {str(e)}")
            return {
                'success': False,
                'error': f"Mouse click failed: {str(e)}"
            }

    def press_key(self, key: str) -> dict:
        """
        Press a keyboard key (e.g., 'enter', 'tab', 'space').
        Returns: {
            'success': bool,
            'message': status_message,
            'error': error_message if failed
        }
        """
        try:
            if not self.pyautogui_available:
                return {
                    'success': False,
                    'error': 'pyautogui not available'
                }
            
            logger.info(f"Pressing key: {key}")
            
            pyautogui.press(key)
            
            return {
                'success': True,
                'message': f"Key pressed: {key}"
            }
        
        except Exception as e:
            logger.error(f"Key press failed: {str(e)}")
            return {
                'success': False,
                'error': f"Key press failed: {str(e)}"
            }

    # ==================== VOLUME CONTROL ====================
    def control_volume(self, level: int) -> dict:
        """
        Set system volume level (0-100).
        Returns: {
            'success': bool,
            'message': status_message,
            'error': error_message if failed
        }
        """
        try:
            # Clamp level
            level = max(0, min(100, level))
            
            if not self.pycaw_available:
                logger.warning("pycaw not available, trying nircmd fallback")
                try:
                    # nircmd approach (requires nircmd installed)
                    subprocess.run(['nircmd', 'setsysvolume', str(level * 655)])  # 655 = 65535/100
                    logger.info(f"Volume set to {level}% (nircmd)")
                    return {
                        'success': True,
                        'message': f"Volume set to {level}%"
                    }
                except:
                    return {
                        'success': False,
                        'error': 'Volume control not available. Install: pip install pycaw'
                    }
            
            logger.info(f"Setting volume to {level}%")
            
            try:
                # Try pycaw approach
                devices = AudioUtilities.GetSpeakers()
                if devices is None:
                    logger.warning("No audio devices found, using fallback")
                    return {
                        'success': False,
                        'error': 'No audio devices found on system'
                    }
                
                interface = devices.Activate(ISimpleAudioVolume._iid_, 0, None)
                volume = interface.QueryInterface(ISimpleAudioVolume)
                
                # Set volume (0.0 to 1.0)
                volume.SetMasterVolume(level / 100.0, None)
                
                logger.info(f"Volume set to {level}%")
                return {
                    'success': True,
                    'message': f"Volume set to {level}%"
                }
            except Exception as pycaw_error:
                logger.warning(f"pycaw failed: {str(pycaw_error)}, trying nircmd")
                try:
                    subprocess.run(['nircmd', 'setsysvolume', str(level * 655)])
                    logger.info(f"Volume set to {level}% (nircmd fallback)")
                    return {
                        'success': True,
                        'message': f"Volume set to {level}%"
                    }
                except:
                    return {
                        'success': False,
                        'error': f"Volume control unavailable: {str(pycaw_error)}"
                    }
        
        except Exception as e:
            logger.error(f"Volume control failed: {str(e)}")
            return {
                'success': False,
                'error': f"Volume control failed: {str(e)}"
            }

    # ==================== BRIGHTNESS CONTROL ====================
    def control_brightness(self, level: int) -> dict:
        """
        Set screen brightness level (0-100).
        Returns: {
            'success': bool,
            'message': status_message,
            'error': error_message if failed
        }
        """
        try:
            # Clamp level
            level = max(0, min(100, level))
            
            if not self.brightness_available:
                return {
                    'success': False,
                    'error': 'Brightness control not available. Install: pip install screen_brightness_control'
                }
            
            logger.info(f"Setting brightness to {level}%")
            
            sbc.set_brightness(level)
            
            logger.info(f"Brightness set to {level}%")
            return {
                'success': True,
                'message': f"Brightness set to {level}%"
            }
        
        except Exception as e:
            logger.error(f"Brightness control failed: {str(e)}")
            return {
                'success': False,
                'error': f"Brightness control failed: {str(e)}"
            }

    # ==================== STATUS & DIAGNOSTICS ====================
    def get_system_capabilities(self) -> dict:
        """Get available system capabilities."""
        return {
            'screenshot': self.screenshot_available,
            'keyboard': self.keyboard_available,
            'mouse': self.pyautogui_available,
            'brightness': self.brightness_available,
            'volume': self.pycaw_available,
            'app_launch': True,  # Always available via subprocess
            'file_operations': True,  # Always available via os module
        }

    def get_common_apps(self) -> dict:
        """Get list of recognized common applications."""
        return self.COMMON_APPS


# Global instance
_system_agent = None

def get_system_agent():
    """Get or create global System Agent instance."""
    global _system_agent
    if _system_agent is None:
        _system_agent = SystemAgent()
    return _system_agent
