"""Sphinx configuration file for an LSST stack package.

This configuration only affects single-package Sphinx documentation builds.
"""

import lsst.ts.salobj  # noqa
from documenteer.conf.pipelinespkg import *  # type: ignore # noqa

project = "ts_audio_broadcaster"
html_theme_options["logotext"] = project  # type: ignore # noqa
html_title = project
html_short_title = project
# Avoid warning: Could not find tag file _doxygen/doxygen.tag
doxylink = {}  # type: ignore
