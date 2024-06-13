import pyaudio
import psycopg2
import speech_recognition as sr
import ollama
from os import getenv
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class VoiceAssistant:
    def __init__(self, model_name='llama3', db_params=None, wake_word='hey llama'):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.model_name = model_name
        self.wake_word = wake_word

        # Adjust for ambient noise once during initialization
        with self.microphone as source:
            print("Adjusting for ambient noise... Please wait.")
            self.recognizer.adjust_for_ambient_noise(source)
            print("Ambient noise adjustment complete.")

        # Set up database connection
        if db_params:
            self.conn = psycopg2.connect(**db_params)
            self.cursor = self.conn.cursor()
        else:
            self.conn = None
            self.cursor = None

    def setup(self):
        with self.microphone as source:
            print("Recording... Speak now.")
            audio = self.recognizer.listen(source)
            print("Recording complete. Recognizing...")

        return audio

    def transcribe_audio(self, audio):
        try:
            transcription = self.recognizer.recognize_google(audio)
            return transcription
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand the audio")
            return None
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
            return None

    def chat_with_model(self, message):
        past_conversations = self.retrieve_past_conversations()
        messages = [{'role': 'user', 'content': conv[0]} for conv in past_conversations]
        messages.append({'role': 'user', 'content': (message + "If you hear hey llama, that is your wake word just ignore it. You are an AI Assistant and you don't have to respond to it. You are here to help me. You are an AI Assistant for the elderly. Please respond like you are talking to a human being.")})
        
        stream = ollama.chat(
            model=self.model_name,
            messages=messages,
            stream=True,
        )

        response = ""
        for chunk in stream:
            response += chunk['message']['content']
            print(chunk['message']['content'], end='', flush=True)
        return response

    def store_conversation(self, user_message, assistant_response):
        if self.conn and self.cursor:
            self.cursor.execute(
                "INSERT INTO conversations (user_message, assistant_response) VALUES (%s, %s)",
                (user_message, assistant_response)
            )
            self.conn.commit()
        else:
            print("Database connection is not available. Conversation not stored.")

    def retrieve_past_conversations(self):
        if self.conn and self.cursor:
            self.cursor.execute("SELECT user_message, assistant_response FROM conversations ORDER BY timestamp DESC LIMIT 10")
            return self.cursor.fetchall()
        else:
            print("Database connection is not available. Cannot retrieve past conversations.")
            return []

    def start(self):
        print("Starting voice assistant. Say 'stop' to end.")
        while True:
            audio = self.setup()
            transcription = self.transcribe_audio(audio)
            if transcription:
                print(f"You said: {transcription}")
                if transcription.lower() == "stop":
                    print("Stopping voice assistant.")
                    break
            try:
                if self.wake_word in transcription:
                    response = self.chat_with_model(transcription)
                    self.store_conversation(transcription, response)
            except:
                print("I am sorry, I did not understand you. Can you please repeat that?")

    def close(self):
        if self.conn:
            self.cursor.close()
            self.conn.close()

if __name__ == "__main__":
    db_params = {
        'dbname': getenv('PGDATABASE'),
        'user': getenv('PGUSER'),
        'password': getenv('PGPASSWORD'),
        'host': getenv('PGHOST'),
        'port': getenv('PGPORT', 5432),
    }
    assistant = VoiceAssistant(db_params=db_params)
    try:
        assistant.start()
    finally:
        assistant.close()
