import azure.cognitiveservices.speech as speechsdk
from config import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, TTS_VOICE

# Initialize the speech config
speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
speech_config.speech_recognition_language = "en-US"

# Real-time Speech-to-Text (STT) streaming
def stream_stt(audio_stream_callback):
    """
    Streams audio from a callback and yields recognized text in real-time.
    audio_stream_callback: function that yields audio chunks (bytes)
    """
    audio_format = speechsdk.audio.AudioStreamFormat(samples_per_second=16000, bits_per_sample=16, channels=1)
    pull_stream = speechsdk.audio.PullAudioInputStream(stream_reader=audio_stream_callback, audio_stream_format=audio_format)
    audio_input = speechsdk.AudioConfig(stream=pull_stream)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_input)
    
    done = False
    def stop_cb(evt):
        nonlocal done
        done = True
    recognizer.recognized.connect(lambda evt: print(f"RECOGNIZED: {evt.result.text}"))
    recognizer.session_stopped.connect(stop_cb)
    recognizer.canceled.connect(stop_cb)
    recognizer.start_continuous_recognition()
    while not done:
        # This is a placeholder; in production, yield recognized text as it arrives
        pass
    recognizer.stop_continuous_recognition()

# Real-time Text-to-Speech (TTS) streaming
def stream_tts(text, audio_stream_callback):
    """
    Synthesizes text to speech and streams audio chunks to a callback.
    text: string to synthesize
    audio_stream_callback: function to send audio chunks (bytes)
    """
    speech_synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=speechsdk.audio.AudioOutputConfig(use_default_speaker=False)
    )
    ssml = f"""
    <speak version='1.0' xml:lang='en-US'>
        <voice name='{TTS_VOICE}'>{text}</voice>
    </speak>
    """
    result = speech_synthesizer.speak_ssml_async(ssml).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        audio_stream_callback(result.audio_data)
    else:
        print(f"TTS failed: {result.reason}") 