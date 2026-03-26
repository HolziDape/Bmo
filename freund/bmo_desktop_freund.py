"""
BMO Desktop - Freund-Version
==============================
Starten: Doppelklick auf START_DESKTOP.bat

Was du brauchst:
  1. config.txt: Trage dort die IP von deinem Freund ein
  2. Einmalig SETUP_EINMALIG.bat ausführen (installiert alles)
  3. Dann START_DESKTOP.bat starten

Was BMO dann kann:
  - Sag "Hey BMO" um ihn aufzuwecken
  - Sprich dann mit ihm
  - Er verbindet sich mit dem PC deines Freundes
"""

import os
import sys
import numpy as np
import sounddevice as sd
from openwakeword.model import Model
import speech_recognition as sr
import pygame
import random
import time
import threading
import requests as req
import base64
import soundfile as sf
import tempfile
import ssl

# Global die SSL-Prüfung ausschalten
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context


# ══════════════════════════════════════════════════════════════════
# CONFIG LESEN
# ══════════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def read_config():
    config_path = os.path.join(BASE_DIR, "config.txt")
    if not os.path.exists(config_path):
        print("❌ FEHLER: config.txt nicht gefunden!")
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
core_ip   = cfg.get("CORE_IP", "")
core_port = int(cfg.get("CORE_PORT", "6000"))

if not core_ip or core_ip == "HIER_IP_EINTRAGEN":
    print("\n" + "="*50)
    print("  Bitte erst config.txt ausfüllen!")
    print("="*50 + "\n")
    input("Drücke ENTER zum Beenden...")
    sys.exit(1)

CORE_URL = f"http://{core_ip}:{core_port}"
print(f"Core-Adresse: {CORE_URL}")

# Spotify-Einstellungen
SPOTIFY_CLIENT_ID     = cfg.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = cfg.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI  = cfg.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
SPOTIFY_PLAYLIST_ID   = cfg.get("SPOTIFY_PLAYLIST_ID", "")
SPOTIFY_CACHE_PATH    = os.path.join(BASE_DIR, ".spotify_cache")

SPOTIFY_OK = (
    SPOTIFY_CLIENT_ID not in ("", "HIER_CLIENT_ID_EINTRAGEN") and
    SPOTIFY_CLIENT_SECRET not in ("", "HIER_CLIENT_SECRET_EINTRAGEN")
)


# ══════════════════════════════════════════════════════════════════
# KONFIGURATION
# ══════════════════════════════════════════════════════════════════

WAKE_WORD_MODEL = os.path.join(BASE_DIR, "wakeword.onnx")

# Wake-Word Empfindlichkeit
WAKE_THRESHOLD    = 0.5   # 0.3 = empfindlicher, 0.7 = strenger
WAKE_VOTES_NEEDED = 1     # Wie oft erkannt bevor er reagiert

# Aufnahme
LISTEN_TIMEOUT  = 4    # Sekunden warten auf ersten Ton
PAUSE_THRESHOLD = 1.5  # Sekunden Stille = Satz zu Ende

# Sound-Verzeichnisse (im gleichen Ordner wie dieses Script)
SOUNDS_BASE  = os.path.join(BASE_DIR, "sounds")
BOOT_DIR     = os.path.join(SOUNDS_BASE, "boot")
DENKEN_DIR   = os.path.join(SOUNDS_BASE, "denken")
HEYBMO_DIR   = os.path.join(SOUNDS_BASE, "heybmo")
REPLY_DIR    = os.path.join(SOUNDS_BASE, "reply")
SHUTDOWN_DIR = os.path.join(SOUNDS_BASE, "shutdown")

# Bilder-Verzeichnisse
FACES_BASE = os.path.join(BASE_DIR, "faces")
FACE_DIRS  = {
    "BOOT":   os.path.join(FACES_BASE, "boot"),
    "IDLE":   os.path.join(FACES_BASE, "idle"),
    "LISTEN": os.path.join(FACES_BASE, "hören"),
    "THINK":  os.path.join(FACES_BASE, "denken"),
    "SPEAK":  os.path.join(FACES_BASE, "reden")
}

# Wörter die Konversation beenden
ABBRUCH_WOERTER = [
    "ne", "nein", "nö", "pass", "danke", "reicht",
    "war alles", "das war alles", "nichts", "nichts mehr",
    "kein", "okay danke", "tschüss", "bye", "ciao"
]

CURRENT_STATE = "BOOT"


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
        print(f"[WARN] Spotify: {e}")
        return None

def _ensure_spotify_running(sp):
    import subprocess
    try:
        devices = sp.devices()
        if not devices['devices']:
            spotify_pfade = [
                os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "Spotify.exe"),
            ]
            for pfad in spotify_pfade:
                if os.path.exists(pfad):
                    subprocess.Popen([pfad], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    break
            else:
                subprocess.Popen(["explorer.exe", "spotify:"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(8):
                time.sleep(1)
                devices = sp.devices()
                if devices['devices']:
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
    except: return "Konnte nicht pausieren."

def local_spotify_resume():
    sp = get_spotify()
    if not sp: return "Spotify nicht konfiguriert."
    try: sp.start_playback(); return "Musik läuft weiter."
    except: return "Konnte nicht fortsetzen."

def local_spotify_next():
    sp = get_spotify()
    if not sp: return "Spotify nicht konfiguriert."
    try: sp.next_track(); return "Nächstes Lied!"
    except: return "Konnte nicht springen."

def local_spotify_playlist():
    sp = get_spotify()
    if not sp: return "Spotify nicht konfiguriert."
    if not SPOTIFY_PLAYLIST_ID or SPOTIFY_PLAYLIST_ID == "HIER_PLAYLIST_ID_EINTRAGEN":
        return "Keine Playlist-ID konfiguriert."
    try:
        devices = _ensure_spotify_running(sp)
        if not devices: return "Spotify startet gerade."
        sp.start_playback(device_id=devices[0]['id'],
                          context_uri=f"spotify:playlist:{SPOTIFY_PLAYLIST_ID}")
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


# ══════════════════════════════════════════════════════════════════
# LOKALER ACTION-HANDLER
# ══════════════════════════════════════════════════════════════════

def handle_local_action(action, action_params):
    """Führt eine Aktion lokal auf diesem PC aus."""
    import subprocess as sp_proc
    if action == "shutdown_pc":
        threading.Thread(target=lambda: (
            time.sleep(2),
            sp_proc.run(["shutdown", "/s", "/t", "0"])
        ), daemon=True).start()
        return "Tschüss! Ich fahre jetzt herunter."
    elif action == "spotify_play":
        return local_spotify_play(action_params.get("query", ""))
    elif action == "spotify_pause":
        return local_spotify_pause()
    elif action == "spotify_resume":
        return local_spotify_resume()
    elif action == "spotify_next":
        return local_spotify_next()
    elif action == "spotify_playlist":
        return local_spotify_playlist()
    elif action == "spotify_volume":
        return local_spotify_volume(action_params.get("level", 50))
    return None


# ══════════════════════════════════════════════════════════════════
# CORE-VERBINDUNG
# ══════════════════════════════════════════════════════════════════

def core_health():
    try:
        r = req.get(f"{CORE_URL}/ping", timeout=2)
        return r.status_code == 200
    except:
        return False

def core_process(text):
    """
    Sendet Text an Core (remote=True), führt Aktionen lokal aus,
    holt TTS vom Core.
    """
    try:
        r = req.post(f"{CORE_URL}/process",
                     json={"message": text, "remote": True}, timeout=60)
        d = r.json()
    except Exception as e:
        print(f"[FEHLER] Core nicht erreichbar: {e}")
        return "Ich kann den Core gerade nicht erreichen.", None, None

    response_text = d.get("response", "")
    action        = d.get("action")
    action_params = d.get("action_params", {})

    # Lokale Aktion ausführen
    local_result = handle_local_action(action, action_params)
    if local_result:
        response_text = local_result

    # TTS vom Core
    audio_b64 = None
    if response_text:
        try:
            rs = req.post(f"{CORE_URL}/speak", json={"text": response_text}, timeout=120)
            audio_b64 = rs.json().get("audio")
        except Exception as e:
            print(f"[WARN] TTS: {e}")

    return response_text, audio_b64, action

def core_transcribe(audio_data):
    try:
        wav_bytes = audio_data.get_wav_data(convert_rate=16000, convert_width=2)
        b64 = base64.b64encode(wav_bytes).decode('utf-8')
        r = req.post(f"{CORE_URL}/transcribe",
                     json={"audio": b64, "format": "wav", "remote": True}, timeout=120)
        return r.json().get("transcript", "")
    except Exception as e:
        print(f"[FEHLER] Transkription fehlgeschlagen: {e}")
        return ""


# ══════════════════════════════════════════════════════════════════
# HILFSFUNKTIONEN
# ══════════════════════════════════════════════════════════════════

def get_files(directory, extensions):
    if os.path.exists(directory):
        return [os.path.join(directory, f)
                for f in os.listdir(directory)
                if f.lower().endswith(extensions)]
    return []

def load_face_images():
    images = {}
    for state, path in FACE_DIRS.items():
        imgs = get_files(path, ('.png', '.jpg', '.jpeg'))
        images[state] = [pygame.image.load(i) for i in imgs] if imgs else []
    return images


# ══════════════════════════════════════════════════════════════════
# GRAFIK-THREAD (Pygame GUI)
# ══════════════════════════════════════════════════════════════════

def bmo_face_thread():
    global CURRENT_STATE
    pygame.init()
    screen = pygame.display.set_mode((800, 480))
    pygame.display.set_caption("BMO OS")

    face_dict   = load_face_images()
    clock       = pygame.time.Clock()
    last_state  = None
    current_img = None
    next_switch = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

        now = pygame.time.get_ticks()

        if CURRENT_STATE != last_state:
            available = face_dict.get(CURRENT_STATE, [])
            if available:
                current_img = random.choice(available)
            last_state  = CURRENT_STATE
            next_switch = now + 2000
        elif CURRENT_STATE == "THINK":
            if now > next_switch:
                available = face_dict.get("THINK", [])
                if available:
                    current_img = random.choice(available)
                next_switch = now + 1000
        elif CURRENT_STATE == "SPEAK":
            if now > next_switch:
                available = face_dict.get("SPEAK", [])
                if available:
                    current_img = random.choice(available)
                next_switch = now + 50

        screen.fill((43, 135, 115))
        if current_img:
            rect = current_img.get_rect(center=(400, 240))
            screen.blit(current_img, rect)

        pygame.display.flip()
        clock.tick(30)


# ══════════════════════════════════════════════════════════════════
# AUDIO-FUNKTIONEN
# ══════════════════════════════════════════════════════════════════

def play_random_sound(directory, wait=False):
    sounds = get_files(directory, ".wav")
    if not sounds:
        return
    pygame.mixer.music.stop()
    pygame.mixer.music.unload()
    wahl = random.choice(sounds)
    pygame.mixer.music.load(wahl)
    pygame.mixer.music.set_volume(0.3)
    pygame.mixer.music.play()
    if wait:
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

def speak_bmo(text, audio_b64=None):
    global CURRENT_STATE

    if not audio_b64:
        print(f"[BMO] {text}")
        CURRENT_STATE = "SPEAK"
        time.sleep(max(1.0, len(text) * 0.04))
        CURRENT_STATE = "IDLE"
        return

    try:
        wav_bytes = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(wav_bytes)
            tmp_path = f.name

        CURRENT_STATE = "SPEAK"
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        CURRENT_STATE = "IDLE"

        try:
            os.remove(tmp_path)
        except:
            pass

    except Exception as e:
        print(f"[WARN] Audio-Wiedergabe fehlgeschlagen: {e}")
        print(f"[BMO] {text}")
        CURRENT_STATE = "IDLE"


# ══════════════════════════════════════════════════════════════════
# HAUPTPROGRAMM
# ══════════════════════════════════════════════════════════════════

def main():
    global CURRENT_STATE

    print("=" * 50)
    print("  BMO Desktop - Freund-Version")
    print(f"  Core: {CORE_URL}")
    print("=" * 50)

    if not os.path.exists(WAKE_WORD_MODEL):
        print(f"❌ Wake-Word Modell nicht gefunden: {WAKE_WORD_MODEL}")
        print("   Die Datei 'wakeword.onnx' muss im gleichen Ordner liegen.")
        input("Drücke ENTER zum Beenden...")
        return

    print("Prüfe Verbindung zum Core...")
    if not core_health():
        print(f"❌ Core nicht erreichbar auf {CORE_URL}")
        print("   Bitte deinen Freund fragen ob bmo_core.py läuft.")
        print("   Warte 10 Sekunden und versuche es nochmal...")
        time.sleep(10)
        if not core_health():
            print("❌ Immer noch nicht erreichbar. Beende.")
            input("Drücke ENTER zum Beenden...")
            return
    print("Core verbunden!")

    threading.Thread(target=bmo_face_thread, daemon=True).start()

    print("Initialisiere Audio...")
    pygame.mixer.init()

    recognizer = sr.Recognizer()
    recognizer.pause_threshold       = PAUSE_THRESHOLD
    recognizer.non_speaking_duration = PAUSE_THRESHOLD

    oww_model = Model(wakeword_models=[WAKE_WORD_MODEL])

    CURRENT_STATE = "BOOT"
    play_random_sound(BOOT_DIR, wait=True)
    CURRENT_STATE = "IDLE"

    # ══════════════════════════════════════════════════════════════
    # HAUPTSCHLEIFE
    # ══════════════════════════════════════════════════════════════
    while True:

        # SCHRITT 1: STANDBY — Warte auf "Hey BMO"
        with sd.InputStream(samplerate=16000, channels=1, dtype='int16') as stream:
            print(f"\n[BEREIT] Warte auf 'Hey BMO'...")
            oww_model.reset()
            wake_detected = False
            vote_counter  = 0

            while not wake_detected:
                audio_chunk, _ = stream.read(1280)
                audio_chunk = np.frombuffer(audio_chunk, dtype=np.int16)
                oww_model.predict(audio_chunk)

                triggered = any(
                    oww_model.prediction_buffer[m][-1] > WAKE_THRESHOLD
                    for m in oww_model.prediction_buffer
                )

                if triggered:
                    vote_counter += 1
                    if vote_counter >= WAKE_VOTES_NEEDED:
                        wake_detected = True
                else:
                    vote_counter = 0

        # SCHRITT 2: AKTIV-MODUS
        conversation_active  = True
        is_first_interaction = True

        while conversation_active:
            CURRENT_STATE = "LISTEN"

            if is_first_interaction:
                play_random_sound(HEYBMO_DIR)
                is_first_interaction = False

            with sr.Microphone() as source:
                try:
                    print(f"Höre zu...")
                    audio_input = recognizer.listen(source, timeout=LISTEN_TIMEOUT)
                except (sr.WaitTimeoutError, sr.UnknownValueError):
                    print("Kein Input → Standby...")
                    conversation_active = False
                    continue
                except Exception as e:
                    print(f"Aufnahme-Fehler: {e}")
                    conversation_active = False
                    continue

            CURRENT_STATE = "THINK"
            play_random_sound(DENKEN_DIR)

            user_text = core_transcribe(audio_input)
            print(f"Du: {user_text}")

            if not user_text:
                CURRENT_STATE = "LISTEN"
                continue

            response_text, audio_b64, action = core_process(user_text)
            print(f"BMO: {response_text}")
            speak_bmo(response_text, audio_b64)

            if action in ("spotify_play", "spotify_pause", "spotify_resume", "spotify_next"):
                conversation_active = False
                CURRENT_STATE = "IDLE"
                continue

            if action == "shutdown_pc":
                play_random_sound(SHUTDOWN_DIR, wait=True)
                conversation_active = False
                CURRENT_STATE = "IDLE"
                break

            CURRENT_STATE = "LISTEN"
            play_random_sound(REPLY_DIR, wait=True)

            try:
                with sr.Microphone() as followup_source:
                    print("Warte auf Followup...")
                    followup_audio = recognizer.listen(
                        followup_source, timeout=5, phrase_time_limit=4)
                    followup_text = core_transcribe(followup_audio).lower()
                    print(f"Followup: {followup_text}")

                    if any(wort in followup_text for wort in ABBRUCH_WOERTER):
                        conversation_active = False
                    else:
                        CURRENT_STATE = "THINK"
                        play_random_sound(DENKEN_DIR)
                        response_text2, audio_b64_2, action2 = core_process(followup_text)
                        print(f"BMO: {response_text2}")
                        speak_bmo(response_text2, audio_b64_2)

                        if action2 == "shutdown_pc":
                            play_random_sound(SHUTDOWN_DIR, wait=True)
                            conversation_active = False

            except (sr.WaitTimeoutError, sr.UnknownValueError):
                conversation_active = False

            CURRENT_STATE = "IDLE"

        CURRENT_STATE = "IDLE"
        print("[FERTIG] Zurück im Standby.")


if __name__ == "__main__":
    main()
