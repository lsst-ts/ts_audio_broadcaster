####################
ts_audio_broadcaster
####################

``ts_audio_broadcaster`` is is a component of LSST Telescope and Site software. It is used to generate web service that broadcasts audio from microphones installed on the observatory facilities.

The service is implemented as a Tornado web server that uses websockets to broadcast audio data to clients. The audio data is captured from the microphone using the ``pyaudio`` library.


Configuration
-------------

The service is configured via the following environment variables;
All are optional except the few marked "(required)":

* ``SERVICE_PORT`` (required): port to listen on; default=8888.

Development
-----------

To run the service locally, first install the dependencies::

    pip install -r requirements.txt

Then run the service::

    python -m ts_audio_broadcaster

This code uses ``pre-commit`` to maintain ``black`` formatting and ``flake8`` compliance. To enable this, run the following commands once (the first removes the previous pre-commit hook)::

    git config --unset-all core.hooksPath
    pre-commit install