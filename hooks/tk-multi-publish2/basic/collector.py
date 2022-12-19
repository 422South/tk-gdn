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
            }, "Render Sequence Template": {
                "type": "template",
                "default": None,
                "description": "Template path for render files. Should "
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

        self.collect_movies(parent_item, gdn.Workspace.getWorking_directory())
        self.collect_renders(gdn.Workspace.getWorking_directory(), settings, work_template, parent_item)
        pass

    def __icon_path(self):
        return os.path.join(self.disk_location, os.pardir, "icons", "gdn_icon.png")

    def __get_work_template_for_item(self, settings):
        # try to get the work-template
        work_template_setting = settings.get("Work Template")
        if work_template_setting:
            return self.parent.engine.get_template_by_name(work_template_setting.value)

    def __get_render_collector_template_for_item(self, settings):
        # try to get the work-template
        render_collector_template_setting = settings.get("Render Sequence Template")
        if render_collector_template_setting:
            return self.parent.engine.get_template_by_name(render_collector_template_setting.value)

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
            item.name = "%s (%s)" % (item.name, "movie render")

    def collect_renders(self, project_root, settings, work_template, parent_item):
        images_directory = self.parent.engine.gdn.Workspace.getImages_directory()
        render_collector_template = self.__get_render_collector_template_for_item(settings)
        entity_fields = work_template.get_fields(self.parent.engine.gdn.Workspace.get_current_scene_path())
        if not render_collector_template:
            self.logger.debug("Missing render collection template !! skipping render files")
            return None

        if not images_directory:
            images_directory = "images"

        renders_directory = os.path.join(project_root, images_directory)

        for root, dirs, files in os.walk(renders_directory, followlinks=False):
            for dir in dirs:
                normalised_path = sgtk.util.ShotgunPath.normalize(os.path.join(root, dir))
                frame_sequences = self.parent.util.get_frame_sequences(normalised_path)
                for (seq_spec, seq_paths) in frame_sequences:
                    self.logger.info("Trying to match sequence %s" % seq_spec)
                    validated = render_collector_template.validate(seq_spec)
                    if not validated:
                        self.logger.debug("Invalid sequence spec does not match collection template %s" % seq_spec)
                        continue
                    fields = render_collector_template.get_fields(seq_spec)
                    entity_type = self.parent.context.entity.get('type')
                    if entity_fields.get(entity_type) != fields.get(entity_type):
                        self.logger.debug("Skipping Sequence spec does not match current %s %s %s" % (
                            entity_type, seq_spec, entity_fields.get(entity_type)))
                    if entity_fields.get('version') != fields.get('version'):
                        self.logger.debug("Skipping Sequence spec does not match current version %s %s" % (
                            seq_spec, entity_fields.get('version')))
                        continue
                    self.logger.info("Found Sequence  %s ... adding" % seq_spec)
                    name = " %s - %s v%s" % (fields.get(entity_type), fields.get('name'), '{:0>3}'.format(fields.get('version')))
                    comment = 'Rendered Sequence'
                    # create a publish item for the document
                    publish_item = parent_item.create_item("gdn.rendering", comment, name)

                    publish_item.set_icon_from_path(self.__icon_path())

                    # disable thumbnail creation for After Effects documents. for the
                    # default workflow, the thumbnail will be auto-updated after the
                    # version creation plugin runs
                    publish_item.thumbnail_enabled = False
                    publish_item.context_change_allowed = False
                    # TODO look at publish rendering - can we remove the paths iterator
                    publish_item.properties["renderpaths"] = [seq_spec]
                    publish_item.expanded = True
                    publish_item.checked = True
                    if work_template is not None:
                        publish_item.properties["work_template"] = work_template
                    # publish_item.set_thumbnail_from_path(path)


