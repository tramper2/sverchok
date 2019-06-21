# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


import bpy

from sverchok.node_tree import SverchCustomTreeNode


class SvThreeDPanelParameterSet(bpy.types.Node, SverchCustomTreeNode):

    bl_idname = 'SvThreeDPanelParameterSet'
    bl_label = '3D panel set'
    bl_icon = 'LOGIC'

    set_name = bpy.props.StringProperty(default='Set1')
    show = bpy.props.BoolProperty(default=True)

    def sv_init(self, context):
        self.outputs.new('StringsSocket', 'param_set').link_limit = 1
        self.inputs.new('StringsSocket', 'param_set').link_limit = 100
        self.inputs.new('StringsSocket', 'param').link_limit = 100

    def draw_buttons(self, context, layout):
        layout.prop(self, 'set_name', text='')

    def draw_buttons_3dpanel(self, layout):
        if self.outputs[0].is_linked:
            return
        row = layout.row()
        row.prop(self, 'show', text=self.set_name, icon='DISCLOSURE_TRI_DOWN' if self.show else 'DISCLOSURE_TRI_RIGHT')
        if self.show:
            row = layout.row()
            row.label(text='', icon='BLANK1')
            col = row.column(align=True)
            if self.inputs['param_set'].is_linked:
                for link in self.inputs['param_set'].links:
                    if link.from_node.bl_idname == 'SvThreeDPanelParameterSet':
                        link.from_node.draw_buttons_3dpanel(col)
            if self.inputs['param'].is_linked:
                for link in self.inputs['param'].links:
                    if link.from_node.bl_idname == 'SvNumberNode':
                        col.prop(link.from_node,
                                          'float_' if link.from_node.selected_mode == 'float' else 'int_',
                                          text=link.from_node.name)


classes = [SvThreeDPanelParameterSet]


def register():
    [bpy.utils.register_class(cl) for cl in classes]


def unregister():
    [bpy.utils.unregister_class(cl) for cl in classes[::-1]]
