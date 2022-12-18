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
import sgtk
import re
import glob

HookBaseClass = sgtk.get_hook_baseclass()


class GDNSceneCollector(HookBaseClass):
    """
    Collector that operates on the current After Effects document. Should inherit
    from the basic collector hook.
    """

    @property
    def settings(self):
        """
        Dictionary defining the settings that this collector expects to receive
        through the settings parameter in the process_current_session and
        process_file methods.

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

        # grab any base class settings
        collector_settings = super(GDNSceneCollector, self).settings or {}

        # settings specific to this collector
        gdn_session_settings = {
            "Work Template": {
                "type": "template",
                "default": None,
                "description": "Template path for artist work files. Should "
                               "correspond to a template defined in "
                               "templates.yml. If configured, is made available"
                               "to publish plugins via the collected item's "
                               "properties. ",
            },
        }

        # update the base settings with these settings
        collector_settings.update(gdn_session_settings)

        return collector_settings

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the open documents in After Effects and creates publish items
        parented under the supplied item.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """
        gdn = self.parent.engine.gdn

        # check if the current project was saved already
        # if not we will not add a publish item for it
        parent_item = self.__get_project_publish_item(settings, parent_item)
        if gdn.Workspace.getCurrent_scenefile() == None:
            return

        work_template = self.__get_work_template_for_item(settings)

        render_paths = []

        #
        # comment = "GDN Render Files"
        # item_name = "Render File"
        #
        # self.__create_publish_item(
        #     parent_item,
        #     item_name,
        #     comment,
        #     render_paths,
        #     work_template,
        # )

        self.collect_movies(parent_item, gdn.Workspace.getWorking_directory())
        self.collect_renders(parent_item, gdn.Workspace.getWorking_directory())

    def __icon_path(self):
        return os.path.join(self.disk_location, os.pardir, "icons", "gdn_icon.png")

    def __get_work_template_for_item(self, settings):
        # try to get the work-template
        work_template_setting = settings.get("Work Template")
        if work_template_setting:
            return self.parent.engine.get_template_by_name(work_template_setting.value)

    def __get_project_publish_item(self, settings, parent_item):
        """
        Will create a project publish item.

        :param settings: dict. Configured settings for this collector
        :param parent_item: Root item instance
        :returns: the newly created project item
        """
        project_name = "Untitled"
        path = self.parent.engine.project_path
        if path:
            project_name = self.parent.engine.gdn.Workspace.getCurrent_scenefile()
        project_item = parent_item.create_item(
            "gdn.project", "GDN Scene", project_name
        )
        self.logger.info("Collected GDN document: {}".format(project_name))

        project_item.set_icon_from_path(self.__icon_path())
        project_item.thumbnail_enabled = True
        project_item.properties["file_path"] = path
        project_item.properties["published_renderings"] = []
        if path:
            project_item.set_thumbnail_from_path(path)

        work_template = self.__get_work_template_for_item(settings)
        if work_template is not None:
            project_item.properties["work_template"] = work_template
            self.logger.debug("Work template defined for GDN collection.")
        return project_item

    def __create_publish_item(
            self,
            parent_item,
            name,
            comment,
            render_paths,
            work_template=None,
    ):
        """
        Will create a comp publish item.

        :param parent_item: Root item instance
        :param name: str name of the new item
        :param comment: str comment/subtitle of the comp item
        :param render_paths: list-of-str. filepaths to be expected from the render queue item. Sequence-paths
                should use the adobe-style sequence pattern [###]
        :param work_template: Template. The configured work template
        :returns: the newly created comp item
        """
        # create a publish item for the document
        publish_item = parent_item.create_item("gdn.project", comment, name)

        publish_item.set_icon_from_path(self.__icon_path())

        # disable thumbnail creation for After Effects documents. for the
        # default workflow, the thumbnail will be auto-updated after the
        # version creation plugin runs
        publish_item.thumbnail_enabled = False
        publish_item.context_change_allowed = False

        publish_item.properties["renderpaths"] = render_paths

        # enable the rendered render queue items and expand it. other documents are
        # collapsed and disabled.

        publish_item.expanded = True
        publish_item.checked = True

        for path in render_paths:
            publish_item.set_thumbnail_from_path(path)
            break

        if work_template:
            publish_item.properties["work_template"] = work_template
            self.logger.debug("Work template defined for GDN.")
        return publish_item

    def collect_movies(self, parent_item, project_root):
        """
        Creates items for quicktime playblasts.

        Looks for a 'project_root' property on the parent item, and if such
        exists, look for movie files in a 'movies' subfolder.

        :param parent_item: Parent Item instance
        :param str project_root: The maya project root to search for playblasts
        """

        movie_dir_name = None

        # try to query the file rule folder name for movies. This will give
        # us the directory name set for the project where movies will be
        # written
        if "movie" in self.parent.engine.gdn.Workspace.getMovies_directory():
            # this could return an empty string
            movie_dir_name = self.parent.engine.gdn.Workspace.getMovies_directory()

        if not movie_dir_name:
            # fall back to the default
            movie_dir_name = "movies"

        # ensure the movies dir exists
        movies_dir = os.path.join(project_root, movie_dir_name)
        self.logger.info("[Collector] MOVIES PATH: %s" % movies_dir)
        if not os.path.exists(movies_dir):
            return

        scene_file = self.parent.engine.gdn.Workspace.getCurrent_scenefile()
        match = re.match('(.*)\.v(\d{3})\.(\S{3,}$)', scene_file, flags=re.M)
        scene_version = None
        if match:
            scene_version = match.group(2)
            self.logger.debug("Scene version: v%s" % scene_version)

        self.logger.info(
            "Processing movies folder: %s" % (movies_dir,),
            extra={"action_show_folder": {"path": movies_dir}},
        )

        # look for movie files in the movies folder
        for filename in os.listdir(movies_dir):

            # do some early pre-processing to ensure the file is of the right
            # type. use the base class item info method to see what the item
            # type would be.
            item_info = self._get_item_info(filename)
            if item_info["item_type"] != "file.video":
                continue

            # Not bothering to match off the scene name here but could be implemented for further restriction

            if scene_version is None:
                self.logger.debug(
                    "Not collecting %s as it does not match required {shotname}.v000.mov format" % filename)
                continue
            movie_path = os.path.join(movies_dir, filename)
            match = re.match('(.*)\.v(\d{3})\.(.{3,}$)', movie_path, flags=re.M)
            if not match:
                self.logger.info("Not collecting %s as the movie does not match the correct template" % filename)
                continue

            if match.group(2) != scene_version:
                self.logger.info("Not collecting %s as version v%s does not match scene version v%s" % (
                    filename, match.group(2), scene_version))
                continue

            # allow the base class to collect and create the item. it knows how
            # to handle movie files
            item = super(GDNSceneCollector, self)._collect_file(
                parent_item, movie_path
            )

            # the item has been created. update the display name to include
            # the an indication of what it is and why it was collected
            item.name = "%s (%s)" % (item.name, "playblast")

    def collect_renders(self, parent_item, project_root):
        images_directory = self.parent.engine.gdn.Workspace.getImages_directory()

        if not images_directory:
            images_directory = "images"

        renders_directory = os.path.join(project_root, images_directory)
        render_paths = glob.glob(renders_directory)

        # for path in render_paths:
        #
        #     rendered_paths = glob.glob(path)
        #
        #     if rendered_paths:
        #         self.__logger.debug("rendered_paths: %s" % rendered_paths)
        #
        #         normalised_path = sgtk.util.ShotgunPath.normalize(path)
        #         seq_dir = os.path.dirname(normalised_path)
        #         frame_sequences = publisher.util.get_frame_sequences(seq_dir)
        #
        #         for (seq_spec, seq_paths) in frame_sequences:
        #             self.__logger.debug("Trying to match sequence %s" % seq_spec)
        #             #TODO match version number
