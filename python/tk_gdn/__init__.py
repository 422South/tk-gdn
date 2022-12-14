# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk

gdn_bridge = sgtk.platform.import_framework(
    "tk-framework-gdn", "tk_framework_gdn.gdn_bridge"
)

GDNBridge = gdn_bridge.GDNBridge

shotgun_data = sgtk.platform.import_framework(
    "tk-framework-shotgunutils", "shotgun_data"
)

shotgun_globals = sgtk.platform.import_framework(
    "tk-framework-shotgunutils", "shotgun_globals"
)

shotgun_settings = sgtk.platform.import_framework(
    "tk-framework-shotgunutils", "settings"
)

if sgtk.util.is_windows():
    win_32_api = sgtk.platform.import_framework(
        "tk-framework-gdn", "tk_framework_gdn_utils.win_32_api"
    )
