import bpy
from node_s import *

class VectorsOutNode(Node, SverchCustomTreeNode):
    ''' Vectors out '''
    bl_idname = 'VectorsOutNode'
    bl_label = 'Vectors out'
    bl_icon = 'OUTLINER_OB_EMPTY'
    
    def init(self, context):
        self.inputs.new('VerticesSocket', "Vectors", "Vectors")
        self.outputs.new('StringsSocket', "X", "X")
        self.outputs.new('StringsSocket', "Y", "Y")
        self.outputs.new('StringsSocket', "Z", "Z")
        
        

    def update(self):
        # inputs
        if 'Vectors' in self.inputs and len(self.inputs['Vectors'].links)>0 and \
                type(self.inputs['Vectors'].links[0].from_socket) == VerticesSocket:
            if not self.inputs['Vectors'].node.socket_value_update:
                self.inputs['Vectors'].node.update()
            xyz = eval(self.inputs['Vectors'].links[0].from_socket.VerticesProperty)
            print (xyz)
            data = dataCorrect(xyz)
            X, Y, Z = [], [], []
            for item in data:
                Z.append(item[2])
                Y.append(item[1])
                X.append(item[0])
            
            print ('data input vector out is ' + data)
            
        # outputs
        if 'X' in self.outputs and len(self.outputs['X'].links)>0 and \
            type(self.outputs['X'].links[0].from_socket) == StringsSocket:
            if not self.outputs['X'].node.socket_value_update:
                self.outputs['X'].node.update()
            self.outputs['X'].links[0].from_socket.StringsProperty = str(X)
        else:
            X = [0.0]
        
        if 'Y' in self.outputs and len(self.outputs['Y'].links)>0 and \
            type(self.outputs['Y'].links[0].from_socket) == StringsSocket:
            if not self.outputs['Y'].node.socket_value_update:
                self.outputs['Y'].node.update()
            self.outputs['Y'].links[0].from_socket.StringsProperty = str(Y)
        else:
            Y = [0.0]
            
        if 'Z' in self.outputs and len(self.outputs['Z'].links)>0 and \
            type(self.outputs['Z'].links[0].from_socket) == StringsSocket:
            if not self.outputs['Z'].node.socket_value_update:
                self.outputs['Z'].node.update()
            self.outputs['Z'].links[0].from_socket.StringsProperty = str(Z)
        else:
            Z = [0.0]
            
    def fullList(self, l, count):
        d = count - len(l)
        if d > 0:
            l.extend([l[-1] for a in range(d)])
        return
                
    def update_socket(self, context):
        self.update()


    

def register():
    bpy.utils.register_class(VectorsOutNode)
    
def unregister():
    bpy.utils.unregister_class(VectorsOutNode)

if __name__ == "__main__":
    register()