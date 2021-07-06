try:
    import Metashape as ps
except ImportError:
    import PhotoScan as ps
import time
from itertools import chain


def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()

        print('{} {:2.2f} ms'.format(method.__name__, (te - ts) * 1000))
        return result

    return timed


def get_camera_iter(group_name, return_groups=False):
    chunk = ps.app.document.chunk
    groups = [g for g in chunk.camera_groups if g.label == group_name]
    main_group = groups[0]
    cameras = (c for c in chunk.cameras if c.group == main_group)

    if len(groups) > 1:
        other_groups = groups[1:]
        cameras = chain(cameras, (c for c in chunk.cameras
                                  if c.group in other_groups))
    else:
        other_groups = []

    if return_groups:
        return cameras, main_group, other_groups
    else:
        return cameras


@timeit
def disable_duplicates(group_name):
    chunk = ps.app.document.chunk

    if group_name:
        cameras = get_camera_iter(group_name)
    else:
        cameras = chunk.cameras

    unique = set()
    for c in cameras:
        if c.label in unique:
            c.enabled = False
        else:
            unique.add(c.label)


@timeit
def remove_duplicates(group_name):
    chunk = ps.app.document.chunk

    if group_name:
        cameras = get_camera_iter(group_name)
    else:
        cameras = chunk.cameras

    unique = set()
    to_remove = list()

    for c in cameras:
        if c.label in unique:
            to_remove.append(c)
        else:
            unique.add(c.label)

    if to_remove:
        chunk.remove(to_remove)


@timeit
def merge_groups(group_name):
    chunk = ps.app.document.chunk

    if group_name:
        cameras, main_group, groups_to_remove =\
            get_camera_iter(group_name, return_groups=True)
    else:
        cameras = chunk.cameras
        main_group = None
        groups_to_remove = chunk.camera_groups

    unique = set()
    to_remove = list()

    for c in cameras:
        if c.label in unique:
            to_remove.append(c)
        else:
            unique.add(c.label)
            c.group = main_group

    to_remove += groups_to_remove
    if to_remove:
        chunk.remove(to_remove)
