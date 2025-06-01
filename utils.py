import json
import random
import datetime
import os

try:
    import speech_recognition as sr
    import pyttsx3
except ImportError:
    sr = None
    pyttsx3 = None

LANGUAGES = {
    "English": "en",
    "Urdu": "ur"
}

def load_health_data(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data, None
    except Exception as e:
        return None, f"Error loading health data: {e}"

def get_tags(data):
    return [entry["tag"] for entry in data]

def get_patterns_for_tag(data, tag):
    for entry in data:
        if entry["tag"] == tag:
            return entry.get("patterns", [])
    return []

def get_tips_for_tag(data, tag):
    for entry in data:
        if entry["tag"] == tag:
            return entry.get("tips", [])
    return []

def get_severity_levels(data, tag):
    for entry in data:
        if entry["tag"] == tag:
            return list(entry.get("severity", {}).keys())
    return []

def get_severity_advice(data, tag, level):
    for entry in data:
        if entry["tag"] == tag:
            return entry.get("severity", {}).get(level, "")
    return ""

def validate_input(tag, user_input):
    if not tag:
        return False, "Please select a tag."
    if not user_input or not user_input.strip():
        return False, "Please enter or select a pattern."
    return True, ""

def log_symptom(symptom_log, tag, pattern, severity, profile):
    entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tag": tag,
        "pattern": pattern,
        "severity": severity,
        "profile": profile.copy()
    }
    symptom_log.append(entry)

def export_conversation(history, filepath):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            for sender, message in history:
                f.write(f"{sender}: {message}\n")
        return True, None
    except Exception as e:
        return False, str(e)

def speak_text(text, lang="en"):
    if pyttsx3 is None:
        return
    engine = pyttsx3.init()
    engine.setProperty('rate', 160)
    engine.say(text)
    engine.runAndWait()

def recognize_speech(lang="en"):
    if sr is None:
        return ""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        audio = recognizer.listen(source, timeout=5)
    try:
        return recognizer.recognize_google(audio, language=lang)
    except Exception:
        return ""
