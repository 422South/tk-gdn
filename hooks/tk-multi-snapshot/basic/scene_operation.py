# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
from sgtk import Hook


class SceneOperation(Hook):
    """
    Hook called to perform an operation with the
    current scene
    """

    def execute(self, operation, file_path, **kwargs):
        """
        Main hook entry point

        :operation: String
                    Scene operation to perform

        :file_path: String
                    File path to use if the operation
                    requires it (e.g. open)

        :returns:   Depends on operation:
                    'current_path' - Return the current scene
                                     file path as a String
                    all others     - None
        """
        gdn = self.parent.engine.gdn

        if operation == "current_path":
            pass
            # file_obj = gdn.app.project.file
            # if file_obj != None:
            #     return file_obj.fsName
            # raise TankError("The active document must be saved!")

        elif operation == "open":
            pass
            # gdn.app.project.close(adobe.CloseOptions.DO_NOT_SAVE_CHANGES)
            # gdn.app.open(adobe.File(file_path))

        elif operation == "save":
            pass
            # save the current script
            # gdn.app.project.save()
