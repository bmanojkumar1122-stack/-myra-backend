"""
Media Controller - Simplified for Spotify and YouTube playback
"""
import subprocess
import time
import pyautogui
import pygetwindow as gw
from app_registry import get_registry
from typing import Optional, Dict


class MediaController:
    def __init__(self):
        self.registry = get_registry()
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
    
    def launch_app(self, app_name: str) -> bool:
        """Launch application directly"""
        try:
            if app_name.lower() == "spotify":
                path = self.registry.get_spotify_path()
            elif app_name.lower() in ["chrome", "google chrome"]:
                path = self.registry.get_chrome_path()
            elif app_name.lower() == "edge":
                path = self.registry.get_edge_path()
            else:
                path = self.registry.get_app_path(app_name)
            
            if not path:
                return False
            
            subprocess.Popen(path)
            time.sleep(1)
            return True
        except:
            return False
    
    def focus_window(self, window_title_partial: str) -> Optional[object]:
        """Focus window by partial title match"""
        try:
            windows = gw.getWindowsWithTitle(window_title_partial)
            if windows:
                window = windows[0]
                window.activate()
                time.sleep(0.5)
                return window
        except:
            pass
        return None
    
    def spotify_play(self, query: str) -> Dict:
        """Search and play music on Spotify"""
        try:
            print(f"[SPOTIFY] Playing: {query}")
            
            # Launch Spotify if not running
            if not self.focus_window("Spotify"):
                print(f"[SPOTIFY] Launching Spotify...")
                if not self.launch_app("Spotify"):
                    return {"success": False, "error": "Spotify not found"}
                time.sleep(5)  # Wait for Spotify to fully load
                if not self.focus_window("Spotify"):
                    time.sleep(3)
                    self.focus_window("Spotify")
            
            print(f"[SPOTIFY] Searching for: {query}")
            time.sleep(1)
            
            # IMPROVED: Open search with Ctrl+L
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.8)  # Wait for search box to activate
            
            # Select all and clear previous search
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.2)
            
            # Type query with proper interval (0.08 per character, like WhatsApp fix)
            print(f"[SPOTIFY] Typing query: {query}")
            pyautogui.typewrite(query, interval=0.08)
            time.sleep(1)
            
            # Press Enter to search
            print(f"[SPOTIFY] Searching...")
            pyautogui.press('enter')
            time.sleep(3)  # Wait for search results
            
            # IMPORTANT: First tab press gets focus on search results
            # Then press down and enter to select first track
            print(f"[SPOTIFY] Selecting first result...")
            pyautogui.press('tab')
            time.sleep(0.5)
            
            # Press down to go to first track
            pyautogui.press('down')
            time.sleep(0.3)
            
            # Press enter to play the track
            print(f"[SPOTIFY] Playing track...")
            pyautogui.press('enter')
            time.sleep(2)  # Wait for playback to start
            
            print(f"[SPOTIFY] ✓ Track should now be playing!")
            return {"success": True, "action": "spotify_play", "query": query, "status": "now playing"}
            
        except Exception as e:
            print(f"[SPOTIFY ERROR] {e}")
            return {"success": False, "error": str(e)}
    
    def youtube_play(self, query: str) -> Dict:
        """Search and play video on YouTube - FIXED VERSION"""
        try:
            print(f"[YOUTUBE] Playing: {query}")
            
            chrome_path = self.registry.get_chrome_path()
            if not chrome_path:
                return {"success": False, "error": "Chrome not found"}
            
            # Open YouTube homepage directly
            print(f"[YOUTUBE] Opening YouTube homepage...")
            subprocess.Popen([chrome_path, "https://www.youtube.com"])
            
            print(f"[YOUTUBE] Waiting for page to load...")
            time.sleep(6)  # Wait for YouTube to fully load
            
            # Focus Chrome window
            print(f"[YOUTUBE] Focusing Chrome window...")
            pyautogui.hotkey('alt', 'tab')
            time.sleep(1)
            
            # Find and click search box
            # YouTube search box is usually at top - try pressing Tab to get to it
            print(f"[YOUTUBE] Navigating to search box...")
            pyautogui.press('tab')
            time.sleep(0.3)
            
            # Type query in search box
            print(f"[YOUTUBE] Typing query: {query}")
            # Clear any existing text first
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.2)
            
            # Type with proper interval (like WhatsApp fix)
            pyautogui.typewrite(query, interval=0.08)
            time.sleep(0.5)
            
            # Press Enter to search
            print(f"[YOUTUBE] Searching for '{query}'...")
            pyautogui.press('enter')
            time.sleep(5)  # Wait for search results to load
            
            # Navigate to first video result
            print(f"[YOUTUBE] Navigating to first video...")
            # Tab to focus first video in results
            pyautogui.press('tab')
            time.sleep(0.3)
            pyautogui.press('tab')
            time.sleep(0.3)
            
            # Press Enter to open the video
            print(f"[YOUTUBE] Opening video...")
            pyautogui.press('enter')
            time.sleep(6)  # Wait for video page to load
            
            # Click on video player area to ensure focus
            print(f"[YOUTUBE] Clicking video player...")
            pyautogui.click(960, 540)  # Center of screen
            time.sleep(0.5)
            
            # Start playback
            print(f"[YOUTUBE] Starting playback...")
            pyautogui.press('k')  # YouTube play/pause (more reliable than space)
            time.sleep(2)
            
            print(f"[YOUTUBE] ✓ Video should now be playing!")
            return {"success": True, "action": "youtube_play", "query": query, "status": "playing"}
            
        except Exception as e:
            print(f"[YOUTUBE ERROR] {e}")
            return {"success": False, "error": str(e)}
    
    def open_app(self, app_name: str) -> Dict:
        """Open application"""
        try:
            if self.launch_app(app_name):
                return {"success": True, "action": "open_app", "app": app_name}
            return {"success": False, "error": f"{app_name} not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}


_controller = None

def get_media_controller() -> MediaController:
    global _controller
    if _controller is None:
        _controller = MediaController()
    return _controller
