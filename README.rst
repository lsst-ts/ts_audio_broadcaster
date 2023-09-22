####################
ts_audio_broadcaster
####################

``ts_audio_broadcaster`` is a component of LSST Telescope and Site software. It is used to generate web service that broadcasts audio from microphones installed on the observatory facilities.

The service is implemented as a Tornado web server that uses websockets to broadcast audio data to clients. The audio data is captured from the microphone using the ``pyaudio`` library.


Configuration
-------------

The service is configured via the following environment variables;
All are optional except the few marked "(required)":

* ``WEBSERVER_PORT`` (required): port for the tornado web server; default=8888.

Development
-----------

To run the service locally, first install the package as follows::

    pip install -e .

Then run the service::

    python -m ts_audio_broadcaster <mic_server_ip> <mic_server_port> --log-level=<log_level>

This code uses ``pre-commit`` to maintain ``black`` formatting and ``flake8`` compliance. To enable this, run the following commands once (the first removes the previous pre-commit hook)::

    git config --unset-all core.hooksPath
    generate_pre_commit_conf

For more details on how to use generate_pre_commit_conf please follow: https://tssw-developer.lsst.io/procedures/pre_commit.html#ts-pre-commit-conf.