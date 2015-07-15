from weakref import ref

from awesome_tool.mvc.views.gap.constraint import KeepRelativePositionConstraint, KeepPortDistanceConstraint
from awesome_tool.mvc.views.gap.line import PerpLine

from awesome_tool.mvc.models.transition import TransitionModel
from awesome_tool.mvc.models.data_flow import DataFlowModel

from awesome_tool.mvc.views.gap.ports import PortView, ScopedVariablePortView

from awesome_tool.mvc.controllers.gap.enums import SnappedSide

from awesome_tool.utils import constants

from awesome_tool.mvc.controllers.gap import gap_draw_helper

from gtkmvc import Observer

import cairo
from pango import FontDescription, SCALE
from gtk.gdk import Color, CairoContext


class ConnectionView(PerpLine):

    def set_port_for_handle(self, port, handle):
        if handle is self.from_handle():
            self.from_port = port
        elif handle is self.to_handle():
            self.to_port = port

    def reset_port_for_handle(self, handle):
        if handle is self.from_handle():
            self.reset_from_port()
        elif handle is self.to_handle():
            self.reset_to_port()

    def remove_connection_from_port(self, port):
        if self._from_port and port is self._from_port:
            self._from_port.remove_connected_handle(self._from_handle)
        elif self._to_port and port is self._to_port:
            self._to_port.remove_connected_handle(self._to_handle)

    def remove_connection_from_ports(self):
        if self._from_port:
            self._from_port.remove_connected_handle(self._from_handle)
            self._from_port.tmp_disconnect()
        if self._to_port:
            self._to_port.remove_connected_handle(self._to_handle)
            self.to_port.tmp_disconnect()


class ConnectionPlaceholderView(ConnectionView):

    def __init__(self, hierarchy_level, transition_placeholder):
        super(ConnectionPlaceholderView, self).__init__(hierarchy_level)
        self.line_width = .5 / hierarchy_level

        self.transition_placeholder = transition_placeholder

        if transition_placeholder:
            self._line_color = '#81848b'
            self._arrow_color = '#ffffff'
        else:
            self._line_color = '#6c5e3c'
            self._arrow_color = '#ffC926'


class TransitionView(ConnectionView):

    def __init__(self, transition_m, hierarchy_level):
        super(TransitionView, self).__init__(hierarchy_level)
        self._transition_m = None
        self.model = transition_m
        self.line_width = .5 / hierarchy_level

        self._line_color = '#81848b'
        self._arrow_color = '#ffffff'

    @property
    def model(self):
        return self._transition_m()

    @model.setter
    def model(self, transition_model):
        assert isinstance(transition_model, TransitionModel)
        self._transition_m = ref(transition_model)


class DataFlowView(ConnectionView):

    def __init__(self, data_flow_m, hierarchy_level):
        super(DataFlowView, self).__init__(hierarchy_level)
        assert isinstance(data_flow_m, DataFlowModel)
        self._data_flow_m = None
        self.model = data_flow_m
        self.line_width = .5 / hierarchy_level

        self._line_color = '#6c5e3c'
        self._arrow_color = '#ffC926'

    @property
    def model(self):
        return self._data_flow_m()

    @model.setter
    def model(self, data_flow_m):
        assert isinstance(data_flow_m, DataFlowModel)
        self._data_flow_m = ref(data_flow_m)


class ScopedVariableDataFlowView(DataFlowView, Observer):

    def __init__(self, data_flow_m, hierarchy_level, name):
        Observer.__init__(self)
        super(ScopedVariableDataFlowView, self).__init__(data_flow_m, hierarchy_level)

        self._name_width = 10.
        self._name_width_updated = False

        self._print_side = SnappedSide.LEFT
        self._label_selection_waypoint = None

        self._name = None
        self.name = name

    @property
    def from_port(self):
        return self._from_port

    @property
    def to_port(self):
        return self._to_port

    @from_port.setter
    def from_port(self, port):
        assert isinstance(port, PortView)
        self._from_port = port
        self.observe_model(port)
        self._head_length = port.port_side_size
        if not self._from_waypoint:
            self._from_waypoint = self.add_perp_waypoint()
            self._from_port_constraint = KeepPortDistanceConstraint(self.from_handle().pos, self._from_waypoint.pos,
                                                                    port, self._head_length, self.is_out_port(port))
            self.canvas.solver.add_constraint(self._from_port_constraint)
        if self.to_port:
            self.line_width = min(self.to_port.port_side_size, port.port_side_size) * .2
        else:
            self.line_width = port.port_side_size * .2

    @to_port.setter
    def to_port(self, port):
        assert isinstance(port, PortView)
        self._to_port = port
        self.observe_model(port)
        self._to_head_length = port.port_side_size
        if not self._to_waypoint:
            self._to_waypoint = self.add_perp_waypoint(begin=False)
            self._to_port_constraint = KeepPortDistanceConstraint(self.to_handle().pos, self._to_waypoint.pos,
                                                                  port, 2 * self._to_head_length, self.is_in_port(port))
            self.canvas.solver.add_constraint(self._to_port_constraint)
        if self.from_port:
            self.line_width = min(self.from_port.port_side_size, port.port_side_size) * .2

    def reset_from_port(self):
        self.relieve_model(self.from_port)
        super(ScopedVariableDataFlowView, self).reset_from_port()

    def reset_to_port(self):
        self.relieve_model(self.to_port)
        super(ScopedVariableDataFlowView, self).reset_to_port()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        assert isinstance(name, str)
        self._name = name
        
    @property
    def connected(self):
        raise NotImplementedError

    @property
    def desired_name_height(self):
        if self.from_port:
            return self._head_length * 2.5
        else:
            return self._head_length * 1.5

    def draw(self, context):
        if not self.connected:
            super(ScopedVariableDataFlowView, self).draw(context)
        else:
            self._draw_label(context)

    def _draw_label(self, context):
        raise NotImplementedError


class FromScopedVariableDataFlowView(ScopedVariableDataFlowView):

    def __init__(self, data_flow_m, hierarchy_level, name):
        super(FromScopedVariableDataFlowView, self).__init__(data_flow_m, hierarchy_level, name)

    @property
    def connected(self):
        return self._from_port is not None

    @property
    def from_port(self):
        return self._from_port

    @property
    def desired_name_height(self):
        if self.to_port:
            return self._to_head_length * 2.5
        else:
            return self._to_head_length * 1.5

    @from_port.setter
    def from_port(self, port):
        # TODO: change ScopedDataInputPortView to port type of scoped variable in state border
        if isinstance(port, ScopedVariablePortView):
            self._from_port = port
            self._head_length = port.port_side_size
            if not self._from_waypoint:
                self._from_waypoint = self.add_perp_waypoint()
                self._from_port_constraint = KeepPortDistanceConstraint(self.from_handle().pos, self._from_waypoint.pos,
                                                                        port, self._head_length, self.is_out_port(port))
                self.canvas.solver.add_constraint(self._from_port_constraint)
            if self.to_port:
                self.line_width = min(self.to_port.port_side_size, port.port_side_size) * .2
            else:
                self.line_width = port.port_side_size * .2

            self._name = port.model.scoped_variable.name
            if len(self.handles()) == 4:
                self._update_label_selection_waypoint(True)
                # self.add_waypoint((self.to_handle().x + 2 * self._head_length + self._name_width, self.to_handle().y))

    @Observer.observe('side', assign=True)
    def _to_port_changed_side(self, model, prop_name, info):
        self._update_label_selection_waypoint(True)

    def _update_label_selection_waypoint(self, side_changed=False):
        if not self._name_width_updated or side_changed:
            if not side_changed:
                self._name_width_updated = True
            if len(self._handles) == 5:
                self._handles.remove(self._handles[2])
                self._update_ports()
            pos_x = 0.
            pos_y = 0.
            if self.to_port.side is SnappedSide.LEFT:
                pos_x = self.to_handle().x - 2 * self._to_head_length - self._name_width
                pos_y = self.to_handle().y
            elif self.to_port.side is SnappedSide.RIGHT:
                pos_x = self.to_handle().x + 2 * self._to_head_length + self._name_width
                pos_y = self.to_handle().y
            elif self.to_port.side is SnappedSide.TOP:
                pos_x = self.to_handle().x
                pos_y = self.to_handle().y - 2 * self._to_head_length - self._name_width
            elif self.to_port.side is SnappedSide.BOTTOM:
                pos_x = self.to_handle().x
                pos_y = self.to_handle().y + 2 * self._to_head_length + self._name_width
            self.add_waypoint((pos_x, pos_y))

    def add_waypoint(self, pos):
        handle = self._create_handle(pos)
        self._handles.insert(2, handle)
        self._keep_distance_to_port(handle)
        self._update_ports()
        self._label_selection_waypoint = handle

    def _keep_distance_to_port(self, handle):
        canvas = self.canvas
        solver = canvas.solver
        constraint = KeepRelativePositionConstraint(self.to_handle().pos, handle.pos)
        solver.add_constraint(constraint)

    def reset_from_port(self):
        super(FromScopedVariableDataFlowView, self).reset_from_port()
        if len(self._handles) == 4:
            self._handles.remove(self._label_selection_waypoint)
            self._label_selection_waypoint = None
            self._update_ports()

    def _draw_label(self, context):
        if self.parent and self.parent.moving:
            return

        c = context.cairo
        c.set_line_width(self._head_length * .03)

        handle_pos = self.to_handle().pos
        port_side_size = self._to_head_length

        c.set_source_color(Color('#ffbf00'))

        # Ensure that we have CairoContext anf not CairoBoundingBoxContext (needed for pango)
        if isinstance(c, CairoContext):
            cc = c
        else:
            cc = c._cairo

        pcc = CairoContext(cc)
        pcc.set_antialias(cairo.ANTIALIAS_SUBPIXEL)

        scoped_layout = pcc.create_layout()
        port_layout = None

        has_to_port = False
        if self.to_port:
            self._print_side = self.to_port.side
            has_to_port = True
            port_layout = pcc.create_layout()
            port_layout.set_text(self.to_port.name)
        scoped_layout.set_text(self.name)

        font_name = constants.FONT_NAMES[0]
        font_size = 20

        def set_font_description(layout):
            font = FontDescription(font_name + " " + str(font_size))
            layout.set_font_description(font)

        if port_layout:
            set_font_description(scoped_layout)
            while scoped_layout.get_size()[1] / float(SCALE) > self.desired_name_height / 2.:
                font_size *= 0.9
                set_font_description(scoped_layout)
            scoped_name_size = scoped_layout.get_size()[0] / float(SCALE), scoped_layout.get_size()[1] / float(SCALE)

            set_font_description(port_layout)
            while port_layout.get_size()[1] / float(SCALE) > self.desired_name_height / 2.:
                font_size *= 0.9
                set_font_description(port_layout)
            port_name_size = port_layout.get_size()[0] / float(SCALE), port_layout.get_size()[1] / float(SCALE)
            name_size = max(scoped_name_size[0], port_name_size[0]), scoped_name_size[1] + port_name_size[1]
        else:
            set_font_description(scoped_layout)
            while scoped_layout.get_size()[1] / float(SCALE) > self.desired_name_height:
                font_size *= 0.9
                set_font_description(scoped_layout)
            scoped_name_size = scoped_layout.get_size()[0] / float(SCALE), scoped_layout.get_size()[1] / float(SCALE)
            name_size = scoped_name_size

        self._name_width = name_size[0]
        self._update_label_selection_waypoint()

        if not has_to_port:
            rot_angle, move_x, move_y = gap_draw_helper.draw_name_label(context, '#ffbf00', name_size, handle_pos,
                                                                        self._print_side, port_side_size)
        else:
            rot_angle, move_x, move_y = gap_draw_helper.draw_connected_scoped_label(context, '#ffbf00', name_size,
                                                                                    handle_pos, self._print_side,
                                                                                    port_side_size)

        c.move_to(move_x, move_y)
        if self.to_port:
            c.set_source_color(Color("#3c414b"))
        else:
            c.set_source_color(Color("#ffbf00"))

        pcc.update_layout(scoped_layout)
        pcc.rotate(rot_angle)
        pcc.show_layout(scoped_layout)
        pcc.rotate(-rot_angle)

        if port_layout:
            if self._print_side is SnappedSide.RIGHT or self._print_side is SnappedSide.LEFT:
                c.move_to(move_x, move_y + scoped_name_size[1])
            elif self._print_side is SnappedSide.BOTTOM:
                c.move_to(move_x - scoped_name_size[1], move_y)
            elif self._print_side is SnappedSide.TOP:
                c.move_to(move_x + scoped_name_size[1], move_y)
            c.set_source_color(Color("#ffbf00"))

            pcc.update_layout(port_layout)
            pcc.rotate(rot_angle)
            pcc.show_layout(port_layout)
            pcc.rotate(-rot_angle)


class ToScopedVariableDataFlowView(ScopedVariableDataFlowView):

    def __init__(self, data_flow_m, hierarchy_level, name):
        super(ToScopedVariableDataFlowView, self).__init__(data_flow_m, hierarchy_level, name)

    @property
    def connected(self):
        return self._to_port is not None

    @property
    def to_port(self):
        return self._to_port

    @to_port.setter
    def to_port(self, port):
        if isinstance(port, ScopedVariablePortView):
            self._to_port = port
            self._to_head_length = port.port_side_size
            if not self._to_waypoint:
                self._to_waypoint = self.add_perp_waypoint(begin=False)
                self._to_port_constraint = KeepPortDistanceConstraint(self.to_handle().pos, self._to_waypoint.pos,
                                                                      port, 2 * self._to_head_length, self.is_in_port(port))
                self.canvas.solver.add_constraint(self._to_port_constraint)
            if self.from_port:
                self.line_width = min(self.from_port.port_side_size, port.port_side_size) * .2
            self._name = port.model.scoped_variable.name
            if len(self.handles()) == 4:
                self._update_label_selection_waypoint(True)
                # self.add_waypoint((self.from_handle().x + 2 * self._head_length + self._name_width, self.from_handle().y))

    @Observer.observe('side', assign=True)
    def _from_port_changed_side(self, model, prop_name, info):
        self._update_label_selection_waypoint(True)

    def _update_label_selection_waypoint(self, side_changed=False):
        if not self._name_width_updated or side_changed:
            if not side_changed:
                self._name_width_updated = True
            if len(self._handles) == 5:
                self._handles.remove(self._handles[2])
                self._update_ports()
            pos_x = 0.
            pos_y = 0.
            if self.from_port.side is SnappedSide.LEFT:
                pos_x = self.from_handle().x - 2 * self._head_length - self._name_width
                pos_y = self.from_handle().y
            elif self.from_port.side is SnappedSide.RIGHT:
                pos_x = self.from_handle().x + 2 * self._head_length + self._name_width
                pos_y = self.from_handle().y
            elif self.from_port.side is SnappedSide.TOP:
                pos_x = self.from_handle().x
                pos_y = self.from_handle().y - 2 * self._head_length - self._name_width
            elif self.from_port.side is SnappedSide.BOTTOM:
                pos_x = self.from_handle().x
                pos_y = self.from_handle().y + 2 * self._head_length + self._name_width
            self.add_waypoint((pos_x, pos_y))

    def add_waypoint(self, pos):
        handle = self._create_handle(pos)
        self._handles.insert(2, handle)
        self._keep_distance_to_port(handle)
        self._update_ports()
        self._label_selection_waypoint = handle

    def _keep_distance_to_port(self, handle):
        canvas = self.canvas
        solver = canvas.solver
        constraint = KeepRelativePositionConstraint(self.from_handle().pos, handle.pos)
        solver.add_constraint(constraint)

    def reset_to_port(self):
        super(ToScopedVariableDataFlowView, self).reset_to_port()
        if len(self._handles) == 4:
            self._handles.remove(self._label_selection_waypoint)
            self._label_selection_waypoint = None
            self._update_ports()

    def _draw_label(self, context):
        if self.parent and self.parent.moving:
            return

        c = context.cairo
        c.set_line_width(self._head_length * .03)

        handle_pos = self.from_handle().pos
        port_side_size = self._head_length

        c.set_source_color(Color('#ffbf00'))

        # Ensure that we have CairoContext anf not CairoBoundingBoxContext (needed for pango)
        if isinstance(c, CairoContext):
            cc = c
        else:
            cc = c._cairo

        pcc = CairoContext(cc)
        pcc.set_antialias(cairo.ANTIALIAS_SUBPIXEL)

        scoped_layout = pcc.create_layout()
        port_layout = None

        has_from_port = False
        if self.from_port:
            self._print_side = self.from_port.side
            has_from_port = True
            port_layout = pcc.create_layout()
            port_layout.set_text(self.from_port.name)
        scoped_layout.set_text(self.name)

        font_name = constants.FONT_NAMES[0]
        font_size = 20

        def set_font_description(layout):
            font = FontDescription(font_name + " " + str(font_size))
            layout.set_font_description(font)

        if port_layout:
            set_font_description(scoped_layout)
            while scoped_layout.get_size()[1] / float(SCALE) > self.desired_name_height / 2.:
                font_size *= 0.9
                set_font_description(scoped_layout)
            scoped_name_size = scoped_layout.get_size()[0] / float(SCALE), scoped_layout.get_size()[1] / float(SCALE)

            set_font_description(port_layout)
            while port_layout.get_size()[1] / float(SCALE) > self.desired_name_height / 2.:
                font_size *= 0.9
                set_font_description(port_layout)
            port_name_size = port_layout.get_size()[0] / float(SCALE), port_layout.get_size()[1] / float(SCALE)
            name_size = max(scoped_name_size[0], port_name_size[0]), scoped_name_size[1] + port_name_size[1]
        else:
            set_font_description(scoped_layout)
            while scoped_layout.get_size()[1] / float(SCALE) > self.desired_name_height:
                font_size *= 0.9
                set_font_description(scoped_layout)
            scoped_name_size = scoped_layout.get_size()[0] / float(SCALE), scoped_layout.get_size()[1] / float(SCALE)
            name_size = scoped_name_size

        self._name_width = name_size[0]
        self._update_label_selection_waypoint()

        if not has_from_port:
            rot_angle, move_x, move_y = gap_draw_helper.draw_name_label(context, '#ffbf00', name_size, handle_pos,
                                                                        self._print_side, port_side_size)
        else:
            rot_angle, move_x, move_y = gap_draw_helper.draw_connected_scoped_label(context, '#ffbf00', name_size,
                                                                                    handle_pos, self._print_side,
                                                                                    port_side_size)

        c.move_to(move_x, move_y)
        if self.from_port:
            c.set_source_color(Color("#3c414b"))
        else:
            c.set_source_color(Color("#ffbf00"))

        pcc.update_layout(scoped_layout)
        pcc.rotate(rot_angle)
        pcc.show_layout(scoped_layout)
        pcc.rotate(-rot_angle)

        if port_layout:
            if self._print_side is SnappedSide.RIGHT or self._print_side is SnappedSide.LEFT:
                c.move_to(move_x, move_y + scoped_name_size[1])
            elif self._print_side is SnappedSide.BOTTOM:
                c.move_to(move_x - scoped_name_size[1], move_y)
            elif self._print_side is SnappedSide.TOP:
                c.move_to(move_x + scoped_name_size[1], move_y)
            c.set_source_color(Color("#ffbf00"))

            pcc.update_layout(port_layout)
            pcc.rotate(rot_angle)
            pcc.show_layout(port_layout)
            pcc.rotate(-rot_angle)