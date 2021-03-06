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
from contextlib import contextmanager
from functools import wraps
from math import radians, ceil
import itertools
import ast
import copy
from itertools import zip_longest
import bpy
from mathutils import Vector, Matrix
from numpy import (
    array as np_array,
    newaxis as np_newaxis,
    ndarray,
    repeat as np_repeat,
    concatenate as np_concatenate,
    tile as np_tile,
    float64,
    int32, int64)
from sverchok.utils.logging import info
from sverchok.core.events import CurrentEvents, BlenderEventsTypes

DEBUG_MODE = False
HEAT_MAP = False
RELOAD_EVENT = False

# this is set correctly later.
SVERCHOK_NAME = "sverchok"

cache_viewer_baker = {}

sentinel = object()



#####################################################
################### cache magic #####################
#####################################################

#handle for object in node and neuro node
temp_handle = {}

def handle_delete(handle):
    if handle in temp_handle:
        del temp_handle[handle]

def handle_read(handle):
    if not (handle in temp_handle):
        return (False, [])
    return (True, temp_handle[handle]['prop'])

def handle_write(handle, prop):
    handle_delete(handle)

    temp_handle[handle] = {"prop" : prop}

def handle_check(handle, prop):
    if handle in handle_check and \
            prop == handle_check[handle]['prop']:
        return True
    return False


#####################################################
################ list matching magic ################
#####################################################


def repeat_last(lst):
    """
    creates an infinite iterator the first each element in lst
    and then keep repeating the last element,
    use with terminating input
    """
    i = -1
    while lst:
        i += 1
        if len(lst) > i:
            yield lst[i]
        else:
            yield lst[-1]


def match_long_repeat(lsts):
    """return matched list, using the last value to fill lists as needed
    longest list matching [[1,2,3,4,5], [10,11]] -> [[1,2,3,4,5], [10,11,11,11,11]]
    """
    max_l = 0
    tmp = []
    for l in lsts:
        max_l = max(max_l, len(l))
    for l in lsts:
        if len(l) == max_l:
            tmp.append(l)
        else:
            tmp.append(repeat_last(l))
    return list(map(list, zip(*zip(*tmp))))

def zip_long_repeat(*lists):
    objects = match_long_repeat(lists)
    return zip(*objects)

def match_long_cycle(lsts):
    """return matched list, cycling the shorter lists
    longest list matching, cycle [[1,2,3,4,5] ,[10,11]] -> [[1,2,3,4,5] ,[10,11,10,11,10]]
    """
    max_l = 0
    tmp = []
    for l in lsts:
        max_l = max(max_l, len(l))
    for l in lsts:
        if len(l) == max_l:
            tmp.append(l)
        else:
            tmp.append(itertools.cycle(l))
    return list(map(list, zip(*zip(*tmp))))


# when you intent to use lenght of first list to control WHILE loop duration
# and you do not want to change the length of the first list, but you want the second list
# lenght to by not less than the length of the first
def second_as_first_cycle(F, S):
    if len(F) > len(S):
        return list(map(list, zip(*zip(*[F, itertools.cycle(S)]))))[1]
    else:
        return S

def match_cross(lsts):
    """ return cross matched lists
    [[1,2], [5,6,7]] -> [[1,1,1,2,2,2], [5,6,7,5,6,7]]
    """
    return list(map(list, zip(*itertools.product(*lsts))))


def match_cross2(lsts):
    """ return cross matched lists
    [[1,2], [5,6,7]] ->[[1, 2, 1, 2, 1, 2], [5, 5, 6, 6, 7, 7]]
    """
    return list(reversed(list(map(list, zip(*itertools.product(*reversed(lsts)))))))


# Shortest list decides output length [[1,2,3,4,5], [10,11]] -> [[1,2], [10, 11]]
def match_short(lsts):
    """return lists of equal length using the Shortest list to decides length
    Shortest list decides output length [[1,2,3,4,5], [10,11]] -> [[1,2], [10, 11]]
    """
    return list(map(list, zip(*zip(*lsts))))


def fullList(l, count):
    """extends list l so len is at least count if needed with the
    last element of l"""
    n = len(l)
    if n == count:
        return
    d = count - n
    if d > 0:
        l.extend([l[-1] for a in range(d)])
    return

def fullList_np(l, count):
    """extends list l so len is at least count if needed with the
    last element of l"""
    n = len(l)
    if n == count:
        return
    d = count - n
    if d > 0:
        try:
            l.extend([l[-1] for a in range(d)])
        except:
            l = numpy_full_list(l, n)
    else:
        l = l[:count]


def fullList_deep_copy(l, count):
    """the same that full list function but
    it have correct work with objects such as lists."""
    d = count - len(l)
    if d > 0:
        l.extend([copy.deepcopy(l[-1]) for _ in range(d)])
    return

def cycle_for_length(lst, count):
    result = []
    n = len(lst)
    for i in range(count):
        result.append(lst[i % n])
    return result

def repeat_last_for_length(lst, count, deepcopy=False):
    """
    Repeat last item of the list enough times
    for result's length to be equal to `count`.

    repeat_last_for_length(None, n) = None
    repeat_last_for_length([], n) = []
    repeat_last_for_length([1,2], 4) = [1, 2, 2, 2]
    """
    if not lst or len(lst) >= count:
        return lst
    n = len(lst)
    x = lst[-1]
    result = lst[:]
    for i in range(count - n):
        if deepcopy:
            result.append(copy.deepcopy(x))
        else:
            result.append(x)
    return result

def sv_zip(*iterables):
    """zip('ABCD', 'xy') --> Ax By
    like standard zip but list instead of tuple
    """
    iterators = [iter(it) for it in iterables]
    sentinel = object() # use internal sentinel
    while iterators:
        result = []
        for it in iterators:
            elem = next(it, sentinel)
            if elem is sentinel:
                return
            result.append(elem)
        yield result

list_match_modes = [
    ("SHORT",  "Match Short",  "Match shortest List",    1),
    ("CYCLE",  "Cycle",  "Match longest List by cycling",     2),
    ("REPEAT", "Repeat Last", "Match longest List by repeating last item",     3),
    ("XREF",   "X-Ref",  "Cross reference (fast cycle of long)",  4),
    ("XREF2",  "X-Ref 2", "Cross reference (fast cycle of short)",  5),
    ]

list_match_func = {
    "SHORT":  match_short,
    "CYCLE":  match_long_cycle,
    "REPEAT": match_long_repeat,
    "XREF":   match_cross,
    "XREF2":  match_cross2
    }
numpy_list_match_modes =  list_match_modes[:3]
# numpy_list_match_modes = [
#     ("SHORT",  "Match Short",  "Match shortest List",    1),
#     ("CYCLE",  "Cycle",  "Match longest List by cycling",     2),
#     ("REPEAT", "Repeat Last", "Match longest List by repeating last item",     3),
#     ]

def numpy_full_list(array, desired_length):
    '''retuns array with desired length by repeating last item'''
    if not isinstance(array, ndarray):
        array = np_array(array)

    length_diff = desired_length - array.shape[0]

    if length_diff > 0:
        new_part = np_repeat(array[np_newaxis, -1], length_diff, axis=0)
        return np_concatenate((array, new_part))[:desired_length]
    return array[:desired_length]

def numpy_full_list_cycle(array, desired_length):
    '''retuns array with desired length by cycling'''

    length_diff = desired_length - array.shape[0]
    if length_diff > 0:
        if length_diff < array.shape[0]:

            return np_concatenate((array, array[:length_diff]))

        new_part = np_repeat(array, ceil(length_diff / array.shape[0]), axis=0)
        if len(array.shape) > 1:
            shape = (ceil(length_diff / array.shape[0]), 1)
        else:
            shape = ceil(length_diff / array.shape[0])
        new_part = np_tile(array, shape)
        return np_concatenate((array, new_part[:length_diff]))

    return array[:desired_length]

numpy_full_list_func = {
    "SHORT":  lambda x,l: x[:l],
    "CYCLE":  numpy_full_list_cycle,
    "REPEAT": numpy_full_list,
    }

def numpy_match_long_repeat(list_of_arrays):
    '''match numpy arrays length by repeating last one'''
    out = []
    maxl = 0
    for array in list_of_arrays:
        maxl = max(maxl, array.shape[0])
    for array in list_of_arrays:
        length_diff = maxl - array.shape[0]
        if length_diff > 0:
            new_part = np_repeat(array[np_newaxis, -1], length_diff, axis=0)
            array = np_concatenate((array, new_part))
        out.append(array)
    return out

def numpy_match_long_cycle(list_of_arrays):
    '''match numpy arrays length by cycling over the array'''
    out = []
    maxl = 0
    for array in list_of_arrays:
        maxl = max(maxl, array.shape[0])
    for array in list_of_arrays:
        length_diff = maxl - array.shape[0]
        if length_diff > 0:
            if length_diff < array.shape[0]:

                array = np_concatenate((array, array[:length_diff]))
            else:
                new_part = np_repeat(array, ceil(length_diff / array.shape[0]), axis=0)
                if len(array.shape) > 1:
                    shape = (ceil(length_diff / array.shape[0]), 1)
                else:
                    shape = ceil(length_diff / array.shape[0])
                new_part = np_tile(array, shape)
                array = np_concatenate((array, new_part[:length_diff]))
        out.append(array)
    return out

def numpy_match_short(list_of_arrays):
    '''match numpy arrays length by cutting the longer arrays'''
    out = []
    minl = list_of_arrays[0].shape[0]
    for array in list_of_arrays:
        minl = min(minl, array.shape[0])
    for array in list_of_arrays:
        length_diff = array.shape[0] - minl
        if length_diff > 0:
            array = array[:minl]
        out.append(array)
    return out

numpy_list_match_func = {
    "SHORT":  numpy_match_short,
    "CYCLE":  numpy_match_long_cycle,
    "REPEAT": numpy_match_long_repeat,
    }

def make_repeaters(lists):
    chain = itertools.chain
    repeat = itertools.repeat
    out =[]
    for l in lists:
        out.append(chain(l, repeat(l[-1])))

    return out

def make_cyclers(lists):

    cycle = itertools.cycle
    out =[]
    for l in lists:
        out.append(cycle(l))
    return out

iter_list_match_func = {
    "SHORT":  lambda x: x,
    "CYCLE":  make_cyclers,
    "REPEAT": make_repeaters,
    }
#####################################################
################# list levels magic #################
#####################################################

# working with nesting levels
# define data floor
# NOTE, these function cannot possibly work in all scenarios, use with care

def dataCorrect(data, nominal_dept=2):
    """data from nasting to standart: TO container( objects( lists( floats, ), ), )
    """
    dept = levelsOflist(data)
    output = []
    if not dept: # for empty lists
        return []
    if dept < 2:
        return data #[dept, data]
    else:
        output = dataStandart(data, dept, nominal_dept)
        return output

def dataCorrect_np(data, nominal_dept=2):
    """data from nasting to standart: TO container( objects( lists( floats, ), ), )
    """
    dept = levels_of_list_or_np(data)
    output = []
    if not dept: # for empty lists
        return []
    if dept < 2:
        return data #[dept, data]
    else:
        output = dataStandart(data, dept, nominal_dept)
        return output

def dataSpoil(data, dept):
    """from standart data to initial levels: to nested lists
     container( objects( lists( nested_lists( floats, ), ), ), ) это невозможно!
    """
    __doc__ = 'preparing and making spoil'

    def Spoil(dat, dep):
        __doc__ = 'making spoil'
        out = []
        if dep:
            for d in dat:
                out.append([Spoil(d, dep-1)])
        else:
            out = dat
        return out
    lol = levelsOflist(data)
    if dept > lol:
        out = Spoil(data, dept-lol)
    else:
        out = data
    return out


def dataStandart(data, dept, nominal_dept):
    """data from nasting to standart: TO container( objects( lists( floats, ), ), )"""
    deptl = dept - 1
    output = []
    for object in data:
        if deptl >= nominal_dept:
            output.extend(dataStandart(object, deptl, nominal_dept))
        else:
            output.append(data)
            return output
    return output


def levelsOflist(lst):
    """calc list nesting only in countainment level integer"""
    level = 1
    for n in lst:
        if n and isinstance(n, (list, tuple)):
            level += levelsOflist(n)
        return level
    return 0

def levels_of_list_or_np(lst):
    """calc list nesting only in countainment level integer"""
    level = 1
    for n in lst:
        if isinstance(n, (list, tuple)):
            level += levels_of_list_or_np(n)
        elif isinstance(n, (ndarray)):
            level += len(n.shape)

        return level
    return 0

def get_data_nesting_level(data, data_types=(float, int, float64, int32, int64, str)):
    """
    data: number, or list of numbers, or list of lists, etc.
    data_types: list or tuple of types.

    Detect nesting level of actual data.
    "Actual" data is detected by belonging to one of data_types.
    This method searches only for first instance of "actual data",
    so it does not support cases when different elements of source
    list have different nesting.
    Returns integer.
    Raises an exception if at some point it encounters element
    which is not a tuple, list, or one of data_types.

    get_data_nesting_level(1) == 0
    get_data_nesting_level([]) == 1
    get_data_nesting_level([1]) == 1
    get_data_nesting_level([[(1,2,3)]]) == 3
    """

    def helper(data, recursion_depth):
        """ Needed only for better error reporting. """
        if isinstance(data, data_types):
            return 0
        elif isinstance(data, (list, tuple, ndarray)):
            if len(data) == 0:
                return 1
            else:
                return helper(data[0], recursion_depth+1) + 1
        elif data is None:
            raise TypeError("get_data_nesting_level: encountered None at nesting level {}".format(recursion_depth))
        else:
            raise TypeError("get_data_nesting_level: unexpected type `{}' of element `{}' at nesting level {}".format(type(data), data, recursion_depth))

    return helper(data, 0)

def ensure_nesting_level(data, target_level, data_types=(float, int, int32, int64, float64, str)):
    """
    data: number, or list of numbers, or list of lists, etc.
    target_level: data nesting level required for further processing.
    data_types: list or tuple of types.

    Wraps data in so many [] as required to achieve target nesting level.
    Raises an exception, if data already has too high nesting level.

    ensure_nesting_level(17, 0) == 17
    ensure_nesting_level(17, 1) == [17]
    ensure_nesting_level([17], 1) == [17]
    ensure_nesting_level([17], 2) == [[17]]
    ensure_nesting_level([(1,2,3)], 3) == [[(1,2,3)]]
    ensure_nesting_level([[[17]]], 1) => exception
    """

    current_level = get_data_nesting_level(data, data_types)
    if current_level > target_level:
        raise TypeError("ensure_nesting_level: input data already has nesting level of {}. Required level was {}.".format(current_level, target_level))
    result = data
    for i in range(target_level - current_level):
        result = [result]
    return result

def transpose_list(lst):
    """
    Transpose a list of lists.

    transpose_list([[1,2], [3,4]]) == [[1,3], [2, 4]]
    """
    return list(map(list, zip(*lst)))

# from python 3.5 docs https://docs.python.org/3.5/library/itertools.html recipes
def split_by_count(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return list(map(list, zip_longest(*args, fillvalue=fillvalue)))

def describe_data_shape(data):
    """
    Describe shape of data in human-readable form.
    Returns string.
    Can be used for debugging or for displaying information to user.
    Note: this method inspects only first element of each list/tuple,
    expecting they are all homogenous (that is usually true in Sverchok).

    describe_data_shape(None) == 'Level 0: NoneType'
    describe_data_shape(1) == 'Level 0: int'
    describe_data_shape([]) == 'Level 1: list [0]'
    describe_data_shape([1]) == 'Level 1: list [1] of int'
    describe_data_shape([[(1,2,3)]]) == 'Level 3: list [1] of list [1] of tuple [3] of int'
    """
    def helper(data):
        if not isinstance(data, (list, tuple)):
            if isinstance(data, ndarray):
                return len(data.shape), type(data).__name__ + " of " + str(data.dtype) + " with shape " + str(data.shape)
            return 0, type(data).__name__
        else:
            result = type(data).__name__
            result += " [{}]".format(len(data))
            if len(data) > 0:
                child = data[0]
                child_nesting, child_result = helper(child)
                result += " of " + child_result
            else:
                child_nesting = 0
            return (child_nesting + 1), result

    nesting, result = helper(data)
    return "Level {}: {}".format(nesting, result)

def describe_data_structure(data, data_types=(float, int, int32, int64, float64, str)):
    if isinstance(data, data_types):
        return "*"
    elif isinstance(data, (list, tuple)):
        if isinstance(data[0], data_types):
            return str(len(data)) + "*"
        else:
            rs = []
            for item in data:
                r = describe_data_structure(item, data_types)
                rs.append(str(r))
            rs = str(len(data)) + "[" + ", ".join(rs) + "]"
            return rs
    else:
        raise TypeError(f"Unexpected data type: {type(data)}")

def calc_mask(subset_data, set_data, level=0, negate=False, ignore_order=True):
    """
    Calculate mask: for each item in set_data, return True if it is present in subset_data.
    The function can work at any specified level.

    subset_data: subset, for example [1]
    set_data: set, for example [1, 2, 3]
    level: 0 to check immediate members of set and subset; 1 to work with lists of lists and so on.
    negate: if True, then result will be negated (True if item of set is not present in subset).
    ignore_order: when comparing lists, ignore items order.

    Raises an exception if nesting level of input sets is less than specified level parameter.

    calc_mask([1], [1,2,3]) == [True, False, False])
    calc_mask([1], [1,2,3], negate=True) == [False, True, True]
    """
    if level == 0:
        if not isinstance(subset_data, (tuple, list)):
            raise Exception("Specified level is too high for given Subset")
        if not isinstance(set_data, (tuple, list)):
            raise Exception("Specified level is too high for given Set")

        if ignore_order and get_data_nesting_level(subset_data) > 1:
            if negate:
                return [set(item) not in map(set, subset_data) for item in set_data]
            else:
                return [set(item) in map(set, subset_data) for item in set_data]
        else:
            if negate:
                return [item not in subset_data for item in set_data]
            else:
                return [item in subset_data for item in set_data]
    else:
        sub_objects = match_long_repeat([subset_data, set_data])
        return [calc_mask(subset_item, set_item, level - 1, negate, ignore_order) for subset_item, set_item in zip(*sub_objects)]

def apply_mask(mask, lst):
    good, bad = [], []
    for m, item in zip(mask, lst):
        if m:
            good.append(item)
        else:
            bad.append(item)
    return good, bad

def rotate_list(l, y=1):
    """
    "Rotate" list by shifting it's items towards the end and putting last items to the beginning.
    For example,

    rotate_list([1, 2, 3]) = [2, 3, 1]
    rotate_list([1, 2, 3], y=2) = [3, 1, 2]
    """
    if len(l) == 0:
        return l
    if y == 0:
        return l
    y = y % len(l)
    return list(l[y:]) + list(l[:y])

def partition(p, lst):
    good, bad = [], []
    for item in lst:
        if p(item):
            good.append(item)
        else:
            bad.append(item)
    return good, bad

#####################################################
################### matrix magic ####################
#####################################################

# tools that makes easier to convert data
# from string to matrixes, vertices,
# lists, other and vise versa


def Matrix_listing(prop):
    """Convert Matrix() into Sverchok data"""
    mat_out = []
    for matrix in prop:
        unit = []
        for m in matrix:
            # [Matrix0, Matrix1, ... ]
            unit.append(m[:])
        mat_out.append((unit))
    return mat_out


def Matrix_generate(prop):
    """Generate Matrix() data from Sverchok data"""
    mat_out = []
    for matrix in prop:
        unit = Matrix()
        for k, m in enumerate(matrix):
            # [Matrix0, Matrix1, ... ]
            unit[k] = Vector(m)
        mat_out.append(unit)
    return mat_out


def Matrix_location(prop, to_list=False):
    """return a list of locations represeting the translation of the matrices"""
    Vectors = []
    for p in prop:
        if to_list:
            Vectors.append(p.translation[:])
        else:
            Vectors.append(p.translation)
    return [Vectors]


def Matrix_scale(prop, to_list=False):
    """return a Vector()/list represeting the scale factor of the matrices"""
    Vectors = []
    for p in prop:
        if to_list:
            Vectors.append(p.to_scale()[:])
        else:
            Vectors.append(p.to_scale())
    return [Vectors]


def Matrix_rotation(prop, to_list=False):
    """return (Vector, rotation) utility function for Matrix Destructor.
    if list is true the Vector() is decomposed into tuple format.
    """
    Vectors = []
    for p in prop:
        q = p.to_quaternion()
        if to_list:
            vec, angle = q.to_axis_angle()
            Vectors.append((vec[:], angle))
        else:
            Vectors.append(q.to_axis_angle())
    return [Vectors]


def Vector_generate(prop):
    """return a list of Vector() objects from a standard Sverchok data"""
    return [[Vector(v) for v in obj] for obj in prop]


def Vector_degenerate(prop):
    """return a simple list of values instead of Vector() objects"""
    return [[v[0:3] for v in obj] for obj in prop]


def Edg_pol_generate(prop):
    edg_pol_out = []
    if len(prop[0][0]) == 2:
        e_type = 'edg'
    elif len(prop[0]) > 2:
        e_type = 'pol'
    for ob in prop:
        list_out = []
        for p in ob:
            list_out.append(p)
        edg_pol_out.append(list_out)
    # [ [(n1,n2,n3), (n1,n7,n9), p, p, p, p...], [...],... ] n = vertexindex
    return e_type, edg_pol_out


def matrixdef(orig, loc, scale, rot, angle, vec_angle=[[]]):
    modif = []
    for i, de in enumerate(orig):
        ma = de.copy()

        if loc[0]:
            k = min(len(loc[0])-1, i)
            mat_tran = de.Translation(loc[0][k])
            ma = ma @ mat_tran

        if vec_angle[0] and rot[0]:
            k = min(len(rot[0])-1, i)
            a = min(len(vec_angle[0])-1, i)

            vec_a = vec_angle[0][a].normalized()
            vec_b = rot[0][k].normalized()

            mat_rot = vec_b.rotation_difference(vec_a).to_matrix().to_4x4()
            ma = ma @ mat_rot

        elif rot[0]:
            k = min(len(rot[0])-1, i)
            a = min(len(angle[0])-1, i)
            mat_rot = de.Rotation(radians(angle[0][a]), 4, rot[0][k].normalized())
            ma = ma @ mat_rot

        if scale[0]:
            k = min(len(scale[0])-1, i)
            scale2 = scale[0][k]
            id_m = Matrix.Identity(4)
            for j in range(3):
                id_m[j][j] = scale2[j]
            ma = ma @ id_m

        modif.append(ma)
    return modif


####
#### random stuff
####

def no_space(s):
    return s.replace(' ', '_')

def enum_item(s):
    """return a list usable in enum property from a list with one value"""
    return [(no_space(i), i, "") for i in s]

def enum_item_4(s):
    """return a 4*n list usable in enum property from a list with one value"""
    return [(no_space(n), n, '', i) for i, n in enumerate(s)]

def enum_item_5(s, icons):
    """return a 4*n list usable in enum property from a list with one value"""
    return [(no_space(n), n, '', icon, i) for i, (n, icon) in enumerate(zip(s, icons))]

def sv_lambda(**kwargs):
    """üsage: (like a named tuple)

    structure = sv_lambda(keys=20, color=(1,0,0,0))

    print(structure.keys)
    print(structure.color)

    useful for passing a parameter to a function that expects to be able to do a dot lookup
    on the parameter, for instance a function that normally accepts "self" or "node", but the 
    function only really looks up one or two..etc parameters.
    """ 
    dummy = lambda: None
    for k, v in kwargs.items():
        setattr(dummy, k, v)
    return dummy


class classproperty:
    """https://stackoverflow.com/a/13624858/10032221"""
    def __init__(self, fget):
        self.fget = fget

    def __get__(self, owner_self, owner_cls):
        return self.fget(owner_cls)


#####################################################
############### debug settings magic ################
#####################################################


def sverchok_debug(mode):
    """
    set debug mode to mode
    """
    global DEBUG_MODE
    DEBUG_MODE = mode
    return DEBUG_MODE


def setup_init():
    """
    setup variables needed for sverchok to function
    """
    global DEBUG_MODE
    global HEAT_MAP
    global SVERCHOK_NAME
    import sverchok
    SVERCHOK_NAME = sverchok.__name__
    addon = bpy.context.preferences.addons.get(SVERCHOK_NAME)
    if addon:
        DEBUG_MODE = addon.preferences.show_debug
        HEAT_MAP = addon.preferences.heat_map
    else:
        print("Setup of preferences failed")


#####################################################
###############  heat map system     ################
#####################################################


def heat_map_state(state):
    """
    colors the nodes based on execution time
    """
    global HEAT_MAP
    HEAT_MAP = state
    sv_ng = [ng for ng in bpy.data.node_groups if ng.bl_idname == 'SverchCustomTreeType']
    if state:
        for ng in sv_ng:
            color_data = {node.name: (node.color[:], node.use_custom_color) for node in ng.nodes}
            if not ng.sv_user_colors:
                ng.sv_user_colors = str(color_data)
    else:
        for ng in sv_ng:
            if not ng.sv_user_colors:
                print("{0} has no colors".format(ng.name))
                continue
            color_data = ast.literal_eval(ng.sv_user_colors)
            for name, node in ng.nodes.items():
                if name in color_data:
                    color, use = color_data[name]
                    setattr(node, 'color', color)
                    setattr(node, 'use_custom_color', use)
            ng.sv_user_colors = ""

#####################################################
############### update system magic! ################
#####################################################


def updateNode(self, context):
    """
    When a node has changed state and need to call a partial update.
    For example a user exposed bpy.prop
    """
    CurrentEvents.new_event(BlenderEventsTypes.node_property_update, self)
    self.process_node(context)


def update_with_kwargs(update_function, **kwargs):
    """
    You can wrap property update function for adding extra key arguments to it, like this:

    def update_prop(self, context, extra_arg=None):
        print(extra_arg)

    node_prop_name: bpy.props.BoolProperty(update=update_with_kwargs(update_prop, extra_arg='node_prop_name'))
    """

    # https://docs.python.org/3/library/functools.html#functools.partial
    @wraps(update_function)
    def handel_update_call(node, context):
        update_function(node, context, **handel_update_call.extra_args)

    handel_update_call.extra_args = dict()
    for attr_name, data in kwargs.items():
        handel_update_call.extra_args[attr_name] = data

    return handel_update_call


@contextmanager
def throttle_tree_update(node):
    """ usage
    from sverchok.node_tree import throttle_tree_update

    inside your node, f.ex inside a wrapped_update that creates a socket

    def wrapped_update(self, context):
        with throttle_tree_update(self):
            self.inputs.new(...)
            self.outputs.new(...)

    that's it.

    """
    try:
        node.id_data.skip_tree_update = True
        yield node
    finally:
        node.id_data.skip_tree_update = False


##############################################################
##############################################################
############## changable type of socket magic ################
########### if you have separate socket solution #############
#################### welcome to provide #####################
##############################################################
##############################################################

def changable_sockets(node, inputsocketname, outputsocketname):
    '''
    arguments: node, name of socket to follow, list of socket to change
    '''
    if not inputsocketname in node.inputs:
        # - node not initialized in sv_init yet,
        # - or socketname incorrect
        info(f"changable_socket was called on {node.name} with a socket named {inputsocketname}, this socket does not exist")
        return

    in_socket = node.inputs[inputsocketname]
    ng = node.id_data
    if in_socket.links:
        in_other = get_other_socket(in_socket)
        if not in_other:
            return
        outputs = node.outputs
        s_type = in_other.bl_idname
        if s_type == 'SvDummySocket':
            return #
        if outputs[outputsocketname[0]].bl_idname != s_type:
            node.id_data.freeze(hard=True)
            to_links = {}
            for n in outputsocketname:
                out_socket = outputs[n]
                to_links[n] = [l.to_socket for l in out_socket.links]
                outputs.remove(outputs[n])
            for n in outputsocketname:
                new_out_socket = outputs.new(s_type, n)
                for to_socket in to_links[n]:
                    ng.links.new(to_socket, new_out_socket)
            node.id_data.unfreeze(hard=True)


def replace_socket(socket, new_type, new_name=None, new_pos=None):
    '''
    Replace a socket with a socket of new_type and keep links
    '''

    socket_name = new_name or socket.name
    socket_pos = new_pos or socket.index
    ng = socket.id_data

    ng.freeze()

    if socket.is_output:
        outputs = socket.node.outputs
        to_sockets = [l.to_socket for l in socket.links]

        outputs.remove(socket)
        new_socket = outputs.new(new_type, socket_name)
        outputs.move(len(outputs)-1, socket_pos)

        for to_socket in to_sockets:
            link = ng.links.new(new_socket, to_socket)
            link.is_valid = True

    else:
        inputs = socket.node.inputs
        from_socket = socket.links[0].from_socket if socket.is_linked else None

        inputs.remove(socket)
        new_socket = inputs.new(new_type, socket_name)
        inputs.move(len(inputs)-1, socket_pos)

        if from_socket:
            link = ng.links.new(from_socket, new_socket)
            link.is_valid = True

    ng.unfreeze()

    return new_socket


def get_other_socket(socket):
    """
    Get next real upstream socket.
    This should be expanded to support wifi nodes also.
    Will return None if there isn't a another socket connect
    so no need to check socket.links
    """
    if not socket.is_linked:
        return None
    if not socket.is_output:
        other = socket.links[0].from_socket
    else:
        other = socket.links[0].to_socket

    if other.node.bl_idname == 'NodeReroute':
        if not socket.is_output:
            return get_other_socket(other.node.inputs[0])
        else:
            return get_other_socket(other.node.outputs[0])
    else:  #other.node.bl_idname == 'WifiInputNode':
        return other


###########################################
# Multysocket magic / множественный сокет #
###########################################

#     utility function for handling n-inputs, for usage see Test1.py
#     for examples see ListJoin2, LineConnect, ListZip
#     min parameter sets minimum number of sockets
#     setup two variables in Node class
#     create Fixed inputs socket, the multi socket will not change anything
#     below min
#     base_name = StringProperty(default='Data ')
#     multi_socket_type = StringProperty(default='SvStringsSocket')

# the named argument min will be replaced soonish.

def multi_socket(node, min=1, start=0, breck=False, out_count=None):
    '''
     min - integer, minimal number of sockets, at list 1 needed
     start - integer, starting socket.
     breck - boolean, adding bracket to name of socket x[0] x[1] x[2] etc
     output - integer, deal with output, if>0 counts number of outputs multy sockets
     base name added in separated node in self.base_name = 'some_name', i.e. 'x', 'data'
     node.multi_socket_type - type of socket, as .bl_idname

    '''
    #probably incorrect state due or init or change of inputs
    # do nothing
    ng = node.id_data

    if min < 1:
        min = 1
    if out_count is None:
        if not node.inputs:
            return
        if node.inputs[-1].links:
            length = start + len(node.inputs)
            if breck:
                name = node.base_name + '[' + str(length) + ']'
            else:
                name = node.base_name + str(length)
            node.inputs.new(node.multi_socket_type, name)
        else:
            while len(node.inputs) > min and not node.inputs[-2].links:
                node.inputs.remove(node.inputs[-1])
    elif isinstance(out_count, int):
        lenod = len(node.outputs)
        ng.freeze(True)
        print(out_count)
        if out_count > 30:
            out_count = 30
        if lenod < out_count:
            while len(node.outputs) < out_count:
                length = start + len(node.outputs)
                if breck:
                    name = node.base_name + '[' + str(length)+ ']'
                else:
                    name = node.base_name + str(length)
                node.outputs.new(node.multi_socket_type, name)
        else:
            while len(node.outputs) > out_count:
                node.outputs.remove(node.outputs[-1])
        ng.unfreeze(True)


#####################################
# socket data cache                 #
#####################################


def SvGetSocketAnyType(self, socket, default=None, deepcopy=True):
    """Old interface, don't use"""
    return socket.sv_get(default, deepcopy)


def SvSetSocketAnyType(self, socket_name, out):
    """Old interface, don't use"""

    self.outputs[socket_name].sv_set(out)


def socket_id(socket):
    """return an usable and semi stable hash"""
    return socket.socket_id

def node_id(node):
    """return a stable hash for the lifetime of the node
    needs StringProperty called n_id in the node
    """
    return node.node_id


# EDGE CACHE settings : used to accellerate the (linear) edge list generation
_edgeCache = {}
_edgeCache["main"] = []  # e.g. [[0, 1], [1, 2], ... , [N-1, N]] (extended as needed)


def update_edge_cache(n):
    """
    Extend the edge list cache to contain at least n edges.

    NOTE: This is called by the get_edge_list to make sure the edge cache is large
    enough, but it can also be called preemptively by the nodes prior to making
    multiple calls to get_edge_list in order to pre-augment the cache to a known
    size and thus accellearate the subsequent calls to get_edge_list as they
    will not have to augment the cache with every call.
    """
    m = len(_edgeCache["main"])  # current number of edges in the edge cache
    if n > m: # requested #edges < cached #edges ? => extend the cache
        _edgeCache["main"].extend([[m + i, m + i + 1] for i in range(n - m)])


def get_edge_list(n):
    """
    Get the list of n edges connecting n+1 vertices.

    e.g. [[0, 1], [1, 2], ... , [n-1, n]]

    NOTE: This uses an "edge cache" to accellerate the edge list generation.
    The cache is extended automatically as needed to satisfy the largest number
    of edges within the node tree and it is shared by all nodes using this method.
    """
    update_edge_cache(n) # make sure the edge cache is large enough
    return _edgeCache["main"][:n] # return a subset list of the edge cache


def get_edge_loop(n):
    """
    Get the loop list of n edges connecting n vertices.

    e.g. [[0, 1], [1, 2], ... , [n-2, n-1], [n-1, 0]]

    NOTE: This uses an "edge cache" to accellerate the edge list generation.
    The cache is extended automatically as needed to satisfy the largest number
    of edges within the node tree and it is shared by all nodes using this method.
    """
    nn = n - 1
    update_edge_cache(nn) # make sure the edge cache is large enough
    return _edgeCache["main"][:nn] + [[nn, 0]]
