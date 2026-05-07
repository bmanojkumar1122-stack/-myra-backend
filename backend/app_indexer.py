# app_indexer.py - CLEAN VERSION
import os
import json
from pathlib import Path
from typing import Dict
import winreg
import subprocess

try:
    from fuzzywuzzy import fuzz, process
    HAS_FUZZY = True
except ImportError:
    HAS_FUZZY = False
    print("[WARNING] fuzzywuzzy not installed. Install with: pip install fuzzywuzzy python-Levenshtein")

INDEX_FILE = "app_index.json"

DEFAULT_SEARCH_DIRS = [
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
    Path(os.path.expanduser("~/")),
    Path(os.path.expanduser("~\\AppData\\Local")),
    Path(os.path.expanduser("~\\AppData\\Roaming")),
]


class AppIndexer:
    """Scan Windows locations for executables and build name->path index."""

    def __init__(self, search_dirs=None, limit=2000):
        self.search_dirs = search_dirs or DEFAULT_SEARCH_DIRS
        self.limit = limit
        self.apps: Dict[str, dict] = {}
        self.app_list = []

    def _iter_dirs(self):
        for d in self.search_dirs:
            if d and d.exists():
                yield d

    def scan_start_menu(self):
        """Scan Windows Start Menu for installed apps"""
        try:
            start_menu_paths = [
                os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
                os.path.expandvars(r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs"),
            ]
            
            for start_menu_path in start_menu_paths:
                if not os.path.exists(start_menu_path):
                    continue
                    
                for root, dirs, files in os.walk(start_menu_path):
                    for file in files:
                        if file.endswith(('.lnk', '.url')):
                            full_path = os.path.join(root, file)
                            app_name = Path(file).stem
                            
                            if file.endswith('.lnk'):
                                target_path = self._resolve_lnk(full_path)
                            else:
                                target_path = full_path
                            
                            self.apps[app_name.lower()] = {
                                'name': app_name,
                                'path': full_path,
                                'target': target_path,
                                'type': 'shortcut'
                            }
        except Exception as e:
            print(f"Error scanning Start Menu: {e}")

    def scan_desktop(self):
        """Scan Desktop for shortcuts"""
        try:
            desktop_path = os.path.expandvars(r"%USERPROFILE%\Desktop")
            if desktop_path and os.path.exists(desktop_path):
                for file in os.listdir(desktop_path):
                    if file.endswith(('.lnk', '.url')):
                        full_path = os.path.join(desktop_path, file)
                        app_name = Path(file).stem
                        
                        if file.endswith('.lnk'):
                            target_path = self._resolve_lnk(full_path)
                        else:
                            target_path = full_path
                        
                        if app_name.lower() not in self.apps:
                            self.apps[app_name.lower()] = {
                                'name': app_name,
                                'path': full_path,
                                'target': target_path,
                                'type': 'shortcut'
                            }
        except Exception as e:
            pass  # Silently handle Desktop scan errors

    def scan_program_files(self):
        """Scan Program Files for executable locations"""
        try:
            program_files = [
                os.path.expandvars(r"%ProgramFiles%"),
                os.path.expandvars(r"%ProgramFiles(x86)%"),
            ]
            
            found = 0
            for pf_path in program_files:
                if not pf_path or not os.path.exists(pf_path):
                    continue
                    
                for root, dirs, files in os.walk(pf_path):
                    # Limit depth
                    if root.count(os.sep) - pf_path.count(os.sep) > 2:
                        dirs.clear()
                        continue
                    
                    for file in files:
                        if file.endswith('.exe'):
                            if found >= self.limit:
                                return
                            full_path = os.path.join(root, file)
                            app_name = Path(file).stem
                            
                            if app_name.lower() not in self.apps:
                                self.apps[app_name.lower()] = {
                                    'name': app_name,
                                    'path': full_path,
                                    'target': full_path,
                                    'type': 'executable'
                                }
                                found += 1
        except Exception as e:
            print(f"Error scanning Program Files: {e}")

    def scan_directories(self):
        """Scan predefined directories for executables"""
        found = 0
        for root in self._iter_dirs():
            try:
                for path in root.rglob('*.exe'):
                    if found >= self.limit:
                        return
                    try:
                        name = path.stem.lower()
                        if name not in self.apps:
                            self.apps[name] = {
                                'name': path.stem,
                                'path': str(path),
                                'target': str(path),
                                'type': 'executable'
                            }
                            found += 1
                    except Exception:
                        continue
            except Exception:
                continue

    def scan_registry(self):
        """Scan Windows Registry for installed apps"""
        try:
            registry_paths = [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
            ]
            
            for registry_path in registry_paths:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path)
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)
                            
                            try:
                                display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                if display_name:
                                    app_key = display_name.lower()
                                    if app_key not in self.apps:
                                        self.apps[app_key] = {
                                            'name': display_name,
                                            'path': registry_path,
                                            'target': registry_path,
                                            'type': 'installed'
                                        }
                            except:
                                pass
                        except:
                            pass
                except:
                    pass
        except Exception as e:
            print(f"Error scanning Registry: {e}")

    def _resolve_lnk(self, lnk_path):
        """Resolve Windows shortcut (.lnk) to target path"""
        try:
            result = subprocess.run(
                ["powershell", "-Command", 
                 f"& {{(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk_path}').TargetPath}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() if result.stdout else lnk_path
        except:
            return lnk_path

    def build_index(self):
        """Build complete app index"""
        print("[AppIndexer] Building app index...")
        self.scan_start_menu()
        self.scan_desktop()
        self.scan_program_files()
        self.scan_directories()
        self.scan_registry()
        
        self.app_list = list(self.apps.values())
        print(f"[AppIndexer] Indexed {len(self.app_list)} applications")
        self._save()
        return self.app_list

    def _save(self):
        """Save index to JSON file"""
        try:
            with open(INDEX_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.apps, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving index: {e}")

    @staticmethod
    def load_index() -> Dict:
        """Load index from JSON file"""
        if os.path.exists(INDEX_FILE):
            try:
                with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def search_app(self, query, threshold=60):
        """Fuzzy search for app by name"""
        if not self.app_list:
            self.build_index()
        
        if not HAS_FUZZY:
            # Simple case-insensitive search without fuzzywuzzy
            query_lower = query.lower()
            for app in self.app_list:
                if query_lower in app['name'].lower():
                    return app
            return None
        
        app_names = [app['name'] for app in self.app_list]
        matches = process.extract(query, app_names, scorer=fuzz.token_set_ratio)
        
        for app_name, score in matches:
            if score >= threshold:
                for app in self.app_list:
                    if app['name'] == app_name:
                        return app
        return None

    def get_app_by_name(self, name):
        """Get app by exact name"""
        return self.apps.get(name.lower())

    def list_all_apps(self):
        """Return list of all indexed apps"""
        if not self.app_list:
            self.build_index()
        return self.app_list

    def export_index(self, filepath):
        """Export index to JSON"""
        with open(filepath, 'w') as f:
            json.dump(self.app_list, f, indent=2)

    def import_index(self, filepath):
        """Import index from JSON"""
        with open(filepath, 'r') as f:
            self.app_list = json.load(f)
            self.apps = {app['name'].lower(): app for app in self.app_list}


# Global instance
_indexer = None


def get_indexer():
    global _indexer
    if _indexer is None:
        _indexer = AppIndexer()
    return _indexer