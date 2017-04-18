# Copyright (C) 2015-2017 DLR
#
# All rights reserved. This program and the accompanying materials are made
# available under the terms of the Eclipse Public License v1.0 which
# accompanies this distribution, and is available at
# http://www.eclipse.org/legal/epl-v10.html
#
# Contributors:
# Annika Wollschlaeger <annika.wollschlaeger@dlr.de>
# Benno Voggenreiter <benno.voggenreiter@dlr.de>
# Franz Steinmetz <franz.steinmetz@dlr.de>
# Lukas Becker <lukas.becker@dlr.de>
# Mahmoud Akl <mahmoud.akl@dlr.de>
# Matthias Buettner <matthias.buettner@dlr.de>
# Rico Belder <rico.belder@dlr.de>
# Sebastian Brunner <sebastian.brunner@dlr.de>

"""
.. module:: state_machines_editor
   :synopsis: A module that holds the controller with the interface to the state machines notebook.

"""

import collections
import copy
import gtk

import rafcon.core.singleton
from rafcon.core.states.hierarchy_state import HierarchyState
from rafcon.gui.config import global_gui_config
from rafcon.gui.controllers.graphical_editor import GraphicalEditorController
from rafcon.gui.controllers.utils.extended_controller import ExtendedController
from rafcon.gui.helpers import text_formatting
from rafcon.gui.helpers.label import draw_for_all_gtk_states
from rafcon.gui.models.state_machine import StateMachineModel, StateMachine
from rafcon.gui.models.state_machine_manager import StateMachineManagerModel
from rafcon.gui.utils import constants
from rafcon.gui.utils.dialog import RAFCONButtonDialog
from rafcon.gui.views.graphical_editor import GraphicalEditorView
from rafcon.utils import log

logger = log.get_logger(__name__)

GAPHAS_AVAILABLE = True
try:
    from rafcon.gui.views.graphical_editor_gaphas import GraphicalEditorView as GraphicalEditorGaphasView
    from rafcon.gui.controllers.graphical_editor_gaphas import GraphicalEditorController as \
        GraphicalEditorGaphasController
except ImportError as e:
    logger.warn("The Gaphas graphical editor is not supported due to missing libraries: {0}".format(e.message))
    GAPHAS_AVAILABLE = False

ROOT_STATE_NAME_MAX_CHARS = 25


def create_tab_close_button(callback, *additional_parameters):
    close_label = gtk.Label()
    close_label.set_markup('<span font_desc="%s %s">&#x%s;</span>' % (constants.ICON_FONT, constants.FONT_SIZE_SMALL,
                                                                      constants.BUTTON_CLOSE))
    close_button = gtk.Button()
    close_button.set_size_request(width=constants.GRID_SIZE*3, height=constants.GRID_SIZE*3)
    close_button.set_relief(gtk.RELIEF_NONE)
    close_button.set_focus_on_click(True)
    close_button.add(close_label)

    close_button.connect('released', callback, *additional_parameters)

    return close_button


def create_tab_header(title, close_callback, *additional_parameters):
    label = gtk.Label(title)
    close_button = create_tab_close_button(close_callback, *additional_parameters)

    hbox = gtk.HBox()
    hbox.set_name("tab_label")

    hbox.pack_start(label, expand=True, fill=True, padding=constants.GRID_SIZE)
    hbox.pack_start(close_button, expand=False, fill=False, padding=0)
    hbox.show_all()

    return hbox, label


def set_tab_label_texts(label, state_machine_m, unsaved_changes=False):
    state_machine_id = state_machine_m.state_machine.state_machine_id
    root_state_name = state_machine_m.root_state.state.name
    root_state_name_trimmed = text_formatting.limit_string(root_state_name, ROOT_STATE_NAME_MAX_CHARS)
    state_machine_path = state_machine_m.state_machine.file_system_path or "[not yet saved]"
    label_text = "{0}&#8201;&#8226;&#8201;{1}".format(state_machine_id, root_state_name_trimmed)
    tooltip_text = root_state_name + "\n\nPath: " + state_machine_path
    if unsaved_changes:
        label_text += '&#8201;*'
    label.set_markup(label_text)
    label.set_tooltip_text(tooltip_text)


def get_state_machine_id(state_machine_m):
    return state_machine_m.state_machine.state_machine_id


def add_state_machine(widget, event=None):
    """Create a new state-machine when the user clicks on the '+' next to the tabs"""
    logger.debug("Creating new state-machine...")
    root_state = HierarchyState("new root state")
    state_machine = StateMachine(root_state)
    rafcon.core.singleton.state_machine_manager.add_state_machine(state_machine)


class StateMachinesEditorController(ExtendedController):
    """Controller handling the State Machines Editor

    :param  rafcon.gui.models.state_machine_manager.StateMachineManagerModel sm_manager_model: The state machine manager
         model, holding data regarding state machines.
    :param rafcon.gui.views.state_machines_editor.StateMachinesEditorView view: The GTK view showing the tabs of state
        machines.
    """

    def __init__(self, sm_manager_model, view):
        ExtendedController.__init__(self, sm_manager_model, view, spurious=True)

        assert isinstance(sm_manager_model, StateMachineManagerModel)

        self.state_machine_manager_model = sm_manager_model
        self.tabs = {}
        self.last_opened_state_machines = collections.deque(maxlen=10)

    def register_view(self, view):
        """Called when the View was registered"""
        self.view['notebook'].connect("add_state_machine", add_state_machine)
        self.view['notebook'].connect("close_state_machine", self.close_state_machine)
        self.view['notebook'].connect('switch-page', self.on_switch_page)

        # Add all already open state machines
        for state_machine in self.model.state_machines.itervalues():
            self.add_graphical_state_machine_editor(state_machine)

    def register_actions(self, shortcut_manager):
        """Register callback methods fot triggered actions.

        :param rafcon.gui.shortcut_manager.ShortcutManager shortcut_manager: Shortcut Manager Object holding mappings
            between shortcuts and actions.
        """
        shortcut_manager.add_callback_for_action('close', self.on_close_shortcut)

        # Call register_action of parent in order to register actions for child controllers
        super(StateMachinesEditorController, self).register_actions(shortcut_manager)

    def close_state_machine(self, widget, page_number):
        """Triggered when the close button in the tab is clicked
        """
        page = widget.get_nth_page(page_number)
        for tab_info in self.tabs.itervalues():
            if tab_info['page'] is page:
                state_machine_m = tab_info['state_machine_m']
                self.on_close_clicked(None, state_machine_m, None, force=False)
                return

    def on_close_shortcut(self, *args):
        """Close selected state machine (triggered by shortcut)"""
        state_machine_m = self.model.get_selected_state_machine_model()
        if state_machine_m is None:
            return
        self.on_close_clicked(None, state_machine_m, None, force=False)

    def on_switch_page(self, notebook, page_pointer, page_num):
        # Important: The method notification_selected_sm_changed will trigger this method, which in turn will trigger
        #               the notification_selected_sm_changed method again, thus some parts of this function will be
        #               triggerd twice => take care
        # From documentation: Note the page parameter is a GPointer and not usable within PyGTK. Use the page_num
        # parameter to retrieve the new current page using the get_nth_page() method.
        page = notebook.get_nth_page(page_num)
        for tab_info in self.tabs.itervalues():
            if tab_info['page'] is page:
                new_sm_id = get_state_machine_id(tab_info['state_machine_m'])
                if self.model.selected_state_machine_id != new_sm_id:
                    self.model.selected_state_machine_id = new_sm_id
                if self.last_opened_state_machines[len(self.last_opened_state_machines) - 1] != new_sm_id:
                    self.last_opened_state_machines.append(new_sm_id)
                return

    def rearrange_state_machines(self, page_num_by_sm_id):
        for sm_id, page_num in page_num_by_sm_id.iteritems():
            state_machine_m = self.tabs[sm_id]['state_machine_m']
            tab, tab_label = create_tab_header('', self.on_close_clicked, state_machine_m, 'refused')
            set_tab_label_texts(tab_label, state_machine_m, state_machine_m.state_machine.marked_dirty)
            page = self.tabs[sm_id]['page']
            self.view.notebook.remove_page(self.get_page_num(sm_id))
            self.view.notebook.insert_page(page, tab, page_num)

    def get_page_num(self, state_machine_id):
        page = self.tabs[state_machine_id]['page']
        page_num = self.view.notebook.page_num(page)
        return page_num

    def get_page_for_state_machine_id(self, state_machine_id):
        return self.tabs[state_machine_id]['page']

    def get_state_machine_id_for_page(self, page):
        for tab_info in self.tabs.itervalues():
            if tab_info['page'] is page:
                return get_state_machine_id(tab_info['state_machine_m'])

    def add_graphical_state_machine_editor(self, state_machine_m):
        """Add to for new state machine

        If a new state machine was added, a new tab is created with a graphical editor for this state machine.

        :param state_machine_m: The new state machine model
        """
        assert isinstance(state_machine_m, StateMachineModel)

        sm_id = get_state_machine_id(state_machine_m)
        logger.debug("Create new graphical editor for state machine with id %s" % str(sm_id))

        if global_gui_config.get_config_value('GAPHAS_EDITOR', False) and GAPHAS_AVAILABLE:
            graphical_editor_view = GraphicalEditorGaphasView()
            graphical_editor_ctrl = GraphicalEditorGaphasController(state_machine_m, graphical_editor_view)
        else:
            graphical_editor_view = GraphicalEditorView()
            graphical_editor_ctrl = GraphicalEditorController(state_machine_m, graphical_editor_view)

        self.add_controller(sm_id, graphical_editor_ctrl)

        tab, tab_label = create_tab_header('', self.on_close_clicked, state_machine_m, 'refused')
        set_tab_label_texts(tab_label, state_machine_m, state_machine_m.state_machine.marked_dirty)

        page = graphical_editor_view['main_frame']
        self.view.notebook.append_page(page, tab)
        self.view.notebook.set_tab_reorderable(page, True)
        page.show_all()

        self.tabs[sm_id] = {'page': page,
                            'state_machine_m': state_machine_m}

        graphical_editor_view.show()
        self.view.notebook.show()
        self.last_opened_state_machines.append(sm_id)

    @ExtendedController.observe("selected_state_machine_id", assign=True)
    def notification_selected_sm_changed(self, model, prop_name, info):
        """If a new state machine is selected, make sure the tab is open"""
        selected_state_machine_id = self.model.selected_state_machine_id
        if selected_state_machine_id is None:
            return

        page_id = self.get_page_num(selected_state_machine_id)

        # to retrieve the current tab colors
        number_of_pages = self.view["notebook"].get_n_pages()
        old_label_colors = range(number_of_pages)
        for p in range(number_of_pages):
            page = self.view["notebook"].get_nth_page(p)
            label = self.view["notebook"].get_tab_label(page).get_children()[0]
            old_label_colors[p] = label.get_style().fg[gtk.STATE_NORMAL]

        if not self.view.notebook.get_current_page() == page_id:
            self.view.notebook.set_current_page(page_id)

        # set the old colors
        for p in range(number_of_pages):
            page = self.view["notebook"].get_nth_page(p)
            label = self.view["notebook"].get_tab_label(page).get_children()[0]
            label.modify_fg(gtk.STATE_ACTIVE, old_label_colors[p])
            label.modify_fg(gtk.STATE_INSENSITIVE, old_label_colors[p])

    def set_active_state_machine(self, state_machine_id):
        page_num = self.get_page_num(state_machine_id)
        self.view.notebook.set_current_page(page_num)

    @ExtendedController.observe("state_machines", after=True)
    def model_changed(self, model, prop_name, info):
        # Check for new state machines
        for sm_id, sm in self.model.state_machine_manager.state_machines.iteritems():
            if sm_id not in self.tabs:
                self.add_graphical_state_machine_editor(self.model.state_machines[sm_id])

        # Check for removed state machines
        state_machines_to_be_deleted = []
        for sm_id in self.tabs:
            if sm_id not in self.model.state_machine_manager.state_machines:
                state_machines_to_be_deleted.append(self.tabs[sm_id]['state_machine_m'])
        for state_machine_m in state_machines_to_be_deleted:
            self.remove_state_machine(state_machine_m)

    @ExtendedController.observe("state_machine_mark_dirty", assign=True)
    def sm_marked_dirty(self, model, prop_name, info):
        sm_id = self.model.state_machine_mark_dirty
        if sm_id in self.model.state_machine_manager.state_machines:
            label = self.view["notebook"].get_tab_label(self.tabs[sm_id]["page"]).get_children()[0]
            set_tab_label_texts(label, self.tabs[sm_id]["state_machine_m"], True)

    @ExtendedController.observe("state_machine_un_mark_dirty", assign=True)
    def sm_un_marked_dirty(self, model, prop_name, info):
        sm_id = self.model.state_machine_un_mark_dirty
        if sm_id in self.model.state_machine_manager.state_machines:
            label = self.view["notebook"].get_tab_label(self.tabs[sm_id]["page"]).get_children()[0]
            set_tab_label_texts(label, self.tabs[sm_id]["state_machine_m"], False)

    def on_close_clicked(self, event, state_machine_m, result, force=False):
        """Triggered when the close button of a state machine tab is clicked

        Closes state machine if it is saved. Otherwise gives the user the option to 'Close without Saving' or to 'Cancel
        the Close Operation'

        :param state_machine_m: The selected state machine model.
        """
        from rafcon.core.execution.execution_status import StateMachineExecutionStatus
        from rafcon.core.singleton import state_machine_execution_engine, state_machine_manager

        def push_sm_running_dialog():
            def on_message_dialog_sm_running(widget, response_id):
                if response_id == 1:
                    logger.debug("State machine execution is being stopped")
                    state_machine_execution_engine.stop()
                    self.remove_state_machine(state_machine_m)
                elif response_id == 2:
                    logger.debug("State machine execution will keep running")
                widget.destroy()

            message_string = "The state machine is still running. Are you sure you want to close?"
            RAFCONButtonDialog(message_string, ["Stop and close", "Cancel"], on_message_dialog_sm_running,
                               message_type=gtk.MESSAGE_QUESTION, parent=self.get_root_window())

        if force:
            self.remove_state_machine(state_machine_m)
        # sm not saved

        elif state_machine_m.state_machine.marked_dirty:
            def on_message_dialog_response_signal(widget, response_id, state_machine_m):

                if response_id == 1:
                    if not state_machine_execution_engine.finished_or_stopped() \
                            and state_machine_manager.active_state_machine_id == \
                                    state_machine_m.state_machine.state_machine_id:
                        push_sm_running_dialog()
                    else:
                        self.remove_state_machine(state_machine_m)
                else:
                    logger.debug("Closing of state machine model canceled")
                widget.destroy()

            sm_id = get_state_machine_id(state_machine_m)
            root_state_name = state_machine_m.root_state.state.name
            message_string = "There are unsaved changed in the state machine '{0}' with id {1}. Do you want to close " \
                             "the state machine anyway?".format(root_state_name, sm_id)
            RAFCONButtonDialog(message_string, ["Close without saving", "Cancel"], on_message_dialog_response_signal,
                               [state_machine_m], message_type=gtk.MESSAGE_QUESTION, parent=self.get_root_window())

        # sm running
        elif not state_machine_execution_engine.finished_or_stopped() and \
                        state_machine_manager.active_state_machine_id == state_machine_m.state_machine.state_machine_id:
            push_sm_running_dialog()
        else:
            self.remove_state_machine(state_machine_m)

    def remove_state_machine(self, state_machine_m):
        """

        :param state_machine_m: The selected state machine model.
        """
        sm_id = get_state_machine_id(state_machine_m)

        copy_of_last_opened_state_machines = copy.deepcopy(self.last_opened_state_machines)

        # the following statement will switch the selected notebook tab automatically and the history of the
        # last opened state machines will be destroyed
        # Close tab and remove info
        page_id = self.get_page_num(sm_id)
        self.view.notebook.remove_page(page_id)
        del self.tabs[sm_id]
        self.remove_controller(sm_id)
        self.last_opened_state_machines = copy_of_last_opened_state_machines

        # self.model is the state_machine_manager_model
        # if the state_machine is removed by a core function the state_machine_editor listens to this event, closes
        # the sm-tab and calls this function; in this case do not remove the state machine from the core smm again!
        if sm_id in self.model.state_machine_manager.state_machines:
            self.model.state_machine_manager.remove_state_machine(sm_id)

        # Open tab with next state machine
        sm_keys = self.model.state_machine_manager.state_machines.keys()

        if len(sm_keys) > 0:
            sm_id = -1
            while sm_id not in sm_keys:
                if len(self.last_opened_state_machines) > 0:
                    sm_id = self.last_opened_state_machines.pop()
                else:
                    sm_id = self.model.state_machine_manager.state_machines[sm_keys[0]].state_machine_id

            self.model.selected_state_machine_id = sm_id
        else:
            self.model.selected_state_machine_id = None

    def close_all_pages(self):
        """Closes all tabs of the state machines editor."""
        state_machine_m_list = []
        for tab in self.tabs.itervalues():
            state_machine_m_list.append(tab['state_machine_m'])
        for state_machine_m in state_machine_m_list:
            self.on_close_clicked(None, state_machine_m, None, force=True)

    def highlight_execution_of_currently_active_sm(self, active):
        """
        High light active state machine. Please consider the difference between active and selected state machine.
        :param active: a flag if the state machine has to be shown as running
        :return:
        """

        notebook = self.view['notebook']
        active_state_machine_id = self.state_machine_manager_model.state_machine_manager.active_state_machine_id
        if active_state_machine_id is None:
            return
        else:
            page = self.get_page_for_state_machine_id(active_state_machine_id)
            if page is None:
                # logger.warning("No state machine open {0}".format(page_num))
                return

        label = notebook.get_tab_label(page).get_children()[0]
        if active:
            draw_for_all_gtk_states(label,
                                    "modify_fg",
                                    gtk.gdk.color_parse(global_gui_config.colors['STATE_MACHINE_ACTIVE']))
        else:
            draw_for_all_gtk_states(label,
                                    "modify_fg",
                                    gtk.gdk.color_parse(global_gui_config.colors['STATE_MACHINE_NOT_ACTIVE']))