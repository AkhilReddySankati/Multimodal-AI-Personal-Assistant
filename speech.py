import speech_recognition as sr
import pyttsx3


# ============================================================
# SPEECH RECOGNITION
# ============================================================

recognizer = sr.Recognizer()


# ============================================================
# TEXT TO SPEECH
# ============================================================

engine = pyttsx3.init()


# ============================================================
# SPEECH → TEXT
# ============================================================

def speech_to_text():
    """
    Listen through the microphone and convert speech to text.

    Returns:
        str: recognized text
        "" : if speech was not recognized
    """

    try:

        with sr.Microphone() as source:

            print("\n🎤 Listening...")

            # Adjust microphone for background noise
            recognizer.adjust_for_ambient_noise(
                source,
                duration=1
            )

            try:

                audio = recognizer.listen(
                    source,
                    timeout=5,
                    phrase_time_limit=15
                )

            except sr.WaitTimeoutError:

                print("⏱️ No speech detected.")

                return ""

        # ----------------------------------------------------
        # Convert speech to text
        # ----------------------------------------------------

        try:

            text = recognizer.recognize_google(
                audio
            )

            print(
                f"\n👤 You said: {text}"
            )

            return text

        except sr.UnknownValueError:

            print(
                "❌ Could not understand the audio."
            )

            return ""

        except sr.RequestError as error:

            print(
                f"❌ Speech recognition service error: {error}"
            )

            return ""

    except Exception as error:

        print(
            f"❌ Speech recognition error: {error}"
        )

        return ""


# ============================================================
# ALIAS
# ============================================================
# Keep compatibility with older code that uses listen()

def listen():
    return speech_to_text()


# ============================================================
# TEXT → SPEECH
# ============================================================

def speak(text):
    """
    Convert text response into spoken audio.
    """

    if not text:
        return

    print(
        f"\n🤖 AI: {text}"
    )

    try:

        engine.say(
            text
        )

        engine.runAndWait()

    except Exception as error:

        print(
            f"❌ Text-to-speech error: {error}"
        )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("🎤 SPEECH MODULE TEST")
    print("=" * 60)

    text = speech_to_text()

    if text:

        print(
            f"\nRecognized text: {text}"
        )

        speak(
            f"You said {text}"
        )

    else:

        print(
            "\nNo speech was recognized."
        )