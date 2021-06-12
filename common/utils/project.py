"""Common scripts, classes and functions

Copyright (C) 2021  Geoscan Ltd. https://www.geoscan.aero/

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import os
import PhotoScan

try:
    from .pixel_errors import get_cameras_by_pixel_errors
    from .from_project_dir import ProjectProperties
except SystemError:
    from pixel_errors import get_cameras_by_pixel_errors
    from from_project_dir import ProjectProperties


# Allowed PhotoScan image extansions
IMAGES_EXTANSIONS = {
    '.jpg',
    '.jpeg',
    '.tif',
    '.tiff',
    '.png',
    '.bmp',
    '.arw',
    '.png',
}


class BadProject(RuntimeError):
    """
    Special exception for represent inappropriate project. For example, not openable project
    """


class Extent:
    """
    Holds extent of something
    """
    def __init__(self, left=None, right=None, bottom=None, top=None):
        self.left = left
        self.right = right
        self.bottom = bottom
        self.top = top

    @classmethod
    def from_object(cls, obj):
        """
        Creates Extent instance from object with attributes: left, right, bottom, top
        :param obj:
        :return: Extent instance
        """
        extent = cls(
            left=obj.left,
            right=obj.right,
            bottom=obj.bottom,
            top=obj.top
        )
        return extent

    def __iter__(self):
        return (i for i in (self.left, self.right, self.bottom, self.top))

    def __repr__(self):
        return "<Extent instance: left={}, right={}, bottom={}, top={}>".format(*self)

    def __bool__(self):
        return all(i is not None for i in self)


def add_photos_by_steps(paths, k=1000, progress=None):
    def create_progress_func():
        if progress:
            return lambda val: progress((i + val/100) * 100 / total_groups)
        else:
            return None

    app = PhotoScan.app
    images_paths = filter(lambda x: os.path.splitext(x)[1].lower() in IMAGES_EXTANSIONS, paths)
    filtered_paths = filter(lambda x: os.path.isfile(x), images_paths)
    filtered_paths = list(filtered_paths)

    app.update()

    groups, remainder = divmod(len(filtered_paths), k)

    chunk = __get_current_chunk()

    total_groups = (groups + 1) if remainder else groups
    n = 0
    for i in range(groups):
        m = i * k
        n = m + k
        print('Adding photos (step %s of %s) from %s to %s...' % (i+1, total_groups, m+1, n))
        add_photos(filtered_paths[m:n], progress=create_progress_func())

    if remainder:
        i = total_groups-1
        print('Adding photos (step %s of %s) from %s to %s...' % (total_groups, total_groups, n+1, len(filtered_paths)))
        add_photos(filtered_paths[n:], progress=create_progress_func())

    existing_cams = set([os.path.normpath(cam.photo.path) for cam in chunk.cameras])
    paths_set = set(images_paths)
    not_added = paths_set - existing_cams

    if not_added:
        print('Some photos were not added!')
        return not_added
    else:
        print('Photos successfully added!')


def add_photos(path_list, progress=None):
    chunk = __get_current_chunk()

    if progress is not None:
        chunk.addPhotos(path_list, strip_extensions=False, progress=progress)
    else:
        chunk.addPhotos(path_list, strip_extensions=False)


def add_photos_ignore_existing(path_list, progress=None):
    app = PhotoScan.app
    chunk = __get_current_chunk()

    existing_cams = set([os.path.normpath(i.photo.path).replace('STORAGE-NAS-', 'storage-nas-') for i in chunk.cameras])

    cams_to_add = [i.replace('STORAGE-NAS-', 'storage-nas-') for i in path_list]
    app.update()

    new_cams = set(cams_to_add) - existing_cams
    app.update()

    if new_cams:
        return add_photos_by_steps(new_cams, progress=progress)


def get_dir(path=None):
    if path:
        return ProjectProperties.get_dir(path)
    else:
        return PhotoScan.app.document.path


def check_images_paths():
    cameras = __get_current_chunk().cameras
    broken = []

    for cam in cameras:
        if not os.path.isfile(cam.photo.path):
            broken.append(cam)
    return broken


def open_project(path, ignore_lock=True):
    if ignore_lock:
        project_dir = get_dir(path)
        lock_path = os.path.join(project_dir, 'lock')
        if os.path.isfile(lock_path):
            try:
                os.remove(lock_path)
                print('Removed: {}'.format(lock_path))
            except OSError:
                print('File "lock" is blocked: {}'.format(lock_path))
    try:
        PhotoScan.app.document.open(path)
    except RuntimeError as e:
        raise BadProject('Failed to load project "{}"\nwith message "{}"'.format(path, str(e)))


def reload_project():
    path = PhotoScan.app.document.path
    open_project(path)


def realign_cameras_by_pixel_error(pixerror=4.0):
    huge_errors = get_cameras_by_pixel_errors(pixerror)
    if len(huge_errors) < 100:
        realign_cameras(huge_errors)
        huge_errors = get_cameras_by_pixel_errors(pixerror)
        for c in huge_errors:
            c.enabled = False
            c.reference.enabled = False
            print(c)
    return huge_errors


def realign_cameras(cameras):
    chunk = __get_current_chunk()

    for c in cameras:
        c.transform = None

    chunk.alignCameras(
        cameras,
        adaptive_fitting=False
    )


def __something_by_key(iterable, object_name, key):
    """
    Returns something by its key attribute from iterable
    :param iterable: iterable object
    :param object_name: str — used for exception generation
    :param key: int
    :return: PhotoScan.Shape instance
    :raises: RuntimeError
    """
    for obj in iterable:
        if obj.key == key:
            return obj
    raise RuntimeError('Cannot find {} with key: {}'.format(object_name, key))


def chunk_by_key(key):
    """
    Returns chunk by its key
    :param key: int
    :return: PhotoScan.Chunk instance
    :raises: RuntimeError
    """
    return __something_by_key(PhotoScan.app.document.chunks, "chunk", key)


def sensor_by_key(key):
    """
    Returns sensor by its key
    :param key: int
    :return: PhotoScan.Sensor instance
    :raises: RuntimeError
    """
    return __something_by_key(__get_current_chunk().sensors, "sensor", key)


def shape_by_key(key):
    """
    Returns shape by its key
    :param key: int
    :return: PhotoScan.Shape instance
    :raises: RuntimeError
    """
    return __something_by_key(__get_current_chunk().shapes, "shape", key)


def __get_current_chunk(project_path=None):
    """
    Returns current chunk, or raises BadProject exceptions, if project.chunk is empty
    :param project_path:
    :return: PhotoScan.Chunk instance
    :raises: BadProject
    """
    if project_path:
        open_project(project_path)

    chunk = PhotoScan.app.document.chunk
    if chunk is None:
        raise BadProject("Empty chunk!")

    return chunk


def cameras_extent():
    """
    Returns cameras extent in user CRS
    :return: Extent instance
    """

    def xy(cam):
        xy = cam.reference.location[:2]
        return xy

    cameras = __get_current_chunk().cameras

    if not cameras:
        raise BadProject('No cameras in chunk!')

    cameras_iter = iter(cameras)

    success = False
    left = right = top = bottom = None
    for cam in cameras_iter:
        try:
            x, y = xy(cam)
        except TypeError:
            pass
        else:
            success = True
            left = right = x
            top = bottom = y
            break

    if not success:
        raise BadProject('No referenced cameras!')

    for cam in cameras_iter:
        try:
            x, y = xy(cam)
        except TypeError:
            continue

        if x < left:
            left = x
        elif x > right:
            right = x

        if y < bottom:
            bottom = y
        elif y > top:
            top = y

    extent = Extent(left, right, bottom, top)
    return extent


def available_extent():
    """
    Gets first available extent: orthomosaic, dem, cameras extents. Extent in user CRS
    :return: Extent instance
    """
    chunk = __get_current_chunk()
    grid = chunk.orthomosaic or chunk.elevation
    if grid is None:
        return cameras_extent()
    return Extent.from_object(grid)


if __name__ == '__main__':
    extent_ = Extent.from_object(PhotoScan.app.document.chunk.orthomosaic)
    extent2_ = cameras_extent()
    print(extent_)
    print(extent2_)
