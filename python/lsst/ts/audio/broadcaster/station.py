import asyncio
import pyaudio
import socket
import wave
import tornado

from pydub import AudioSegment


__all__ = ['Station']

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 4096
BUFFER_DURATION = 5  # Adjust this value as needed

class Station:
    """
    A class that represents a station that can connect to a microphone,
    record audio and stream it!
    """
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.pyaudio = pyaudio.PyAudio()
        self.buffer = []
        self.current_pos = None
    
    def connect(self, host, port):
        print("Connecting to the server...", flush=True)
        self.sock.connect((host, port))
    
    def add_frame_to_buffer(self, frame):
        self.buffer.append(frame)
        self.current_pos = len(self.buffer) - 1
    
    async def start_fill_buffer(self):
        print("Filling buffer...", flush=True)
        audio_buffer = b''  # Initialize an empty byte buffer
        try:
            while True:
                await asyncio.sleep(0.00001)
                data = self.sock.recv(CHUNK)  # Receive audio data
                if data == b'':
                    raise RuntimeError("socket connection broken")
                audio_buffer += data

                # Check if the buffer is filled with enough data for playback
                if len(audio_buffer) >= int(RATE * BUFFER_DURATION):
                    frame = audio_buffer[:CHUNK]
                    self.add_frame_to_buffer(frame) # Play the first chunk of buffered data
                    audio_buffer = audio_buffer[CHUNK:] # Remove the played data from the buffer
        except Exception as e:
            print(e, flush=True)

    async def transform_and_transmit(self, buffer):
        print("Transforming and transmitting...", flush=True)
        wave_file_name = 'test_audio.wav'
        with wave.open(wave_file_name, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            # wf.setsampwidth(self.pyaudio.get_sample_size(FORMAT))
            wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
            wf.setframerate(RATE)

            for frame in buffer:
                wf.writeframes(frame)
        
        exported_file = 'output.mp3'
        audio_segment = AudioSegment.from_file(wave_file_name)
        audio_segment.export(exported_file, format="mp3")

        with open(exported_file, 'rb') as f:
            data = f.read(CHUNK)
            while data:
                yield data
                data = f.read(CHUNK)
    
    def clean(self):
        print('Shutting down')
        self.sock.close()
        self.pyaudio.terminate()


station = Station()

class AudioHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.is_client_connected = True
        self.from_pos = None

    async def get(self):
        self.from_pos = len(station.buffer) - 1 if len(station.buffer) > 0 else 0
        self.set_header('Content-Type', 'audio/mpeg')
        try:
            while self.is_client_connected:
                client_buffer = station.buffer[self.from_pos:]
                if (len(client_buffer) <= 50):
                    print("Waiting for buffer to fill...", flush=True)
                    await asyncio.sleep(1)
                    continue
                async for frame in station.transform_and_transmit(client_buffer):
                    self.write(frame)
                self.flush()
                self.from_pos = len(station.buffer) - 1
        except Exception as e:
            print(e, flush=True)
    
    def on_connection_close(self):
        print("Connection closed!", flush=True)
        self.is_client_connected = False

    def on_finish(self):
        print("Finished!", flush=True)

def make_app():
    return tornado.web.Application([
        (r'/audio_feed', AudioHandler),
    ])

async def check_buffer_len():
    while True:
        print("Buffer len:", flush=True)
        print(len(station.buffer), flush=True)
        await asyncio.sleep(1)

async def main():
    app = make_app()
    app.listen(8888)
    station.connect('192.168.1.167', 4444)
    asyncio.create_task(check_buffer_len())
    asyncio.create_task(station.start_fill_buffer())
    await asyncio.Event().wait()


if __name__ == '__main__':
    asyncio.run(main())
