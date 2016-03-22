"""
.. module:: storage
   :platform: Unix, Windows
   :synopsis: A module to store a statemachine in the local file system

.. moduleauthor:: Sebastian Brunner


"""

import os
import shutil
import glob
from time import gmtime, strftime
import copy

import yaml
from gtkmvc import Observable

from rafcon.statemachine.state_machine import StateMachine
from rafcon.statemachine.config import global_config
from rafcon.statemachine.custom_exceptions import LibraryNotFoundException

from rafcon.utils.constants import RAFCON_TEMP_PATH_STORAGE
from rafcon.utils import filesystem
from rafcon.utils import storage_utils
from rafcon.utils import log
logger = log.get_logger(__name__)


LIBRARY_NOT_FOUND_DUMMY_STATE_NAME = "LIBRARY NOT FOUND DUMMY STATE"


# clean the DEFAULT_SCRIPT_PATH folder at each program start
from rafcon.statemachine.enums import DEFAULT_SCRIPT_PATH
if os.path.exists(DEFAULT_SCRIPT_PATH):
    files = glob.glob(os.path.join(DEFAULT_SCRIPT_PATH, "*"))
    for f in files:
        shutil.rmtree(f)


class StateMachineStorage(Observable):

    """This class implements the Storage interface by using a file system on the disk.

    The data storage format is a directory system.

    :ivar base_path: the base path to resolve all relative paths
    :ivar _paths_to_remove_before_sm_save: each state machine holds a list of paths that are going to be removed while
                                            saving the state machine
    :ivar ids_of_modified_state_machines: each state machine has a flag if it was modified since the last saving
    """

    FILE_NAME_META_DATA = 'meta_data.json'
    FILE_NAME_META_DATA_OLD = 'gui_gtk.json'
    FILE_NAME_CORE_DATA = 'core_data.json'
    FILE_NAME_CORE_DATA_OLD = 'meta.json'
    SCRIPT_FILE = 'script.py'
    STATEMACHINE_FILE = 'statemachine.yaml'
    LIBRARY_FILE = 'library.yaml'

    def __init__(self, base_path=RAFCON_TEMP_PATH_STORAGE):
        Observable.__init__(self)

        self._base_path = None
        self.base_path = os.path.abspath(base_path)
        logger.debug("Storage class initialized!")
        self._paths_to_remove_before_sm_save = {}

    def mark_path_for_removal_for_sm_id(self, state_machine_id, path):
        """
        Marks a path for removal. The path is removed if the state machine of the specified state machine id is saved.
        :param state_machine_id: the state machine id the path belongs to
        :param path: the path to a state that was deleted
        :return:
        """
        if state_machine_id not in self._paths_to_remove_before_sm_save.iterkeys():
            self._paths_to_remove_before_sm_save[state_machine_id] = []
            logger.debug("path %s for state machine id %s is going to be deleted during saving of the state machine" %
                         (str(path), str(state_machine_id)))
        self._paths_to_remove_before_sm_save[state_machine_id].append(path)

    def unmark_path_for_removal_for_sm_id(self, state_machine_id, path):
        """
        Unmarks a path for removal.
        :param state_machine_id: the state machine id the path belongs to
        :param path: the path to a state that should not be removed
        :return:
        """
        if state_machine_id in self._paths_to_remove_before_sm_save.iterkeys():
            if path in self._paths_to_remove_before_sm_save[state_machine_id]:
                self._paths_to_remove_before_sm_save[state_machine_id].remove(path)

    def save_statemachine_to_path(self, statemachine, base_path, version=None, delete_old_state_machine=False,
                                  save_as=False, temporary_storage=False):
        """
        Saves a root state to a yaml file.
        :param statemachine: the statemachine to be saved
        :param base_path: base_path to which all further relative paths refers to
        :param version: the version of the statemachine to save
        :return:
        """
        if base_path is not None:
            self.base_path = base_path

        if not temporary_storage:
            if save_as:
                if statemachine.state_machine_id in self._paths_to_remove_before_sm_save.iterkeys():
                    self._paths_to_remove_before_sm_save[statemachine.state_machine_id] = {}
            else:
                # remove all paths that were marked to be removed
                if statemachine.state_machine_id in self._paths_to_remove_before_sm_save.iterkeys():
                    for path in self._paths_to_remove_before_sm_save[statemachine.state_machine_id]:
                        if os.path.exists(path):
                            filesystem.remove_path(path)

        root_state = statemachine.root_state
        # clean old path first
        if os.path.exists(self.base_path):
            if delete_old_state_machine:
                filesystem.remove_path(self.base_path)
        if not os.path.exists(self.base_path):
            filesystem.create_path(self.base_path)
        f = open(os.path.join(self.base_path, self.STATEMACHINE_FILE), 'w')
        last_update = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        creation_time = last_update
        if hasattr(statemachine, 'creation_time'):
            creation_time = statemachine.creation_time
        statemachine_content = "root_state: %s\nversion: %s\ncreation_time: %s\nlast_update: %s"\
                               % (root_state.state_id, version, creation_time, last_update)
        yaml.dump(yaml.load(statemachine_content), f, indent=4)
        f.close()
        # set the file_system_path of the state machine
        if not temporary_storage:
            statemachine.file_system_path = copy.copy(base_path)
        # add root state recursively
        self.save_state_recursively(root_state, "")
        if statemachine.marked_dirty and not temporary_storage:
            statemachine.marked_dirty = False
        if not temporary_storage:
            statemachine.file_system_path = self.base_path
        logger.debug("Successfully saved statemachine!")

    def save_script_file_for_state_and_source_path(self, state, state_path):
        """
        Saves the script file for a state to the directory of the state. The script name will be set to the SCRIPT_FILE
        constant.
        :param state: The state of which the script file should be saved
        :param state_path: The path of the state meta file
        :return:
        """
        from rafcon.statemachine.states.execution_state import ExecutionState
        if isinstance(state, ExecutionState):
            state_path_full = os.path.join(self.base_path, state_path)
            source_script_file = os.path.join(state.get_file_system_path(), state.script.filename)
            destination_script_file = os.path.join(state_path_full, self.SCRIPT_FILE)
            if not source_script_file == destination_script_file:
                try:
                    if not os.path.exists(source_script_file):
                            script_file = open(destination_script_file, 'w')
                            script_file.write(state.script_text)
                            script_file.close()
                    else:
                        shutil.copyfile(source_script_file, destination_script_file)
                except Exception:
                    logger.warning("Copy of script file failed: {0} -> {1}".format(source_script_file,
                                                                                   destination_script_file))
                    raise

                state.script.reload_path(self.SCRIPT_FILE)
            else:  # load text into script file
                script_file = open(source_script_file, 'w')
                script_file.write(state.script_text)
                script_file.close()

    @staticmethod
    def save_script_file(state):
        script_file_path = os.path.join(state.get_file_system_path(), state.script.filename)
        script_file = open(script_file_path, 'w')
        script_file.write(state.script_text)
        script_file.close()

    def save_state_recursively(self, state, parent_path, force_full_load=False):
        """
        Recursively saves a state to a yaml file. It calls this method on all its substates.
        :param state:
        :param parent_path:
        :return:
        """
        from rafcon.statemachine.states.execution_state import ExecutionState
        from rafcon.statemachine.states.container_state import ContainerState
        state_path = os.path.join(parent_path, str(state.state_id))
        state_path_full = os.path.join(self.base_path, state_path)
        filesystem.create_path(state_path_full)
        if isinstance(state, ExecutionState):
            self.save_script_file_for_state_and_source_path(state, state_path)

        storage_utils.write_dict_to_json(state, os.path.join(state_path_full, self.FILE_NAME_CORE_DATA))

        # create yaml files for all children
        if isinstance(state, ContainerState):
            for state in state.states.itervalues():
                self.save_state_recursively(state, state_path, force_full_load)

    def load_statemachine_from_path(self, base_path=None):
        """
        Loads a state machine from a given path. If no path is specified the state machine is tried to be loaded
        from the base path.
        :param base_path: An optional base path for the state machine.
        :return: a tuple of the loaded container state, the version of the state and the creation time
        """
        if base_path is not None:
            self.base_path = base_path
        logger.debug("Load state machine from path %s" % str(base_path))
        try:
            stream = file(os.path.join(self.base_path, self.STATEMACHINE_FILE), 'r')
        except IOError:
            raise AttributeError("Provided path doesn't contain a valid state-machine: {0}".format(base_path))
        tmp_dict = yaml.load(stream)
        root_state_id = tmp_dict['root_state']
        version = tmp_dict['version']
        creation_time = tmp_dict['creation_time']
        if 'last_update' not in tmp_dict:
            last_update = creation_time
        else:
            last_update = tmp_dict['last_update']
        tmp_base_path = os.path.join(self.base_path, root_state_id)
        logger.debug("Loading root state from path %s" % tmp_base_path)
        sm = StateMachine()
        sm.version = version
        sm.creation_time = creation_time
        sm.last_update = last_update
        sm.file_system_path = self.base_path
        sm.root_state = self.load_state_recursively(parent=sm, state_path=tmp_base_path)
        sm.marked_dirty = False

        hierarchy_level = 0
        number_of_states, hierarchy_level = sm.root_state.get_states_statistics(hierarchy_level)
        logger.debug("Loaded state machine ({1}) has {0} states. (Max hierarchy level {2})".
                     format(number_of_states,
                            base_path,
                            hierarchy_level))
        logger.debug("Loaded state machine ({1}) has {0} transitions.".format(sm.root_state.get_number_of_transitions(),
                                                                              base_path))

        return [sm, version, creation_time]

    def load_state_from_path(self, state_path):
        """
        Loads a state from a given path
        from the base path.
        :param state_path: The path of the state on the file system.
        :return: the loaded state
        """
        return self.load_state_recursively(parent=None, state_path=state_path)

    def load_state_recursively(self, parent, state_path=None):
        """
        Recursively loads the state. It calls this method on each sub-state of a container state.
        :param parent:  the root state of the last load call to which the loaded state will be added
        :param state_path: the path on the filesystem where to find eht meta file for the state
        :return:
        """

        path_core_data = os.path.join(state_path, self.FILE_NAME_CORE_DATA)

        # TODO: Should be removed with next minor release
        if not os.path.exists(path_core_data):
            path_core_data = os.path.join(state_path, self.FILE_NAME_CORE_DATA_OLD)

        try:
            state_info = self.load_data_file(path_core_data)
        except LibraryNotFoundException, e:
            logger.error("Library could not be loaded: {0}\n"
                         "Skipping library and continuing loading the state machine".format(str(e.message)))

            from rafcon.statemachine.states.hierarchy_state import HierarchyState
            state_id = self.retrieve_state_id_core_data_file(path_core_data)
            dummy_state = HierarchyState(LIBRARY_NOT_FOUND_DUMMY_STATE_NAME, state_id=state_id)
            # set parent of dummy state
            if parent:
                from rafcon.statemachine.states.state import State
                if isinstance(parent, State):
                    parent.add_state(dummy_state, storage_load=True)
                else:
                    dummy_state.parent = parent
            return dummy_state

        # Transitions and data flows are not added when loading a state, as also states are not added.
        # We have to wait until the child states are loaded, before adding transitions and data flows, as otherwise the
        # validity checks for transitions and data flows would fail
        if not isinstance(state_info, tuple):
            state = state_info
        else:
            state = state_info[0]
            transitions = state_info[1]
            data_flows = state_info[2]

        # set parent of state
        from rafcon.statemachine.states.state import State
        if parent:
            if isinstance(parent, State):
                parent.add_state(state, storage_load=True)
            else:
                state.parent = parent
        else:
            # as the parent is None the state cannot calculate its path, therefore the path is cached for it
            state.set_file_system_path(state_path)

        from rafcon.statemachine.states.execution_state import ExecutionState
        if isinstance(state, ExecutionState):
            state.script.reload_path(self.SCRIPT_FILE)
            self.load_script_file(state)

        one_of_my_child_states_not_found = False

        # load child states
        for p in os.listdir(state_path):
            child_state_path = os.path.join(state_path, p)
            if os.path.isdir(child_state_path):
                child_state = self.load_state_recursively(state, child_state_path)
                if child_state.name is LIBRARY_NOT_FOUND_DUMMY_STATE_NAME:
                    one_of_my_child_states_not_found = True

        if one_of_my_child_states_not_found:
            # omit adding transitions and data flows in this case
            pass
        else:
            # Now we can add transitions and data flows, as all child states were added
            if isinstance(state_info, tuple):
                state.transitions = transitions
                state.data_flows = data_flows

        return state

    @staticmethod
    def retrieve_state_id_core_data_file(filename):
        if os.path.exists(filename):
            content = storage_utils.load_dict_from_json(filename, as_dict=True)
            return content["state_id"]
        raise ValueError("Data file not found: {0}".format(filename))

    @staticmethod
    def load_data_file(filename):
        if os.path.exists(filename):
            return storage_utils.load_dict_from_json(filename)
        raise ValueError("Data file not found: {0}".format(filename))

    @staticmethod
    def load_script_file(state):
        from rafcon.statemachine.states.execution_state import ExecutionState
        if isinstance(state, ExecutionState):
            script = filesystem.read_file(state.get_file_system_path(), state.script.filename)
            state.script_text = script

    #########################################################################
    # Properties for all class fields that must be observed by gtkmvc
    #########################################################################

    @property
    def base_path(self):
        """Property for the _base_path field

        """
        return self._base_path

    @base_path.setter
    @Observable.observed
    def base_path(self, base_path):
        if not isinstance(base_path, basestring):
            raise TypeError("base_path must be of type str")

        self._base_path = base_path