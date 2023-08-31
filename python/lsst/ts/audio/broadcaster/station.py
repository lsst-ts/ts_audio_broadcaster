__all__ = ["Station"]

import asyncio
import logging
import socket
import wave
from typing import Optional

import pyaudio
from pydub import AudioSegment

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 4096
BUFFER_DURATION = 5  # Adjust this value as needed


class Station:
    """
    A class that represents a station that can connect to a microphone,
    record audio and stream it!

    Parameters
    ----------
    log : logging.Logger
        Logger to use for logging
    """

    def __init__(self, host, port, log):
        self.host: str = host
        self.port: int = port
        self.log: logging.Logger = log.getChild(type(self).__name__)
        self.sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.buffer: list = []
        self.current_pos: Optional[int] = None
        self._connected_mic: bool = False
        self.buffer_fill_interval: float = 0.00001
        self.max_buffer_len: int = 1000
        self.max_reconnection_attempts: int = 5

    def connect(self):
        """Connect to the microphone server with a socket connection.

        Parameters
        ----------
        host : str
            IP of the microphone server, e.g. '10.10.1.1'
        port : int
            Port of the microphone server, e.g. 4444

        Raises
        ------
        RuntimeError
            If host or port are empty
            If the socket connection is already established
            If the socket connection fails
        """
        self.sock.connect((self.host, self.port))
        self._connected_mic = True
        self.log.info(f"Connected to microphone at {self.host}:{self.port}")

    def add_frame_to_buffer(self, frame):
        self.buffer.append(frame)
        self.current_pos = len(self.buffer) - 1

    def set_emtpy_buffer(self):
        self.buffer = []
        self.current_pos = None

    def assert_microphone_connected(self):
        if not self._connected_mic:
            raise RuntimeError("Microphone not connected!")

    async def start_fill_buffer(self):
        """Start filling the buffer with audio data from the microphone server.

        This method will run forever until the socket connection is broken.
        When this happens the method will try to reconnect to the
        microphone server `self.max_reconnection_attempts` times.

        Notes
        -----
        This method will add an audio frame to the buffer every time the
        internal buffer is filled with enough data for playback.

        If the station buffer reaches `self.max_buffer_len` frames,
        it will be emptied.

        Raises
        ------
        RuntimeError
            If the microphone is not connected
            If the socket connection is broken
        """
        self.log.info("Filling buffer...")
        reconnection_attemps = 0
        audio_buffer = b""
        while True:
            try:
                self.assert_microphone_connected()
                self.max_reconnection_attempts = 5
                if len(self.buffer) >= self.max_buffer_len:
                    self.set_emtpy_buffer()

                await asyncio.sleep(self.buffer_fill_interval)
                data = self.sock.recv(CHUNK)
                if data == b"":
                    raise RuntimeError("Socket connection broken")
                audio_buffer += data

                if len(audio_buffer) >= int(RATE * BUFFER_DURATION):
                    frame = audio_buffer[:CHUNK]
                    self.add_frame_to_buffer(frame)
                    audio_buffer = audio_buffer[CHUNK:]
            except Exception as e:
                self.log.warning(f"{e}, retrying connection...")
                await asyncio.sleep(1)
                reconnection_attemps += 1
                if reconnection_attemps <= self.max_reconnection_attempts:
                    try:
                        self.connect()
                        self.set_emtpy_buffer()
                        continue
                    except Exception:
                        continue
                break
        self.log.info("Stopped filling buffer.")

    async def transform_and_transmit(self, buffer: list):
        """Create a wave file from the buffer and transmit it to the client
        through mp3 bytes chunks.

        Parameters
        ----------
        buffer : list
            List of audio frames to transmit

        Yields
        ------
        data : bytes
            Bytes of the mp3 file
        """
        self.log.debug("Transforming and transmitting...")
        wave_file_name = "output.wav"
        with wave.open(wave_file_name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
            wf.setframerate(RATE)

            for frame in buffer:
                wf.writeframes(frame)

        exported_file = "output.mp3"
        audio_segment = AudioSegment.from_file(wave_file_name)
        audio_segment.export(exported_file, format="mp3")

        with open(exported_file, "rb") as f:
            data = f.read(CHUNK)
            while data:
                yield data
                data = f.read(CHUNK)

    def clean(self):
        self.log.info("Cleaning up...")
        self.sock.close()
