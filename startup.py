# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import pathlib
import sys

import sgtk
import sgtk.platform.framework
from sgtk.platform import SoftwareLauncher, SoftwareVersion, LaunchInformation


class EngineConfigurationError(sgtk.TankError):
    pass


class GDNLauncher(SoftwareLauncher):
    """
    Handles the launching of GDN. Contains the logic for
    scanning for installed versions of the software and
    how to correctly set up a launch environment for the tk-aftereffects
    engine.
    """

    # Named regex strings to insert into the executable template paths when
    # matching against supplied versions and products. Similar to the glob
    # strings, these allow us to alter the regex matching for any of the
    # variable components of the path in one place
    COMPONENT_REGEX_LOOKUP = {
        "version": "[\d.]+",
        "version_back": "[\d.]+",  # backreference to ensure same version
    }

    # This dictionary defines a list of executable template strings for each
    # of the supported operating systems. The templates are used for both
    # globbing and regex matches by replacing the named format placeholders
    # with an appropriate glob or regex string. As Adobe adds modifies the
    # install path on a given OS for a new release, a new template will need
    # to be added here.
    #
    EXECUTABLE_MATCH_TEMPLATES = [
        {
            "win32": os.path.join(pathlib.Path.home(),
                                  "AppData/Roaming",
                                  "422 Global Data Navigator/{version}/422GlobalDataNavigator-{version_back}.exe"),
        },
    ]

    @property
    def minimum_supported_version(self):
        """
        The minimum software version that is supported by the launcher.
        """
        return "6.0.300"

    def prepare_launch(self, exec_path, args, file_to_open=None):
        """
        Prepares an environment to launch GDN so that will automatically
        load Toolkit after startup.

        :param str exec_path: Path to Maya executable to launch.
        :param str args: Command line arguments as strings.
        :param str file_to_open: (optional) Full path name of a file to open on launch.
        :returns: :class:`LaunchInformation` instance
        """

        # determine all environment variables
        required_env = self.compute_environment()

        # Add std context and site info to the env
        std_env = self.get_standard_plugin_environment()
        required_env.update(std_env)

        # populate the file to open env.
        if file_to_open:
            required_env["SGTK_FILE_TO_OPEN"] = file_to_open

        return LaunchInformation(exec_path, args, required_env)

    def scan_software(self):
        """
        Scan the filesystem for all After Effects executables.

        :return: A list of :class:`SoftwareVersion` objects.
        """

        self.logger.debug("Scanning for GDN executables...")

        # use the bundled icon
        icon_path = os.path.join(self.disk_location, "icon_256.png")
        self.logger.debug("Using icon path: %s" % (icon_path,))

        platform = (
            "win32"
            if sgtk.util.is_windows()
            else "darwin"
            if sgtk.util.is_macos()
            else None
        )

        if platform is None:
            self.logger.debug("GDN not supported on this platform.")
            return []

        all_sw_versions = []

        for match_template_set in self.EXECUTABLE_MATCH_TEMPLATES:
            for executable_path, tokens in self._glob_and_match(
                    match_template_set[platform], self.COMPONENT_REGEX_LOOKUP
            ):
                self.logger.debug(
                    "Processing %s with tokens %s", executable_path, tokens
                )
                # extract the components (default to None if not included). but
                # version is in all templates, so should be there.
                executable_version = tokens.get("version")

                sw_version = SoftwareVersion(
                    executable_version, "422 Global Data Navigator", executable_path, icon_path
                )
                supported, reason = self._is_supported(sw_version)
                if supported:
                    all_sw_versions.append(sw_version)
                else:
                    self.logger.debug(reason)

        return all_sw_versions

    def compute_environment(self):
        """
        Return the env vars needed to launch the GDN in SG mode.

        This will generate a dictionary of environment variables

        :returns: dictionary of env var string key/value pairs.
        """
        env = {}

        # TODO
        framework_location = self.__get_gdn_framework_location()
        if framework_location is None:
            raise EngineConfigurationError(
                (
                    "The tk-framework-gdn "
                    "could not be found in the current environment. "
                    "Please check the log for more information."
                )
            )
        # TODO
        # set the interpreter with which to launch the GDN integration
        env["SHOTGUN_GDN_PYTHON"] = sys.executable
        env["SHOTGUN_GDN_FRAMEWORK_LOCATION"] = framework_location
        env["SHOTGUN_ENGINE"] = "tk-gdn"

        # We're going to append all of this Python process's sys.path to the
        # PYTHONPATH environment variable. This will ensure that we have access
        # to all libraries available in this process in subprocesses like the
        # Python process that is spawned by the Shotgun CEP extension on launch
        # of an Adobe host application. We're appending instead of setting because
        # we don't want to stomp on any PYTHONPATH that might already exist that
        # we want to persist when the Python subprocess is spawned.
        sgtk.util.append_path_to_env_var(
            "PYTHONPATH", os.pathsep.join(sys.path),
        )
        env["PYTHONPATH"] = os.environ["PYTHONPATH"]

        return env

    def __get_gdn_framework_location(self):
        """
        This helper method will query the current disc-location for the configured
        tk-adobe-framework.

        This is necessary, as the the framework relies on an environment variable
        to be set by the parent engine and also the SG menu to be installed.

        TODO: When the following logic was implemented, there was no way of
            accessing the engine's frameworks at launch time. Once this is
            possible, this logic should be replaced.

        Returns (str or None): The tk-gdn-framework disc-location directory path
            configured under the tk-multi-launchapp
        """

        engine = sgtk.platform.current_engine()
        env_name = engine.environment.get("name")

        env = engine.sgtk.pipeline_configuration.get_environment(env_name)
        engine_desc = env.get_engine_descriptor("tk-gdn")
        if env_name is None:
            self.logger.warn(
                (
                    "The current environment {!r} "
                    "is not configured to run the tk-gdn "
                    "engine. Please add the engine to your env-file: "
                    "{!r}"
                ).format(env, env.disk_location)
            )
            return

        framework_name = None
        for req_framework in engine_desc.get_required_frameworks():
            if req_framework.get("name") == "tk-framework-gdn":
                name_parts = [req_framework["name"]]
                if "version" in req_framework:
                    name_parts.append(req_framework["version"])
                framework_name = "_".join(name_parts)
                break
        else:
            self.logger.warn(
                (
                    "The engine tk-gdn must have "
                    "the tk-framework-gdn configured in order to run"
                )
            )
            return

        desc = env.get_framework_descriptor(framework_name)
        return desc.get_path()
