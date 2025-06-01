import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import google.generativeai as genai
import os
from dotenv import load_dotenv
from utils import (
    load_health_data, get_tags, get_patterns_for_tag, get_tips_for_tag,
    get_severity_levels, get_severity_advice, validate_input, log_symptom,
    export_conversation, speak_text, LANGUAGES
)
import matplotlib.pyplot as plt
import threading
import speech_recognition as sr

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATA_PATH = "health_data.json"
DISCLAIMER = "\n\nThis is general advice. Consult a doctor."
DEFAULT_LANG = "English"

def get_gemini_response(messages, lang="en"):
    """
    messages: list of dicts, e.g. [{"role": "user", "parts": [{"text": "Hello"}]}, ...]
    Returns: response text from Gemini
    """
    if not GEMINI_API_KEY:
        return "Gemini API key not set. Please set GEMINI_API_KEY environment variable."
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        formatted_messages = []
        for msg in messages:
            role = "user" if msg["role"] in ["user", "system"] else "model"
            formatted_messages.append({"role": role, "parts": msg["parts"]})
        
        chat = model.start_chat(history=formatted_messages[:-1])
        last_message = formatted_messages[-1]["parts"][0]["text"] if formatted_messages else ""
        response = chat.send_message(last_message)
        return response.text
    except Exception as e:
        return f"Error contacting Gemini API: {e}"

def recognize_speech(lang="en"):
    """
    Recognize speech from the microphone and convert it to text.
    lang: Language code (e.g., "en" for English).
    Returns: Recognized text or None if recognition fails.
    """
    # Map simple language codes to Google Speech Recognition format
    lang_map = {
        "en": "en-US",
        "es": "es-ES",
        "fr": "fr-FR",
        # Add more mappings as needed based on LANGUAGES dictionary
    }
    lang_code = lang_map.get(lang, "en-US")  # Default to "en-US" if lang not found

    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    try:
        with mic as source:
            # Adjust for ambient noise
            recognizer.adjust_for_ambient_noise(source, duration=1)
            # Listen for audio
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            # Recognize speech using Google Speech Recognition
            text = recognizer.recognize_google(audio, language=lang_code)
            return text
    except sr.UnknownValueError:
        return None  # Speech was unintelligible
    except sr.RequestError as e:
        raise Exception(f"Speech recognition service error: {e}")
    except sr.WaitTimeoutError:
        return None  # No speech detected within timeout
    except Exception as e:
        raise Exception(f"Microphone error: {e}")

class HealthBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("HealthBot - Your Medical Assistant")
        self.root.geometry("850x700")
        self.root.configure(bg="#e0f7fa")

        # Data
        self.data, self.data_error = load_health_data(DATA_PATH)
        self.selected_tag = tk.StringVar()
        self.selected_pattern = tk.StringVar()
        self.selected_severity = tk.StringVar()
        self.user_input = tk.StringVar()
        self.language = tk.StringVar(value=DEFAULT_LANG)
        self.symptom_log = []
        self.conversation_history = []
        self.profile = {"Age": "", "Gender": ""}

        # Conversation history for Gemini
        self.gemini_history = [
            {"role": "user", "parts": [{"text": "You are HealthBot, a helpful medical assistant. Give general advice, but always recommend consulting a doctor for serious issues."}]}
        ]

        # Audio playback control
        self.is_reading = False
        self.audio_thread = None

        # Title
        title = tk.Label(root, text="HealthBot - Your Medical Assistant", font=("Segoe UI", 22, "bold"),
                         bg="#008080", fg="white", pady=12)
        title.pack(fill=tk.X)

        # Profile panel
        profile_frame = tk.LabelFrame(root, text="User Profile", bg="#e0f7fa", fg="#008080", font=("Segoe UI", 11, "bold"))
        profile_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(profile_frame, text="Age:", bg="#e0f7fa", font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(10,2))
        self.age_entry = tk.Entry(profile_frame, width=5, font=("Segoe UI", 11))
        self.age_entry.pack(side=tk.LEFT)
        tk.Label(profile_frame, text="Gender:", bg="#e0f7fa", font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(10,2))
        self.gender_combo = ttk.Combobox(profile_frame, values=["Male", "Female", "Other"], width=8, font=("Segoe UI", 11))
        self.gender_combo.pack(side=tk.LEFT)
        tk.Label(profile_frame, text="Language:", bg="#e0f7fa", font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(10,2))
        self.lang_combo = ttk.Combobox(profile_frame, values=list(LANGUAGES.keys()), textvariable=self.language, width=10, font=("Segoe UI", 11))
        self.lang_combo.pack(side=tk.LEFT)

        # Conversation history
        self.chat_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Segoe UI", 12),
                                                   bg="#f5f5f5", fg="#263238", height=15, state='disabled')
        self.chat_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.chat_area.tag_configure("user", background="#d1e7dd", foreground="#1b4332", justify="right", lmargin1=100, lmargin2=100, rmargin=10)
        self.chat_area.tag_configure("bot", background="#fff3cd", foreground="#7c4700", justify="left", lmargin1=10, lmargin2=10, rmargin=100)
        self.chat_area.tag_configure("system", background="#e0e0e0", foreground="#263238", justify="center")

        # Tag buttons
        tag_frame = tk.Frame(root, bg="#e0f7fa")
        tag_frame.pack(pady=(0, 5))
        self.tag_buttons = []
        if self.data:
            for entry in self.data:
                btn = tk.Button(tag_frame, text=entry["tag"].capitalize(),
                                command=lambda t=entry["tag"]: self.on_tag_selected(t),
                                bg="#4dd0e1", fg="#004d40", font=("Segoe UI", 11, "bold"), width=13)
                btn.pack(side=tk.LEFT, padx=4, pady=4)
                self.tag_buttons.append(btn)
        else:
            tk.Label(tag_frame, text=self.data_error or "No data found.", fg="red", bg="#e0f7fa").pack()

        # Patterns dropdown
        pattern_frame = tk.Frame(root, bg="#e0f7fa")
        pattern_frame.pack(pady=(0, 5))
        tk.Label(pattern_frame, text="Choose a pattern or type your question:", bg="#e0f7fa", font=("Segoe UI", 11)).pack(side=tk.LEFT)
        self.pattern_combo = ttk.Combobox(pattern_frame, textvariable=self.selected_pattern, width=40, font=("Segoe UI", 11))
        self.pattern_combo.pack(side=tk.LEFT, padx=8)
        self.pattern_combo.bind("<<ComboboxSelected>>", self.on_pattern_selected)

        # Severity dropdown
        severity_frame = tk.Frame(root, bg="#e0f7fa")
        severity_frame.pack(pady=(0, 5))
        tk.Label(severity_frame, text="Severity:", bg="#e0f7fa", font=("Segoe UI", 11)).pack(side=tk.LEFT)
        self.severity_combo = ttk.Combobox(severity_frame, textvariable=self.selected_severity, width=15, font=("Segoe UI", 11))
        self.severity_combo.pack(side=tk.LEFT, padx=8)
        self.severity_combo.bind("<<ComboboxSelected>>", self.on_severity_selected)

        # Tips panel
        tips_frame = tk.Frame(root, bg="#e0f7fa")
        tips_frame.pack(pady=(0, 5))
        tk.Label(tips_frame, text="Health Tips:", bg="#e0f7fa", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        self.tips_label = tk.Label(tips_frame, text="", bg="#e0f7fa", fg="#00695c", font=("Segoe UI", 11))
        self.tips_label.pack(side=tk.LEFT, padx=8)

        # User text entry
        self.entry = tk.Entry(root, textvariable=self.user_input, font=("Segoe UI", 12), bg="#ffffff", fg="#263238")
        self.entry.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.entry.bind("<Return>", lambda event: self.send_message())

        # Send, Audio, Reset, Export, Chart, Emergency buttons
        btn_frame = tk.Frame(root, bg="#e0f7fa")
        btn_frame.pack(pady=(0, 10))
        tk.Button(btn_frame, text="Send", command=self.send_message,
                  bg="#008080", fg="white", font=("Segoe UI", 12, "bold"), width=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="🎤 Speak", command=self.audio_input,
                  bg="#4dd0e1", fg="#004d40", font=("Segoe UI", 12, "bold"), width=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="🔊 Read", command=self.audio_output,
                  bg="#4dd0e1", fg="#004d40", font=("Segoe UI", 12, "bold"), width=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Reset", command=self.reset_conversation,
                  bg="#bdbdbd", fg="#263238", font=("Segoe UI", 10), width=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Export", command=self.export_history,
                  bg="#bdbdbd", fg="#263238", font=("Segoe UI", 10), width=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Chart", command=self.show_symptom_chart,
                  bg="#bdbdbd", fg="#263238", font=("Segoe UI", 10), width=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="🚨 Emergency", command=self.emergency_alert,
                  bg="#d32f2f", fg="white", font=("Segoe UI", 10, "bold"), width=12).pack(side=tk.LEFT, padx=4)

        # Welcome message
        self.display_message("HealthBot", "Hello! Please select a tag or type your health question.")

    def on_tag_selected(self, tag):
        self.selected_tag.set(tag)
        patterns = get_patterns_for_tag(self.data, tag)
        self.pattern_combo["values"] = patterns
        self.pattern_combo.set("")
        self.user_input.set("")
        self.selected_severity.set("")
        self.severity_combo["values"] = get_severity_levels(self.data, tag)
        tips = get_tips_for_tag(self.data, tag)
        self.tips_label.config(text=" | ".join(tips))
        self.display_message("HealthBot", f"Selected tag: {tag.capitalize()}. Now choose a pattern or type your question.")

    def on_pattern_selected(self, event):
        pattern = self.pattern_combo.get()
        self.user_input.set(pattern)

    def on_severity_selected(self, event):
        tag = self.selected_tag.get()
        level = self.selected_severity.get()
        advice = get_severity_advice(self.data, tag, level)
        if advice:
            self.display_message("HealthBot", f"Severity advice: {advice}")

    def send_message(self):
        tag = self.selected_tag.get()
        user_text = self.user_input.get() or self.selected_pattern.get()
        severity = self.selected_severity.get()
        self.profile["Age"] = self.age_entry.get()
        self.profile["Gender"] = self.gender_combo.get()
        valid, msg = validate_input(tag, user_text)
        if not valid:
            messagebox.showwarning("Input Error", msg)
            return
        self.display_message("You", user_text)
        user_profile = f"Age: {self.profile['Age']}, Gender: {self.profile['Gender']}, Language: {self.language.get()}"
        prompt = f"{user_text}\n\nUser Profile: {user_profile}"
        self.gemini_history.append({"role": "user", "parts": [{"text": prompt}]})
        response = get_gemini_response(self.gemini_history, lang=LANGUAGES.get(self.language.get(), "en"))
        self.gemini_history.append({"role": "model", "parts": [{"text": response}]})
        response_with_disclaimer = response + DISCLAIMER
        self.display_message("HealthBot", response_with_disclaimer)
        log_symptom(self.symptom_log, tag, user_text, severity, self.profile)
        self.conversation_history.append(("You", user_text))
        self.conversation_history.append(("HealthBot", response_with_disclaimer))
        self.user_input.set("")
        self.pattern_combo.set("")
        self.selected_severity.set("")

    def display_message(self, sender, message):
        self.chat_area.config(state='normal')
        message = message.strip()
        if sender == "You" or sender == "You (via Speech)":
            tag = "user"
            display_sender = "You"
            formatted = f"{display_sender}: {message}\n"
        elif sender == "HealthBot":
            tag = "bot"
            display_sender = "HealthBot"
            formatted = f"{display_sender}: {message}\n"
        else:
            tag = "system"
            formatted = f"{sender}: {message}\n"
        self.chat_area.insert(tk.END, formatted, tag)
        self.chat_area.insert(tk.END, "\n")
        self.chat_area.config(state='disabled')
        self.chat_area.see(tk.END)

    def reset_conversation(self):
        self.chat_area.config(state='normal')
        self.chat_area.delete(1.0, tk.END)
        self.chat_area.config(state='disabled')
        self.selected_tag.set("")
        self.selected_pattern.set("")
        self.selected_severity.set("")
        self.user_input.set("")
        self.pattern_combo.set("")
        self.severity_combo.set("")
        self.tips_label.config(text="")
        self.symptom_log.clear()
        self.conversation_history.clear()
        self.gemini_history = [
            {"role": "user", "parts": [{"text": "You are HealthBot, a helpful medical assistant. Give general advice, but always recommend consulting a doctor for serious issues."}]}
        ]
        self.display_message("HealthBot", "Conversation reset. Please select a tag or type your health question.")

    def export_history(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if file_path:
            success, err = export_conversation(self.conversation_history, file_path)
            if success:
                messagebox.showinfo("Export", "Conversation exported successfully!")
            else:
                messagebox.showerror("Export Error", err)

    def show_symptom_chart(self):
        if not self.symptom_log:
            messagebox.showinfo("No Data", "No symptoms logged yet.")
            return
        tags = [entry["tag"] for entry in self.symptom_log]
        tag_counts = {tag: tags.count(tag) for tag in set(tags)}
        plt.figure(figsize=(6,4))
        plt.bar(tag_counts.keys(), tag_counts.values(), color="#008080")
        plt.title("Symptom Tracking")
        plt.xlabel("Symptom Tag")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.show()

    def emergency_alert(self):
        messagebox.showerror("EMERGENCY", "If this is a medical emergency, call 1122 or your local emergency number immediately!")

    def audio_input(self):
        try:
            text = recognize_speech(lang=LANGUAGES.get(self.language.get(), "en"))
            if text:
                self.user_input.set(text)
                self.display_message("You (via Speech)", text)
            else:
                messagebox.showwarning("Audio Input", "Could not recognize speech. Please speak clearly or check your microphone.")
        except Exception as e:
            messagebox.showerror("Audio Input Error", str(e))

    def audio_output(self):
        try:
            if not self.is_reading:
                last_bot_msg = ""
                for sender, msg in reversed(self.conversation_history):
                    if sender == "HealthBot":
                        last_bot_msg = msg
                        break
                if last_bot_msg:
                    self.is_reading = True
                    self.audio_thread = threading.Thread(target=self._play_audio, args=(last_bot_msg,), daemon=True)
                    self.audio_thread.start()
                else:
                    messagebox.showinfo("Audio Output", "No bot message to read.")
            else:
                self.is_reading = False
                if hasattr(self, 'audio_engine') and self.audio_engine:
                    self.audio_engine.stop()
        except Exception as e:
            messagebox.showerror("Audio Output Error", str(e))

    def _play_audio(self, message):
        try:
            import pyttsx3
            self.audio_engine = pyttsx3.init()
            self.audio_engine.say(message)
            self.audio_engine.runAndWait()
            if self.is_reading:
                self.audio_engine.stop()
            self.is_reading = False
            self.audio_engine = None
        except Exception as e:
            self.is_reading = False
            self.root.after(0, lambda: messagebox.showerror("Audio Output Error", str(e)))

if __name__ == "__main__":
    root = tk.Tk()
    app = HealthBotGUI(root)
    root.mainloop()