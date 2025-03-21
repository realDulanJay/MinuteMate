#!/usr/bin/env python

from pydantic import BaseModel
from crewai.flow.flow import Flow, listen, start
from groq import Groq
from pydub import AudioSegment
from pydub.utils import make_chunks
from pathlib import Path

from crews.meeting_minutes_crew.meeting_minutes_crew import MeetingMinutesCrew
from crews.gmail_crew.gmail_crew import GmailCrew

import agentops
import os
from dotenv import load_dotenv

load_dotenv()

client = Groq()

class MeetingMinutesState(BaseModel):
    transcript: str = ""
    meeting_minutes: str = ""


class MeetingMinutesFlow(Flow[MeetingMinutesState]):

    @start()
    def transcribe_meeting(self):
        print("Generating Transcription")

        SCRIPT_DIR = Path(__file__).parent
        audio_path = str(SCRIPT_DIR / "EarningsCall.wav")
        
        # Load the audio file
        audio = AudioSegment.from_file(audio_path, format="wav")
        
        # Define chunk length in milliseconds 
        chunk_length_ms = 60000
        chunks = make_chunks(audio, chunk_length_ms)

        # Transcribe each chunk
        full_transcription = ""
        for i, chunk in enumerate(chunks):
            print(f"Transcribing chunk {i+1}/{len(chunks)}")
            chunk_path = f"chunk_{i}.wav"
            chunk.export(chunk_path, format="wav")
            
            with open(chunk_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-large-v3-turbo", 
                    file=audio_file
                )
                full_transcription += transcription.text + " "

        self.state.transcript = full_transcription
        print(f"Transcription: {self.state.transcript}")

    @listen(transcribe_meeting)
    def generate_meeting_minutes(self):
        print("Generating Meeting Minutes")

        crew = MeetingMinutesCrew()

        inputs = {
            "transcript": self.state.transcript
        }
        meeting_minutes = crew.crew().kickoff(inputs)
        self.state.meeting_minutes = meeting_minutes

    @listen(generate_meeting_minutes)
    def create_draft_meeting_minutes(self):
        print("Creating Draft Meeting Minutes")

        crew = GmailCrew()

        inputs = {
            "body": str(self.state.meeting_minutes)
        }

        draft_crew = crew.crew().kickoff(inputs)
        print(f"Draft Crew: {draft_crew}")

def kickoff():
    agentops.init(api_key=os.getenv("AGENTOPS_API_KEY"), auto_start_session=False)
    agentops.start_session()
    meeting_minutes_flow = MeetingMinutesFlow()
    meeting_minutes_flow.plot()
    meeting_minutes_flow.kickoff()

    agentops.end_session()

if __name__ == "__main__":
    kickoff()
