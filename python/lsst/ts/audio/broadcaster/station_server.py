# This file is part of LOVE-producer.
#
# Developed for Vera C. Rubin Observatory Telescope and Site Systems.
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

__all__ = ["AudioBroadcasterServer", "run_audio_broadcaster"]


import argparse
import asyncio
import logging
import os
import signal
from typing import Optional

import tornado

from .station import Station

logging.basicConfig(level=logging.DEBUG)


class AudioHandler(tornado.web.RequestHandler):
    """Tornado web handler to serve audio stream to clients.

    Clients that connects using the GET method will continuously
    receive audio data buffered from the microphone station.

    Parameters
    ----------
    station : Station
        Station to use to get audio stream
    log : logging.Logger
        Logger to use for logging
    """

    def initialize(self, station, log):
        self.station: Station = station
        self.log: logging.Logger = log.getChild(type(self).__name__)
        self.is_client_connected: bool = True
        self.from_pos: Optional[int] = None
        self.client_buffer_min_length: int = 50
        self.client_buffer_fill_interval: float = 1

    async def get(self):
        self.log.debug("New connection!")
        self.from_pos = (
            len(self.station.buffer) - 1 if len(self.station.buffer) > 0 else 0
        )
        self.set_header("Content-Type", "audio/mpeg")
        while self.is_client_connected:
            client_buffer = self.station.buffer[self.from_pos :]
            if len(client_buffer) < self.client_buffer_min_length:
                self.log.debug(
                    f"Waiting {self.client_buffer_fill_interval} sec for buffer to fill..."
                )
                await asyncio.sleep(self.client_buffer_fill_interval)
                continue
            async for frame in self.station.transform_and_transmit(client_buffer):
                self.write(frame)
            self.flush()
            self.from_pos = len(self.station.buffer) - 1

    def on_connection_close(self):
        self.log.debug("Connection closed!")
        self.is_client_connected = False


class AudioBroadcasterServer:
    """Container class to configure and host a microphone Station
    and provide a Tornado webserver to broadcast audio streams.

    Parameters
    ----------
    host : str
        IP of the microphone server, e.g. 10.10.1.1
    port : str
        Port of the microphone server, e.g. 8888
    log_level : int
        Logging level; INFO=20 (default), DEBUG=10
    """

    def __init__(self, host, port, log_level=logging.INFO) -> None:
        self.log: logging.Logger = logging.getLogger()

        if not self.log.hasHandlers():
            self.log.addHandler(logging.StreamHandler())

        self.host: str = host
        self.port: int = port
        self.log.setLevel(log_level)

        self.station: Station = Station(self.host, self.port, self.log)
        self._wait_forever_task: Optional[asyncio.Future] = None

    async def run_broadcaster(self):
        """Run the audio broadcaster server by creating a Tornado
        web server app.
        This method also connects to the microphone server
        and starts filling the buffer with audio data.
        This method will run forever until a signal is received.
        """

        def make_tornado_app():
            return tornado.web.Application(
                [
                    (
                        r"/audio_feed",
                        AudioHandler,
                        dict(station=self.station, log=self.log),
                    ),
                ]
            )

        app = make_tornado_app()
        app.listen(self.web_server_port)
        self.station.connect()

        start_task = asyncio.create_task(self.station.start_fill_buffer())

        loop = asyncio.get_running_loop()
        for signal_value in (
            signal.SIGTERM,
            signal.SIGINT,
            signal.SIGHUP,
        ):
            loop.add_signal_handler(signal_value, self.signal_handler)

        self._wait_forever_task = asyncio.Future()

        for task in asyncio.as_completed(
            [
                self._wait_forever_task,
                start_task,
            ]
        ):
            try:
                await task
            except Exception:
                self.log.exception("Error in execution task.")
            finally:
                break

        self.log.warning("Terminating...")

        await self.station.clean()

    def signal_handler(self):
        self.log.warning(f"AudioBroadcasterServer.signal_handler for pid={os.getpid()}")
        self._wait_forever_task.set_result(None)

    @classmethod
    async def amain(cls):
        """Parse command line arguments, create and run a
        `Station` and a Tornado web server.
        """
        parser = cls.make_argument_parser()
        args = parser.parse_args()

        logging.basicConfig(level=args.log_level)

        if args.server == "":
            raise RuntimeError(
                "At least one server must be provided. "
                "See `--help` for more information."
            )

        if args.port is None:
            raise RuntimeError(
                "At least one port must be provided. "
                "See `--help` for more information."
            )

        audio_broadcaster_set = cls(
            server=args.server,
            port=args.port,
            log_level=args.log_level,
        )

        await audio_broadcaster_set.run_broadcaster()

    @classmethod
    def make_argument_parser(cls):
        """Make command line arguments."""

        parser = argparse.ArgumentParser(
            description="Produce microphones audio stream to LOVE for one microphone server.",
        )

        parser.add_argument(
            "server",
            type=str,
            help="IP of the microphone server, e.g. '10.10.1.1'",
        )

        parser.add_argument(
            "port",
            type=int,
            help="Port of the microphone server, e.g. '8888'",
        )

        parser.add_argument(
            "--log-level",
            type=int,
            dest="log_level",
            default=logging.INFO,
            help="Logging level; INFO=20 (default), DEBUG=10",
        )

        return parser

    @property
    def web_server_port(self):
        return int(os.environ.get("WEBSERVER_PORT", "8888"))


def run_audio_broadcaster():
    """Run audio broadcaster server."""
    asyncio.run(AudioBroadcasterServer.amain())
