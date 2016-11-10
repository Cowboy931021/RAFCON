import gtk
from enum import Enum

from rafcon.mvc.utils import constants


class ButtonDialog(Enum):
    __order__ = "OPTION_1 OPTION_2 OPTION_3 OPTION_4 OPTION_5"
    OPTION_1 = 1
    OPTION_2 = 2
    OPTION_3 = 3
    OPTION_4 = 4
    OPTION_5 = 5


class RAFCONDialog(gtk.MessageDialog):

    def __init__(self, type=gtk.MESSAGE_INFO, buttons=gtk.BUTTONS_NONE, flags=gtk.DIALOG_MODAL, parent=None):
        super(RAFCONDialog, self).__init__(type=type, buttons=buttons, flags=flags)

        # Prevent dialog window from being hidden by the main window
        if parent:
            self.set_transient_for(parent)

    def set_markup(self, markup_text):
        from cgi import escape
        super(RAFCONDialog, self).set_markup(escape(markup_text))

    def finalize(self, callback, *args):
        self.connect('response', callback, *args)

        # Use HBox instead of ButtonBox to align buttons within the action area
        button_box = self.get_action_area()
        vbox = button_box.get_parent()
        hbox = gtk.HBox(homogeneous=False, spacing=constants.GRID_SIZE)
        buttons = [button for button in button_box.get_children()]
        for button in buttons:
            button_box.remove(button)
            button.set_relief(gtk.RELIEF_NORMAL)
            hbox.pack_end(button)
        vbox.remove(button_box)
        align_action_area = gtk.Alignment(xalign=1, yalign=0.0, xscale=0.0, yscale=0.0)
        align_action_area.add(hbox)
        vbox.pack_end(align_action_area)
        align_action_area.show()
        hbox.show()
        self.show()


class RAFCONButtonDialog(RAFCONDialog):
    def __init__(self, markup_text, button_texts, callback, callback_args=(), type=gtk.MESSAGE_INFO, parent=None,
                 width=None):
        super(RAFCONButtonDialog, self).__init__(type, gtk.BUTTONS_NONE, gtk.DIALOG_MODAL, parent)
        if isinstance(width, int):
            hbox = self.get_action_area()
            vbox = hbox.parent
            msg_ctr = vbox.get_children()[0]
            text_ctr = msg_ctr.get_children()[1]
            text_ctr.get_children()[0].set_size_request(width, -1)
            text_ctr.get_children()[1].set_size_request(width, -1)
        self.set_markup(markup_text)
        for button_text, option in zip(button_texts, ButtonDialog):
            self.add_button(button_text, option.value)
        self.finalize(callback, *callback_args)
        self.grab_focus()
        self.run()


class RAFCONTextInput(gtk.Dialog):

    def __init__(self, content=''):
        super(RAFCONTextInput, self).__init__()
        self.content = content
        self.entry = None
        self.setup()

    def return_text(self):
        return self.entry.get_text()

    def setup(self):

        self.entry = gtk.Entry()

        self.entry.set_max_length(60)
        self.entry.set_text(self.content)
        self.entry.set_editable(1)
        self.entry.select_region(0, len(self.entry.get_text()))

        self.add_action_widget(self.entry, 0)
        self.entry.show()

        self.show()
        return

