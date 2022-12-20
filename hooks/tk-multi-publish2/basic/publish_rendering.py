# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
import re

import sgtk

HookBaseClass = sgtk.get_hook_baseclass()


class GDNRenderPublishPlugin(HookBaseClass):
    """
    Plugin for publishing GDN renderings.

    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{engine}/tk-multi-publish2/basic/publish_rendering.py"

    """

    REJECTED, FULLY_ACCEPTED = range(2)

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        loader_url = "https://developer.shotgridsoftware.com/a4c0a4f1/?title=Loader"

        return """
        Publishes Render Queue elements to ShotGrid. A <b>Publish</b> entry will be
        created in ShotGrid which will include a reference to the file's current
        path on disk. Other users will be able to access the published file via
        the <b><a href='%s'>Loader</a></b> so long as they have access to
        the file's location on disk.

        <h3>Overwriting an existing publish</h3>
        A file can be published multiple times however only the most recent
        publish will be available to other users. Warnings will be provided
        during validation if there are previous publishes.
        """ % (
            loader_url,
        )

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to receive
        through the settings parameter in the accept, validate, publish and
        finalize methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """

        # inherit the settings from the base publish plugin
        base_settings = super(GDNRenderPublishPlugin, self).settings or {}
        seq_publish_settings = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published render sequence files. Should"
                               "correspond to a template defined in "
                               "templates.yml.",
            },
        }
        base_settings.update(seq_publish_settings)
        return base_settings

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """
        return ["gdn.rendering"]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via the
        item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

            - accepted: Indicates if the plugin is interested in this value at
               all. Required.
            - enabled: If True, the plugin will be enabled in the UI, otherwise
                it will be disabled. Optional, True by default.
            - visible: If True, the plugin will be visible in the UI, otherwise
                it will be hidden. Optional, True by default.
            - checked: If True, the plugin will be checked in the UI, otherwise
                it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """
        if self.__is_acceptable(settings, item) is self.REJECTED:
            return {"accepted": False}

        return {"accepted": True, "checked": True}

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.

        Returns a boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: True if item is valid, False otherwise.
        """
        if self.__is_acceptable(settings, item) is not self.FULLY_ACCEPTED:
            return False

        # run the base class validation
        return super(GDNRenderPublishPlugin, self).validate(settings, item)

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """
        item.properties["publish_type"] = "Rendered Image"
        render_paths = item.properties.get("renderpaths", [])
        publish_template_setting = settings.get("Publish Template")
        if not publish_template_setting:
            error_msg = "A publish template must exist for this plugin to work"
            self.logger.error(
                error_msg,
            )
            raise Exception(error_msg)
        publish_template = self.parent.engine.get_template_by_name(
            publish_template_setting.value
        )

        published_renderings = item.properties.get("published_renderings", [])
        for each_path in render_paths:
            path = re.sub(r"[\[\]]", "", each_path)
            item.properties["path"] = path
            if publish_template:
                item.properties["publish_template"] = publish_template
            work_template = item.properties["work_template"]
            if not work_template:
                continue
            # get the current scene path and extract fields from it using the work
            work_fields = work_template.get_fields(path)
            # template:

            # include the camera name in the fields
            # ensure the fields work for the publish template
            missing_keys = publish_template.missing_keys(work_fields)
            if missing_keys:
                error_msg = "Work file '%s' missing keys required for the " \
                            "publish template: %s" % (path, missing_keys)
                self.logger.error(error_msg)
                raise Exception(error_msg)

            super(GDNRenderPublishPlugin, self).publish(settings, item)

            published_renderings.append(item.properties.get("sg_publish_data"))

    def __is_acceptable(self, settings, item):
        """
        This method is a helper to decide, whether the current publish item
        is valid. it is called from the validate and the accept method.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: int indicating the acceptance-level. One of
            REJECTED, PARTIALLY_ACCEPTED, FULLY_ACCEPTED
        """

        render_paths = item.properties.get("renderpaths")
        work_template = item.properties.get("work_template")
        project_path = sgtk.util.ShotgunPath.normalize(self.parent.engine.project_path)

        # set the item path to some temporary value
        for each_path in render_paths:
            item.properties["path"] = re.sub(r"[\[\]]", "", each_path)
            break

        # check if the current configuration has templates assigned
        if (not work_template):
            self.logger.warn(
                (
                    "Publishing renders is not "
                    "supported without configured templates."
                )
            )
            return self.REJECTED

        if not project_path:
            self.logger.warn(
                "Project has to be saved in order to allow publishing renderings",
                extra=self.__get_save_as_action(),
            )
            return self.REJECTED

        return self.FULLY_ACCEPTED

    def __get_save_as_action(self):
        """
        Simple helper for returning a log action dict for saving the project
        """

        engine = self.parent.engine

        # default save callback
        callback = lambda: engine.save_as()

        # if workfiles2 is configured, use that for file save
        if "tk-multi-workfiles2" in engine.apps:
            app = engine.apps["tk-multi-workfiles2"]
            if hasattr(app, "show_file_save_dlg"):
                callback = app.show_file_save_dlg

        return {
            "action_button": {
                "label": "Save As...",
                "tooltip": "Save the active project",
                "callback": callback,
            }
        }
