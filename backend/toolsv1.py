# backend/tools.py
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from deepgram import Deepgram
from elevenlabs import ElevenLabs
import os
from dotenv import load_dotenv

load_dotenv(override=True)

twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-3.5-turbo")
deepgram_client = Deepgram(os.getenv("DEEPGRAM_API_KEY"))
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

@tool
def input_query_tool(query: str) -> str:
    """Capture the user's input query."""
    return query

@tool
def llm_tool(prompt: str) -> str:
    """Generate text using an LLM based on a prompt."""
    return llm.invoke(prompt).content

@tool
def output_report_tool(data: str) -> str:
    """Format the final output as a report."""
    return f"Final Report:\n\n:data"

@tool
def twilio_call_tool(phone_number: str, message: str) -> str:
    """Initiate a phone call with Twilio and connect to WebSocket."""
    twiml = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"wss://{os.getenv('SERVER_HOST', 'localhost:5000')}/connection")
    twiml.append(connect)
    call = twilio_client.calls.create(
        to=phone_number,
        from_=os.getenv("TWILIO_PHONE_NUMBER"),
        twiml=str(twiml)
    )
    return f"Call initiated with SID: {call.sid}"

@tool
def deepgram_stt_tool(audio_url: str) -> str:
    """Convert audio from a URL to text using Deepgram."""
    response = deepgram_client.transcription.sync_prerecorded(
        {"url": audio_url}, {"model": "nova-2", "language": "en"}
    )
    return response["results"]["channels"][0]["alternatives"][0]["transcript"]

@tool
def rag_tool(query: str, context: str) -> str:
    """Retrieve-Augmented Generation using a provided context and query."""
    prompt = f"Given the context: {context}\nAnswer the query: {query}"
    return llm.invoke(prompt).content

@tool
def elevenlabs_tts_tool(text: str) -> str:
    """Convert text to speech using ElevenLabs and return audio URL."""
    audio = elevenlabs_client.generate(
        text=text,
        voice="Rachel",
        model="eleven_monolingual_v1"
    )
    # Placeholder: Save audio and return URL (implement storage logic)
    return "http://example.com/generated_audio.mp3"

@tool
def response_summary_tool(data: str) -> str:
    """Generate a summary of the provided data."""
    prompt = f"Summarize the following data:\n{data}"
    return llm.invoke(prompt).content

available_tools = {
    "input_query_tool": input_query_tool,
    "llm_tool": llm_tool,
    "output_report_tool": output_report_tool,
    "twilio_call_tool": twilio_call_tool,
    "deepgram_stt_tool": deepgram_stt_tool,
    "rag_tool": rag_tool,
    "elevenlabs_tts_tool": elevenlabs_tts_tool,
    "response_summary_tool": response_summary_tool
}