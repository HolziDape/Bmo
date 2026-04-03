"""
BMO Web Interface - Freund-Version
===================================
Starten: Doppelklick auf START_WEB.bat

Was du brauchst:
  1. config.txt ausfüllen (HOST_IP + Spotify-Daten)
  2. Einmalig SETUP_EINMALIG.bat ausführen
  3. Dann START_WEB.bat starten
  4. Browser öffnet sich automatisch auf http://localhost:5000

Wie es funktioniert:
  - Das Denken (KI, Stimme) läuft auf dem PC deines Freundes
  - Spotify, Shutdown, alles andere läuft auf DEINEM PC
  - Wenn dein Freund Admin-Zugriff aktiviert hat, kannst du
    seinen Screen sehen, Pong spielen usw.
"""

import sys
import os
import logging
import webbrowser
import threading
import time
import subprocess

# ── LOGGING ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "bmo_web.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("BMO-Web-Freund")

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests as req
import psutil
import datetime

app  = Flask(__name__)
CORS(app)

PORT = 5000


# ══════════════════════════════════════════════════════════════════
# CONFIG LESEN
# ══════════════════════════════════════════════════════════════════

def read_config():
    config_path = os.path.join(BASE_DIR, "config.txt")
    if not os.path.exists(config_path):
        log.error("config.txt nicht gefunden!")
        return {}
    cfg = {}
    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line or "=" not in line:
                continue
            key, val = line.split("=", 1)
            cfg[key.strip()] = val.strip()
    return cfg

cfg = read_config()

core_ip   = cfg.get("HOST_IP", cfg.get("CORE_IP", ""))
core_port = int(cfg.get("HOST_CORE_PORT", cfg.get("CORE_PORT", "6000")))
web_port  = int(cfg.get("HOST_WEB_PORT", "5000"))

if not core_ip or core_ip in ("HIER_IP_EINTRAGEN", ""):
    print("\n" + "="*50)
    print("  FEHLER: Bitte erst config.txt ausfüllen!")
    print("  Öffne config.txt und trage die IP ein.")
    print("="*50 + "\n")
    input("Drücke ENTER zum Beenden...")
    sys.exit(1)

CORE_URL = f"http://{core_ip}:{core_port}"
HOST_URL = f"http://{core_ip}:{web_port}"
log.info(f"Core: {CORE_URL}")
log.info(f"Host Web: {HOST_URL}")

# Spotify
SPOTIFY_CLIENT_ID     = cfg.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = cfg.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI  = cfg.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
SPOTIFY_PLAYLIST_ID   = cfg.get("SPOTIFY_PLAYLIST_ID", "")
SPOTIFY_CACHE_PATH    = os.path.join(BASE_DIR, ".spotify_cache")

SPOTIFY_OK = (
    SPOTIFY_CLIENT_ID not in ("", "HIER_CLIENT_ID_EINTRAGEN") and
    SPOTIFY_CLIENT_SECRET not in ("", "HIER_CLIENT_SECRET_EINTRAGEN")
)
if not SPOTIFY_OK:
    log.warning("Spotify nicht konfiguriert.")


# ══════════════════════════════════════════════════════════════════
# LOKALES SPOTIFY
# ══════════════════════════════════════════════════════════════════

_spotify = None

def get_spotify():
    global _spotify
    if _spotify is not None:
        return _spotify
    if not SPOTIFY_OK:
        return None
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        _spotify = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="user-modify-playback-state user-read-playback-state",
            cache_path=SPOTIFY_CACHE_PATH
        ))
        return _spotify
    except Exception as e:
        log.warning(f"Spotify Fehler: {e}")
        return None

def _ensure_spotify_running(sp):
    try:
        devices = sp.devices()
        if not devices['devices']:
            for pfad in [
                os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "Spotify.exe"),
            ]:
                if os.path.exists(pfad):
                    subprocess.Popen([pfad], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    break
            else:
                subprocess.Popen(["explorer.exe", "spotify:"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(8):
                time.sleep(1)
                if sp.devices()['devices']:
                    break
        return sp.devices()['devices']
    except:
        return []

def local_spotify_play(query=""):
    sp = get_spotify()
    if not sp: return "Spotify nicht konfiguriert."
    try:
        devices = _ensure_spotify_running(sp)
        if not devices: return "Spotify startet gerade, versuch es gleich nochmal."
        device_id = devices[0]['id']
        if query:
            results = sp.search(q=query, limit=5, type='track')
            if results['tracks']['items']:
                track = results['tracks']['items'][0]
                sp.start_playback(device_id=device_id, uris=[track['uri']])
                return f"Ich spiele {track['name']} von {track['artists'][0]['name']}."
            return f"Nichts gefunden für '{query}'."
        else:
            sp.start_playback(device_id=device_id)
            return "Musik läuft!"
    except Exception as e:
        return f"Spotify Fehler: {e}"

def local_spotify_pause():
    sp = get_spotify()
    if not sp: return "Spotify nicht konfiguriert."
    try: sp.pause_playback(); return "Musik pausiert."
    except: return "Konnte Musik nicht pausieren."

def local_spotify_resume():
    sp = get_spotify()
    if not sp: return "Spotify nicht konfiguriert."
    try: sp.start_playback(); return "Musik läuft weiter."
    except: return "Konnte Musik nicht fortsetzen."

def local_spotify_next():
    sp = get_spotify()
    if not sp: return "Spotify nicht konfiguriert."
    try: sp.next_track(); return "Nächstes Lied!"
    except: return "Konnte nicht springen."

def local_spotify_playlist():
    sp = get_spotify()
    if not sp: return "Spotify nicht konfiguriert."
    if not SPOTIFY_PLAYLIST_ID or SPOTIFY_PLAYLIST_ID == "HIER_PLAYLIST_ID_EINTRAGEN":
        return "Keine Playlist-ID in config.txt eingetragen."
    try:
        devices = _ensure_spotify_running(sp)
        if not devices: return "Spotify startet gerade, versuch es gleich nochmal."
        device_id = devices[0]['id']
        sp.start_playback(device_id=device_id, context_uri=f"spotify:playlist:{SPOTIFY_PLAYLIST_ID}")
        return "Deine Playlist läuft!"
    except Exception as e:
        return f"Fehler: {e}"

def local_spotify_volume(level):
    sp = get_spotify()
    if not sp: return "Spotify nicht konfiguriert."
    try:
        level = max(0, min(100, int(level)))
        sp.volume(level)
        return f"Lautstärke auf {level}%."
    except Exception as e:
        return f"Fehler: {e}"

def local_spotify_get_volume():
    sp = get_spotify()
    if not sp: return None
    try:
        playback = sp.current_playback()
        if playback and playback.get('device'):
            return playback['device']['volume_percent']
    except:
        pass
    return None


# ══════════════════════════════════════════════════════════════════
# LOKALE AKTIONEN
# ══════════════════════════════════════════════════════════════════

def handle_local_action(action, action_params):
    if action == "shutdown_pc":
        threading.Thread(target=lambda: (time.sleep(2), subprocess.run(["shutdown", "/s", "/t", "0"])), daemon=True).start()
        return "Tschüss! Ich fahre jetzt herunter."
    elif action == "spotify_play":    return local_spotify_play(action_params.get("query", ""))
    elif action == "spotify_pause":   return local_spotify_pause()
    elif action == "spotify_resume":  return local_spotify_resume()
    elif action == "spotify_next":    return local_spotify_next()
    elif action == "spotify_playlist": return local_spotify_playlist()
    elif action == "spotify_volume":  return local_spotify_volume(action_params.get("level", 50))
    return None


# ══════════════════════════════════════════════════════════════════
# ADMIN-ZUGRIFF (für deinen Freund — er kann dich steuern)
# ══════════════════════════════════════════════════════════════════

_admin_enabled = False

# Screen-Stream
_SCREEN_OK = False
try:
    import mss as _mss_lib
    _SCREEN_OK = True
except ImportError:
    pass

def _screen_generator():
    try:
        import mss
        from PIL import Image
        import io
        with mss.mss() as sct:
            mon = sct.monitors[1]
            while True:
                img = sct.grab(mon)
                pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                pil.thumbnail((1280, 720))
                buf = io.BytesIO()
                pil.save(buf, format="JPEG", quality=55)
                frame = buf.getvalue()
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                time.sleep(0.083)
    except Exception as e:
        log.warning(f"Screen-Stream Fehler: {e}")


# ══════════════════════════════════════════════════════════════════
# HTML
# ══════════════════════════════════════════════════════════════════

HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>BMO</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
  :root {
    --green: #2b8773; --green-dark: #1f6458;
    --bg: #1a1a2e; --bg2: #16213e; --bg3: #0f1628;
    --border: #2b3a5c; --text: #eee; --text2: #aaa; --text3: #64748b;
  }
  html, body { height: 100%; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); overflow: hidden; }
  .app { display: flex; flex-direction: column; height: 100dvh; }
  header { background: var(--green); padding: 12px 16px; display: flex; align-items: center; gap: 10px; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.3); }
  header h1 { font-size: 20px; font-weight: 700; }
  header .sub { font-size: 12px; opacity: 0.8; }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: #4ade80; animation: pulse 2s infinite; flex-shrink: 0; }
  .dot.off { background: #ef4444; animation: none; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
  .quick-btns { display: flex; gap: 8px; padding: 10px 12px; overflow-x: auto; flex-shrink: 0; background: var(--bg2); border-bottom: 1px solid var(--border); scrollbar-width: none; }
  .quick-btns::-webkit-scrollbar { display: none; }
  .qbtn { display: flex; flex-direction: column; align-items: center; gap: 4px; background: var(--bg3); border: 1px solid var(--border); border-radius: 14px; padding: 10px 14px; cursor: pointer; flex-shrink: 0; min-width: 70px; transition: background .15s, transform .1s; color: var(--text); font-size: 11px; font-weight: 500; user-select: none; }
  .qbtn:active { transform: scale(.93); background: var(--border); }
  .qbtn .icon { font-size: 22px; line-height: 1; }
  .qbtn.green { border-color: var(--green); }
  .qbtn.red { border-color: #ef4444; color: #ef4444; }
  .qbtn.orange { border-color: #f97316; color: #f97316; }
  .qbtn.purple { border-color: #a855f7; color: #a855f7; }
  .chat { flex: 1; overflow-y: auto; padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; overscroll-behavior: contain; }
  .msg { max-width: 82%; padding: 10px 13px; border-radius: 18px; font-size: 15px; line-height: 1.45; animation: fadeIn .2s ease; word-break: break-word; }
  @keyframes fadeIn { from{opacity:0;transform:translateY(5px)} to{opacity:1} }
  .msg.user { align-self: flex-end; background: var(--green); border-bottom-right-radius: 4px; }
  .msg.bmo  { align-self: flex-start; background: var(--bg2); border: 1px solid var(--border); border-bottom-left-radius: 4px; }
  .msg.bmo audio { margin-top: 8px; width: 100%; border-radius: 8px; }
  .msg.sys  { align-self: center; background: transparent; color: var(--text2); font-size: 12px; padding: 2px 8px; }
  .typing { align-self: flex-start; background: var(--bg2); border: 1px solid var(--border); border-radius: 18px; border-bottom-left-radius: 4px; padding: 12px 16px; display: none; }
  .typing span { display: inline-block; width: 7px; height: 7px; background: var(--green); border-radius: 50%; margin: 0 2px; animation: bounce 1.2s infinite; }
  .typing span:nth-child(2){animation-delay:.2s} .typing span:nth-child(3){animation-delay:.4s}
  @keyframes bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-6px)}}
  .input-area { padding: 10px 12px; padding-bottom: max(10px, env(safe-area-inset-bottom)); background: var(--bg2); border-top: 1px solid var(--border); display: flex; gap: 8px; align-items: flex-end; flex-shrink: 0; }
  textarea { flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: 20px; padding: 10px 15px; color: var(--text); font-size: 16px; resize: none; max-height: 100px; outline: none; font-family: inherit; line-height: 1.4; }
  textarea:focus { border-color: var(--green); }
  .ibtn { border: none; border-radius: 50%; width: 44px; height: 44px; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 18px; transition: transform .1s; }
  .ibtn:active { transform: scale(.9); }
  #sendBtn { background: var(--green); color: #fff; }
  #sendBtn:disabled { opacity: .4; }
  #micBtn { background: #1e3a5f; color: #fff; }
  #micBtn.rec { background: #dc2626; animation: pulse .8s infinite; }
  .overlay { position: fixed; inset: 0; background: rgba(0,0,0,.7); display: flex; align-items: flex-end; justify-content: center; z-index: 100; opacity: 0; pointer-events: none; transition: opacity .2s; }
  .overlay.show { opacity: 1; pointer-events: all; }
  .sheet { background: var(--bg2); border-radius: 20px 20px 0 0; padding: 20px 16px; padding-bottom: max(20px, env(safe-area-inset-bottom)); width: 100%; max-width: 600px; transform: translateY(100%); transition: transform .25s cubic-bezier(.32,1,.23,1); max-height: 85dvh; overflow-y: auto; }
  .overlay.show .sheet { transform: translateY(0); }
  .sheet-handle { width: 40px; height: 4px; background: var(--border); border-radius: 2px; margin: 0 auto 16px; }
  .sheet h2 { font-size: 18px; font-weight: 600; margin-bottom: 16px; }
  .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
  .stat-card { background: var(--bg3); border: 1px solid var(--border); border-radius: 14px; padding: 14px; }
  .stat-card .val { font-size: 26px; font-weight: 700; color: var(--green); }
  .stat-card .lbl { font-size: 12px; color: var(--text2); margin-top: 2px; }
  .stat-card .bar { height: 4px; background: var(--border); border-radius: 2px; margin-top: 8px; overflow: hidden; }
  .stat-card .bar-fill { height: 100%; background: var(--green); border-radius: 2px; transition: width .5s; }
  .stat-card .bar-fill.warn { background: #f97316; }
  .stat-card .bar-fill.crit { background: #ef4444; }
  .btn-primary { width: 100%; padding: 14px; background: var(--green); border: none; border-radius: 14px; color: #fff; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 8px; }
  .confirm-btns { display: flex; gap: 10px; margin-top: 8px; }
  .confirm-btns button { flex: 1; padding: 14px; border: none; border-radius: 14px; font-size: 16px; font-weight: 600; cursor: pointer; }
  .btn-cancel { background: var(--bg3) !important; color: var(--text) !important; border: 1px solid var(--border) !important; }
  .btn-confirm { background: #ef4444; color: #fff; }
  .screen-overlay { align-items: stretch; }
  .screen-sheet { background: var(--bg2); width: 100%; max-width: 900px; margin: auto; border-radius: 16px; overflow: hidden; display: flex; flex-direction: column; max-height: 95dvh; }
  .screen-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; border-bottom: 1px solid var(--border); }
  .screen-sheet img { width: 100%; display: block; object-fit: contain; flex: 1; }
</style>
</head>
<body>
<div class="app">
  <header>
    <div class="dot" id="coreDot"></div>
    <div>
      <h1>BMO</h1>
      <span class="sub" id="coreStatus">Verbinde...</span>
    </div>
  </header>

  <div class="quick-btns">
    <button class="qbtn green" onclick="showStats()">
      <span class="icon">📊</span>Stats
    </button>
    <button class="qbtn purple" onclick="showSpotify()">
      <span class="icon">🎵</span>Spotify
    </button>
    <button class="qbtn orange" onclick="confirmShutdown()">
      <span class="icon">⏻</span>Shutdown
    </button>
    <button class="qbtn" onclick="showHostScreen()" style="border-color:#0ea5e9;color:#38bdf8;">
      <span class="icon">🖥️</span>Host Screen
    </button>
    <button class="qbtn" onclick="showPong()" style="border-color:#22c55e;color:#4ade80;">
      <span class="icon">🏓</span>Pong
    </button>
    <button class="qbtn" onclick="showAdminSettings()" style="border-color:#475569;color:#94a3b8;">
      <span class="icon">⚙️</span>Settings
    </button>
  </div>

  <div class="chat" id="chat">
    <div class="msg sys">BMO ist bereit 👾</div>
  </div>
  <div class="typing" id="typing"><span></span><span></span><span></span></div>

  <div class="input-area">
    <textarea id="input" placeholder="Schreib BMO was..." rows="1"></textarea>
    <button class="ibtn" id="micBtn">🎤</button>
    <button class="ibtn" id="sendBtn">➤</button>
  </div>
</div>

<!-- STATS OVERLAY -->
<div class="overlay" id="statsOverlay" onclick="closeOverlay('statsOverlay')">
  <div class="sheet" onclick="event.stopPropagation()">
    <div class="sheet-handle"></div>
    <h2>System Stats</h2>
    <div class="stats-grid">
      <div class="stat-card"><div class="val" id="sCpu">--</div><div class="lbl">CPU %</div><div class="bar"><div class="bar-fill" id="sCpuBar" style="width:0%"></div></div></div>
      <div class="stat-card"><div class="val" id="sRam">--</div><div class="lbl">RAM %</div><div class="bar"><div class="bar-fill" id="sRamBar" style="width:0%"></div></div></div>
      <div class="stat-card"><div class="val" id="sTime">--</div><div class="lbl">Uhrzeit</div></div>
    </div>
    <button onclick="closeOverlay('statsOverlay')" class="btn-primary" style="background:var(--bg3);border:1px solid var(--border);color:var(--text);">Schließen</button>
  </div>
</div>

<!-- SHUTDOWN CONFIRM -->
<div class="overlay" id="shutdownOverlay" onclick="closeOverlay('shutdownOverlay')">
  <div class="sheet" onclick="event.stopPropagation()">
    <div class="sheet-handle"></div>
    <h2>⏻ PC ausschalten?</h2>
    <p style="color:var(--text2);font-size:14px;margin-bottom:16px;">Dein PC wird heruntergefahren.</p>
    <div class="confirm-btns">
      <button class="btn-cancel" onclick="closeOverlay('shutdownOverlay')">Abbrechen</button>
      <button class="btn-confirm" onclick="doShutdown()">Ausschalten</button>
    </div>
  </div>
</div>

<!-- SPOTIFY OVERLAY -->
<div class="overlay" id="spotifyOverlay" onclick="closeOverlay('spotifyOverlay')">
  <div class="sheet" onclick="event.stopPropagation()">
    <div class="sheet-handle"></div>
    <h2>🎵 Spotify</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px;">
      <button onclick="spPlaylist()" style="padding:14px;background:var(--green);border:none;border-radius:14px;color:#fff;font-size:15px;font-weight:600;cursor:pointer;">▶ Playlist</button>
      <button onclick="spPause()"    style="padding:14px;background:var(--bg3);border:1px solid var(--border);border-radius:14px;color:var(--text);font-size:15px;font-weight:600;cursor:pointer;">⏸ Pause</button>
      <button onclick="spResume()"   style="padding:14px;background:var(--bg3);border:1px solid var(--border);border-radius:14px;color:var(--text);font-size:15px;font-weight:600;cursor:pointer;">▶ Weiter</button>
      <button onclick="spSkip()"     style="padding:14px;background:var(--bg3);border:1px solid var(--border);border-radius:14px;color:var(--text);font-size:15px;font-weight:600;cursor:pointer;">⏭ Skip</button>
    </div>
    <div style="margin-bottom:20px;">
      <div style="font-size:13px;color:var(--text2);margin-bottom:10px;">🔊 Lautstärke</div>
      <div style="display:flex;align-items:center;gap:12px;">
        <span style="font-size:18px;">🔈</span>
        <input type="range" id="volSlider" min="0" max="100" value="50"
          style="flex:1;accent-color:var(--green);height:6px;cursor:pointer;"
          oninput="document.getElementById('volLabel').textContent=this.value+'%'"
          onchange="setVolume(this.value)">
        <span style="font-size:18px;">🔊</span>
      </div>
      <div style="text-align:center;margin-top:8px;font-size:22px;font-weight:700;color:var(--green)" id="volLabel">50%</div>
    </div>
    <button onclick="closeOverlay('spotifyOverlay')" class="btn-primary" style="background:var(--bg3);border:1px solid var(--border);color:var(--text);">Schließen</button>
  </div>
</div>

<!-- HOST SCREEN OVERLAY -->
<div class="overlay screen-overlay" id="hostScreenOverlay">
  <div class="screen-sheet" onclick="event.stopPropagation()">
    <div class="screen-header">
      <span style="font-weight:600;font-size:15px;color:#38bdf8;">🖥️ Host – Bildschirm Live</span>
      <div style="display:flex;gap:8px;align-items:center;">
        <span id="hostScreenStatus" style="font-size:11px;color:#64748b;"></span>
        <button onclick="closeHostScreen()"
          style="background:none;border:1px solid #334155;border-radius:8px;color:#94a3b8;padding:5px 12px;cursor:pointer;font-size:13px;">
          ✕
        </button>
      </div>
    </div>
    <img id="hostScreenImg" src="" alt="Host Bildschirm wird geladen...">
  </div>
</div>

<!-- PONG OVERLAY -->
<div class="overlay" id="pongOverlay" onclick="void(0)">
  <div class="sheet" onclick="event.stopPropagation()" style="max-width:640px;">
    <div class="sheet-handle"></div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
      <h2 style="margin:0;">🏓 BMO Pong</h2>
      <button onclick="closePong()"
        style="background:none;border:1px solid var(--border);border-radius:8px;color:var(--text2);padding:5px 12px;font-size:13px;cursor:pointer;">✕</button>
    </div>
    <div style="display:flex;justify-content:center;gap:24px;margin-bottom:8px;">
      <span id="pongScoreL" style="font-size:36px;font-weight:700;color:#2b8773;">0</span>
      <span style="font-size:36px;color:#475569;">:</span>
      <span id="pongScoreR" style="font-size:36px;font-weight:700;color:#f97316;">0</span>
    </div>
    <canvas id="pongCanvas" width="600" height="380"
      style="width:100%;display:block;border-radius:12px;background:#0a0a1a;touch-action:none;cursor:crosshair;"></canvas>
    <div id="pongInfo" style="text-align:center;color:var(--text2);font-size:13px;margin-top:8px;">Verbinde...</div>
    <div style="display:flex;gap:8px;margin-top:10px;">
      <button onclick="pongReset()"
        style="flex:1;padding:12px;background:var(--bg3);border:1px solid var(--border);border-radius:12px;color:var(--text);font-size:14px;cursor:pointer;">
        ↺ Reset
      </button>
      <button onclick="closePong()"
        style="flex:1;padding:12px;background:var(--bg3);border:1px solid var(--border);border-radius:12px;color:var(--text);font-size:14px;cursor:pointer;">
        Beenden
      </button>
    </div>
  </div>
</div>

<!-- SETTINGS OVERLAY -->
<div class="overlay" id="adminSettingsOverlay" onclick="closeOverlay('adminSettingsOverlay')">
  <div class="sheet" onclick="event.stopPropagation()">
    <div class="sheet-handle"></div>
    <h2>⚙️ Settings</h2>
    <div style="color:var(--text2);font-size:13px;margin-bottom:8px;">Admin-Zugriff für deinen Freund</div>
    <div style="color:var(--text3);font-size:12px;margin-bottom:12px;">
      Wenn AN: dein Freund kann deinen Screen sehen, Notifications senden und Pong spielen.
    </div>
    <button id="adminToggleBtn" onclick="toggleAdmin()"
      style="width:100%;padding:14px;background:var(--bg3);border:1px solid var(--border);border-radius:14px;color:var(--text2);font-size:15px;cursor:pointer;transition:border-color .2s,color .2s;">
      🔒 Admin-Zugriff: AUS
    </button>
    <button class="btn-primary" onclick="closeOverlay('adminSettingsOverlay')" style="background:var(--bg3);border:1px solid var(--border);color:var(--text);margin-top:10px;">Schließen</button>
  </div>
</div>

<script>
const chat   = document.getElementById('chat');
const input  = document.getElementById('input');
const sendBtn= document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const typing = document.getElementById('typing');

// ── STATUS ──────────────────────────────────────────────────────
async function updateStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    document.getElementById('coreDot').classList.remove('off');
    document.getElementById('coreStatus').textContent = 'Online · ' + d.time;
    const cpu = d.cpu || 0, ram = d.ram || 0;
    document.getElementById('sCpu').textContent  = cpu + '%';
    document.getElementById('sRam').textContent  = ram + '%';
    document.getElementById('sTime').textContent = d.time || '--';
    const cpuBar = document.getElementById('sCpuBar');
    cpuBar.style.width = cpu + '%';
    cpuBar.className = 'bar-fill' + (cpu > 90 ? ' crit' : cpu > 70 ? ' warn' : '');
    const ramBar = document.getElementById('sRamBar');
    ramBar.style.width = ram + '%';
    ramBar.className = 'bar-fill' + (ram > 90 ? ' crit' : ram > 70 ? ' warn' : '');
  } catch(e) {
    document.getElementById('coreDot').classList.add('off');
    document.getElementById('coreStatus').textContent = 'Core offline';
  }
}
updateStatus();
setInterval(updateStatus, 5000);

function showStats()      { updateStatus(); document.getElementById('statsOverlay').classList.add('show'); }
function confirmShutdown(){ document.getElementById('shutdownOverlay').classList.add('show'); }
function closeOverlay(id) { document.getElementById(id).classList.remove('show'); }
function doShutdown()     { closeOverlay('shutdownOverlay'); quickAction('schalte den PC aus'); }

// ── SPOTIFY ──────────────────────────────────────────────────────
async function showSpotify() {
  try {
    const r = await fetch('/api/spotify/volume');
    const d = await r.json();
    if (d.volume !== null && d.volume !== undefined) {
      document.getElementById('volSlider').value = d.volume;
      document.getElementById('volLabel').textContent = d.volume + '%';
    }
  } catch(e) {}
  document.getElementById('spotifyOverlay').classList.add('show');
}
async function setVolume(val) {
  try { await fetch('/api/spotify/volume', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({level: parseInt(val)})}); } catch(e) {}
}
async function spPlaylist() { try { const r = await fetch('/api/spotify/playlist', {method:'POST'}); const d = await r.json(); addMsg(d.response, 'bmo'); } catch(e) {} }
async function spPause()   { quickAction('pause'); }
async function spResume()  { quickAction('weiter'); }
async function spSkip()    { quickAction('nächstes Lied'); }

// ── HOST SCREEN ──────────────────────────────────────────────────
let _hostScreenActive = false;
function showHostScreen() {
  _hostScreenActive = true;
  document.getElementById('hostScreenStatus').textContent = 'Verbinde...';
  document.getElementById('hostScreenOverlay').classList.add('show');
  const img = document.getElementById('hostScreenImg');
  img.src = '/api/host/screen?' + Date.now();
  img.onload  = () => { document.getElementById('hostScreenStatus').textContent = 'Live'; };
  img.onerror = () => { document.getElementById('hostScreenStatus').textContent = '⛔ Kein Zugriff'; img.src = ''; };
}
function closeHostScreen() {
  _hostScreenActive = false;
  document.getElementById('hostScreenOverlay').classList.remove('show');
  setTimeout(() => { if (!_hostScreenActive) document.getElementById('hostScreenImg').src = ''; }, 300);
}

// ── PONG ─────────────────────────────────────────────────────────
let _pongActive = false, _pongRAF = null, _pongPoll = null;
let _myPaddleY = 0.5;

async function showPong() {
  // Wir spielen rechts auf dem Host
  try {
    const r = await fetch('/api/host/pong/state');
    const d = await r.json();
    if (!d.running) {
      addMsg('⛔ Host spielt gerade kein Pong (oder Admin-Zugriff ist aus).', 'sys');
      return;
    }
  } catch(e) { addMsg('Host nicht erreichbar 😢', 'sys'); return; }

  _pongActive = true;
  document.getElementById('pongOverlay').classList.add('show');
  document.getElementById('pongInfo').textContent = '🟠 Du = rechtes Paddle (Maus/Touch)';
  _startPongInput();
  _startPongRender();
}
function closePong() {
  _pongActive = false;
  if (_pongRAF)  cancelAnimationFrame(_pongRAF);
  if (_pongPoll) clearInterval(_pongPoll);
  document.getElementById('pongOverlay').classList.remove('show');
}
async function pongReset() { closePong(); await new Promise(r => setTimeout(r, 200)); showPong(); }

function _startPongInput() {
  const canvas = document.getElementById('pongCanvas');
  function updateY(e) {
    const rect = canvas.getBoundingClientRect();
    const t = e.touches ? e.touches[0] : e;
    _myPaddleY = Math.max(0.08, Math.min(0.92, (t.clientY - rect.top) / rect.height));
  }
  canvas.onmousemove  = updateY;
  canvas.ontouchmove  = e => { e.preventDefault(); updateY(e); };
  canvas.ontouchstart = e => { e.preventDefault(); updateY(e); };
  _pongPoll = setInterval(() => {
    if (!_pongActive) return;
    fetch('/api/host/pong/paddle', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({side: 'right', y: _myPaddleY})
    }).catch(()=>{});
  }, 40);
}

function _startPongRender() {
  const canvas = document.getElementById('pongCanvas');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  let state = null, frame = 0;
  async function fetchState() {
    try { state = await (await fetch('/api/host/pong/state')).json(); } catch(e) {}
  }
  function loop() {
    if (!_pongActive) return;
    if (frame++ % 2 === 0) fetchState();
    ctx.fillStyle = '#0a0a1a'; ctx.fillRect(0, 0, W, H);
    ctx.setLineDash([8,12]); ctx.strokeStyle = '#1e293b'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(W/2,0); ctx.lineTo(W/2,H); ctx.stroke();
    ctx.setLineDash([]);
    if (state) {
      document.getElementById('pongScoreL').textContent = state.score_l ?? 0;
      document.getElementById('pongScoreR').textContent = state.score_r ?? 0;
      const ph = H * 0.15, pw = 12;
      ctx.fillStyle = '#1e4d43';
      _rr(ctx, 8, state.left * H - ph/2, pw, ph, 4);
      ctx.fillStyle = '#f97316';
      _rr(ctx, W-8-pw, state.right * H - ph/2, pw, ph, 4);
      ctx.strokeStyle='#4ade80'; ctx.lineWidth=2;
      _rr(ctx, W-8-pw, state.right*H-ph/2, pw, ph, 4, true);
      const bx = state.ball.x * W, by = state.ball.y * H;
      const grd = ctx.createRadialGradient(bx,by,0,bx,by,14);
      grd.addColorStop(0,'rgba(255,255,255,.9)'); grd.addColorStop(1,'rgba(255,255,255,0)');
      ctx.fillStyle = grd; ctx.beginPath(); ctx.arc(bx,by,14,0,Math.PI*2); ctx.fill();
      ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(bx,by,6,0,Math.PI*2); ctx.fill();
    }
    _pongRAF = requestAnimationFrame(loop);
  }
  fetchState(); loop();
}
function _rr(ctx, x, y, w, h, r, stroke=false) {
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(x,y,w,h,r); else ctx.rect(x,y,w,h);
  stroke ? ctx.stroke() : ctx.fill();
}

// ── ADMIN SETTINGS ───────────────────────────────────────────────
let _adminOn = false;
function showAdminSettings() { document.getElementById('adminSettingsOverlay').classList.add('show'); }
async function toggleAdmin() {
  try {
    const r = await fetch('/api/admin/toggle', {method:'POST'});
    const d = await r.json();
    _adminOn = d.enabled;
    const btn = document.getElementById('adminToggleBtn');
    btn.textContent    = _adminOn ? '🔓 Admin-Zugriff: AN' : '🔒 Admin-Zugriff: AUS';
    btn.style.borderColor = _adminOn ? '#4ade80' : 'var(--border)';
    btn.style.color       = _adminOn ? '#4ade80' : 'var(--text2)';
  } catch(e) {}
}

// ── CHAT ─────────────────────────────────────────────────────────
async function quickAction(msg) {
  addMsg(msg, 'user');
  setTyping(true);
  try {
    const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message: msg})});
    const d = await r.json();
    setTyping(false);
    addMsg(d.response, 'bmo', d.audio);
  } catch(e) {
    setTyping(false);
    addMsg('Verbindungsfehler 😢', 'sys');
  }
}

function addMsg(text, role, audioB64=null) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.textContent = text;
  if (audioB64) {
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.src = 'data:audio/wav;base64,' + audioB64;
    div.appendChild(audio);
    setTimeout(() => audio.play(), 100);
  }
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function setTyping(show) {
  typing.style.display = show ? 'flex' : 'none';
  chat.scrollTop = chat.scrollHeight;
}

async function send() {
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;
  addMsg(text, 'user');
  setTyping(true);
  try {
    const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message: text})});
    const d = await r.json();
    setTyping(false);
    addMsg(d.response, 'bmo', d.audio || null);
  } catch(e) {
    setTyping(false);
    addMsg('Verbindungsfehler 😢', 'sys');
  }
  sendBtn.disabled = false;
  input.focus();
}

sendBtn.addEventListener('click', send);
input.addEventListener('keydown', e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
input.addEventListener('input', () => { input.style.height='auto'; input.style.height=Math.min(input.scrollHeight,100)+'px'; });

let mediaRecorder, audioChunks=[], recording=false;
micBtn.addEventListener('click', async () => {
  if (!recording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio:true});
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunks, {type:'audio/webm'});
        const reader = new FileReader();
        reader.onload = async () => {
          const b64 = reader.result.split(',')[1];
          setTyping(true);
          try {
            const r = await fetch('/api/voice', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({audio: b64})});
            const d = await r.json();
            setTyping(false);
            if (d.transcript) addMsg(d.transcript, 'user');
            addMsg(d.response, 'bmo', d.audio||null);
          } catch(e) { setTyping(false); addMsg('Sprachfehler 😢', 'sys'); }
        };
        reader.readAsDataURL(blob);
        stream.getTracks().forEach(t => t.stop());
      };
      mediaRecorder.start();
      recording = true;
      micBtn.classList.add('rec');
      micBtn.textContent = '⏹';
    } catch(e) { alert('Mikrofon verweigert!'); }
  } else {
    mediaRecorder.stop();
    recording = false;
    micBtn.classList.remove('rec');
    micBtn.textContent = '🎤';
  }
});
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════
# ROUTES — CHAT / VOICE / STATUS
# ══════════════════════════════════════════════════════════════════

def _chat_and_act(message):
    try:
        r = req.post(f"{CORE_URL}/process", json={"message": message, "remote": True}, timeout=60)
        d = r.json()
    except Exception as e:
        return f"Core nicht erreichbar: {e}", None
    response_text = d.get("response", "")
    action        = d.get("action")
    action_params = d.get("action_params", {})
    local_result  = handle_local_action(action, action_params)
    if local_result:
        response_text = local_result
    audio_b64 = None
    if response_text:
        try:
            rs = req.post(f"{CORE_URL}/speak", json={"text": response_text}, timeout=120)
            audio_b64 = rs.json().get("audio")
        except:
            pass
    return response_text, audio_b64

@app.route('/')
def index():
    return HTML

@app.route('/api/status')
def status():
    try:
        r = req.get(f"{CORE_URL}/status", timeout=2)
        return jsonify(r.json())
    except:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        t   = datetime.datetime.now().strftime('%H:%M')
        return jsonify(cpu=cpu, ram=ram, time=t, gpu=None)

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    data    = request.json or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify(response="Ich habe nichts verstanden.", audio=None)
    response, audio = _chat_and_act(message)
    return jsonify(response=response, audio=audio)

@app.route('/api/voice', methods=['POST'])
def voice_endpoint():
    data = request.json or {}
    b64  = data.get('audio', '')
    if not b64:
        return jsonify(transcript='', response='Kein Audio empfangen.', audio=None)
    try:
        tr = req.post(f"{CORE_URL}/transcribe", json={"audio": b64, "format": "webm", "remote": True}, timeout=30)
        d  = tr.json()
        transcript    = d.get('transcript', '')
        if not transcript:
            return jsonify(transcript='', response='Ich habe dich nicht verstanden.', audio=None)
        response_text = d.get("response", "")
        local_result  = handle_local_action(d.get("action"), d.get("action_params", {}))
        if local_result:
            response_text = local_result
        audio_b64 = None
        if response_text:
            try:
                rs = req.post(f"{CORE_URL}/speak", json={"text": response_text}, timeout=120)
                audio_b64 = rs.json().get("audio")
            except:
                pass
        return jsonify(transcript=transcript, response=response_text, audio=audio_b64)
    except Exception as e:
        return jsonify(transcript='', response=f"Fehler: {e}", audio=None)

@app.route('/api/spotify/playlist', methods=['POST'])
def spotify_playlist_route():
    return jsonify(response=local_spotify_playlist())

@app.route('/api/spotify/volume', methods=['GET', 'POST'])
def spotify_volume_route():
    if request.method == 'GET':
        return jsonify(volume=local_spotify_get_volume())
    level = (request.json or {}).get('level', 50)
    return jsonify(response=local_spotify_volume(level), volume=level)


# ══════════════════════════════════════════════════════════════════
# ROUTES — HOST PROXY (Zugriff auf deines Freundes BMO)
# ══════════════════════════════════════════════════════════════════

@app.route('/api/host/screen')
def host_screen():
    try:
        r = req.get(f"{HOST_URL}/api/admin/screen", stream=True, timeout=10)
        if r.status_code == 403:
            return jsonify(error="Host hat Admin-Zugriff nicht aktiviert."), 403
        return Response(r.iter_content(chunk_size=4096),
                        content_type=r.headers.get('Content-Type', 'multipart/x-mixed-replace; boundary=frame'))
    except Exception as e:
        return jsonify(error=str(e)), 503

@app.route('/api/host/pong/state')
def host_pong_state():
    try:
        r = req.get(f"{HOST_URL}/api/admin/pong/state", timeout=3)
        return jsonify(**r.json())
    except Exception as e:
        return jsonify(running=False, error=str(e))

@app.route('/api/host/pong/paddle', methods=['POST'])
def host_pong_paddle():
    try:
        r = req.post(f"{HOST_URL}/api/admin/pong/paddle", json=request.json or {}, timeout=2)
        return jsonify(**r.json())
    except Exception as e:
        return jsonify(ok=False, error=str(e))

@app.route('/api/host/notify', methods=['POST'])
def host_notify():
    try:
        r = req.post(f"{HOST_URL}/api/admin/notify", json=request.json or {}, timeout=5)
        return jsonify(**r.json())
    except Exception as e:
        return jsonify(ok=False, error=str(e))


# ══════════════════════════════════════════════════════════════════
# ROUTES — ADMIN (dein Freund greift auf DICH zu)
# ══════════════════════════════════════════════════════════════════

def _admin_check():
    if not _admin_enabled:
        from flask import abort
        abort(403)

@app.route('/api/admin/toggle', methods=['POST'])
def admin_toggle():
    global _admin_enabled
    _admin_enabled = not _admin_enabled
    log.info(f"Admin-Zugriff: {'AN' if _admin_enabled else 'AUS'}")
    return jsonify(enabled=_admin_enabled)

@app.route('/api/admin/screen')
def admin_screen():
    _admin_check()
    if not _SCREEN_OK:
        return jsonify(error="mss nicht installiert: pip install mss Pillow"), 503
    return Response(_screen_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/admin/pong/state')
def admin_pong_state():
    _admin_check()
    # Freund-Version hat kein eigenes Pong — leere State zurückgeben
    return jsonify(running=False, ball={'x':0.5,'y':0.5,'vx':0,'vy':0},
                   left=0.5, right=0.5, score_l=0, score_r=0, right_human=False)

@app.route('/api/admin/pong/paddle', methods=['POST'])
def admin_pong_paddle():
    _admin_check()
    return jsonify(ok=True)

@app.route('/api/admin/pong/challenge', methods=['POST'])
def admin_pong_challenge():
    _admin_check()
    try:
        from winotify import Notification
        toast = Notification(app_id="BMO", title="🏓 Pong-Challenge!", msg="Dein Freund fordert dich heraus!")
        toast.show()
    except Exception:
        pass
    return jsonify(ok=True)

@app.route('/api/admin/notify', methods=['POST'])
def admin_notify():
    _admin_check()
    data    = request.json or {}
    title   = str(data.get('title', 'BMO'))[:64]
    message = str(data.get('message', ''))[:256]
    if not message:
        return jsonify(ok=False, error="Keine Nachricht.")
    try:
        try:
            from winotify import Notification
            toast = Notification(app_id="BMO", title=title, msg=message)
            toast.show()
        except ImportError:
            t = title.replace('"','').replace("'",'')
            m = message.replace('"','').replace("'",'')
            ps = (
                'Add-Type -AssemblyName System.Windows.Forms;'
                '$n=New-Object System.Windows.Forms.NotifyIcon;'
                '$n.Icon=[System.Drawing.SystemIcons]::Information;'
                '$n.Visible=$true;'
                f'$n.ShowBalloonTip(4000,\'{t}\',\'{m}\',[System.Windows.Forms.ToolTipIcon]::Info);'
                'Start-Sleep 5; $n.Dispose()'
            )
            subprocess.Popen(['powershell', '-WindowStyle', 'Hidden', '-Command', ps])
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e))

@app.route('/api/admin/processes')
def admin_processes():
    _admin_check()
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = p.info
            procs.append({'pid': info['pid'], 'name': info['name'] or '?',
                          'cpu': round(info['cpu_percent'] or 0, 1),
                          'mem': round(info['memory_percent'] or 0, 1)})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x['mem'], reverse=True)
    return jsonify(processes=procs[:80])

@app.route('/api/admin/processes/<int:pid>/kill', methods=['POST'])
def admin_kill_process(pid):
    _admin_check()
    try:
        p = psutil.Process(pid)
        name = p.name()
        p.terminate()
        return jsonify(ok=True, name=name)
    except psutil.NoSuchProcess:
        return jsonify(ok=False, error="Prozess nicht gefunden.")
    except psutil.AccessDenied:
        return jsonify(ok=False, error="Zugriff verweigert.")
    except Exception as e:
        return jsonify(ok=False, error=str(e))


# ══════════════════════════════════════════════════════════════════
# START
# ══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    log.info(f"BMO Web (Freund-Version) startet auf Port {PORT}...")
    log.info(f"Core: {CORE_URL}  |  Host Web: {HOST_URL}")
    try:
        r = req.get(f"{CORE_URL}/ping", timeout=3)
        log.info("Core erreichbar!")
    except:
        log.warning("Core nicht erreichbar — stelle sicher dass dein Freund BMO gestartet hat.")

    def _open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{PORT}")
    threading.Thread(target=_open_browser, daemon=True).start()

    app.run(host='0.0.0.0', port=PORT, debug=False)
