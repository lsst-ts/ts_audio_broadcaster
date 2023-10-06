# This file is part of ts_audiobroadcaster.
#
# Developed for the Rubin Observatory Telescope and Site System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import asyncio
import logging
import socket
import time
import unittest
from unittest.mock import patch

from lsst.ts.audio.broadcaster import Station

CHUNK = 4096


class MockSocketServer:
    def __init__(self, with_fail=False):
        self.current_chunk = 0
        self.sent_fames = 0
        self.audio_frames = []
        self.with_fail = with_fail
        self.sent_frames_before_fail = 100
        with open("tests/data/audio_sample.wav", "rb") as f:
            audio_frame = f.read(CHUNK)
            while audio_frame:
                self.audio_frames.append(audio_frame)
                audio_frame = f.read(CHUNK)

    def connect(self, host_tuple):
        pass

    def close(self):
        pass

    def recv(self, CHUNK):
        audio_frame = self.audio_frames[self.current_chunk]
        time.sleep(0.01)

        if self.with_fail and self.sent_fames > self.sent_frames_before_fail:
            self.sent_fames = 0
            return b""

        if self.current_chunk < len(self.audio_frames) - 1:
            self.current_chunk += 1
        else:
            self.current_chunk = 0

        self.sent_fames += 1
        return audio_frame


class TestStation(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.log = logging.getLogger(__name__)

    def setUp(self) -> None:
        self.socket_patcher = patch("socket.socket")
        self.socket_mock = self.socket_patcher.start()
        self.socket_mock.return_value = MockSocketServer()
        self.station = Station("0.0.0.0", 9999, self.log)

    def tearDown(self) -> None:
        self.station.clean()
        self.socket_patcher.stop()

    def test_mock_socket_server(self):
        self.assertIs(socket.socket, self.socket_mock)

    def test_connect(self):
        """Test that the station can connect to the microphone server."""
        self.station.connect()
        self.station.assert_microphone_connected()

    async def test_start_fill_buffer_with_disconnect(self):
        """Test that the station can start filling the buffer with
        audio data from the microphone server.

        This method will run forever until the socket connection is broken.
        This will raise an exception that will be catched by the station.
        Then the station will try to reconnect to the microphone server.
        The station buffer should be emptied after the reconnection.
        """
        socket_patcher = patch("socket.socket")
        socket_mock = socket_patcher.start()
        socket_mock.return_value = MockSocketServer(with_fail=True)
        self.station = Station("0.0.0.0", 9999, self.log)

        self.station.connect()
        station_buffering_task = asyncio.create_task(self.station.start_fill_buffer())
        prev_buffer_len = 0
        while True:
            await asyncio.sleep(1)
            if len(self.station.buffer) < prev_buffer_len:
                self.station.assert_microphone_connected()
                break
            prev_buffer_len = len(self.station.buffer)

        prev_buffer_len = 0
        while True:
            await asyncio.sleep(1)
            if len(self.station.buffer) == 0:
                continue
            assert len(self.station.buffer) > prev_buffer_len
            break
        station_buffering_task.cancel()
        socket_patcher.stop()

    async def test_start_fill_buffer(self):
        """Test that the station can start filling the buffer with
        audio data from the microphone server.

        This method will run forever until the buffer has a len of 10.
        """
        self.station.connect()
        station_buffering_task = asyncio.create_task(self.station.start_fill_buffer())
        while True:
            if len(self.station.buffer) >= 10:
                break
            await asyncio.sleep(1)
        station_buffering_task.cancel()
        assert len(self.station.buffer) >= 10

    async def test_transform_and_transmit(self):
        """Test that the station can transform and transmit audio frames.

        This method will run forever until the client buffer has a len of 10.
        """
        self.station.connect()
        station_buffering_task = asyncio.create_task(self.station.start_fill_buffer())
        from_pos = 0
        while True:
            client_buffer = self.station.buffer[from_pos:]
            if len(client_buffer) <= 10:
                await asyncio.sleep(1)
                continue
            mp3_buffer = b""
            async for frame in self.station.transform_and_transmit(client_buffer):
                mp3_buffer += frame
            from_pos = len(self.station.buffer) - 1
            break
        station_buffering_task.cancel()

        assert len(mp3_buffer) > 0

    async def test_empty_buffer(self):
        """Test that the station can empty the buffer
        and continue filling it with audio data from the microphone server.
        """
        self.station.connect()
        current_buffer_len = 0
        station_buffering_task = asyncio.create_task(self.station.start_fill_buffer())
        await asyncio.sleep(1)
        while True:
            if len(self.station.buffer) > current_buffer_len:
                current_buffer_len = len(self.station.buffer)
            else:
                break
            await asyncio.sleep(1)

        assert current_buffer_len > len(self.station.buffer)
        current_buffer_len = len(self.station.buffer)
        await asyncio.sleep(1)
        assert len(self.station.buffer) > current_buffer_len
        station_buffering_task.cancel()

    # TODO: Add test to check if generated audio chunks are valid mp3 format
    # TODO: Add test to check the quality of the audio
