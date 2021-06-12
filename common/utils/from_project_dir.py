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

import xml.etree.ElementTree as ETree
import os
import zipfile
import shutil


class ProjectProperties:
    def __init__(self, path):
        self.path = path
        self.directory = self.get_dir(path)

        self.__active_chunk = None
        self.__next_chunk_id = None
        self.__chunks = None
        self.__parsed_xml = None

    @staticmethod
    def get_dir(path):
        string, ext = os.path.splitext(path)
        if ext.lower() == '.psx':
            return string + '.files'
        elif ext.lower() == '.psz':
            raise ValueError('".psz" file is archive!')
        else:
            raise ValueError('Unknown format: "{}"'.format(ext.lower()))

    @property
    def chunks(self):
        if self.__chunks is None:
            self.__parse_project_xml()
        return self.__chunks

    @property
    def active_chunk(self):
        if self.__active_chunk is None:
            self.__parse_project_xml()
        return self.__active_chunk

    @property
    def active_frame_tuple(self):
        return self.active_chunk.key, self.active_chunk.active_frame.key

    @property
    def active_frame_path(self):
        return self.active_chunk.active_frame_path

    def __parse_project_xml(self):
        proj_dir = self.directory
        project_archive = os.path.join(proj_dir, r'project.zip')
        proj_xml = get_doc_from_archive(project_archive)

        root = ETree.fromstring(proj_xml)
        chunks = root[0]
        active_chunk_id = chunks.attrib.get('active_id')
        if active_chunk_id is not None:
            active_chunk_id = int(active_chunk_id)
        self.__next_chunk_id = int(chunks.attrib['next_id'])

        chunks_dict = dict()
        for chunk in chunks.findall('chunk'):
            id_ = int(chunk.attrib['id'])
            chunks_dict[id_] = ChunkProperties(os.path.join(self.directory, str(id_)), id_)

        self.__chunks = chunks_dict
        self.__active_chunk = chunks_dict[active_chunk_id if active_chunk_id is not None else id_]
        self.__parsed_xml = root

    def __add_chunk_in_xml_tree(self, id_, active_id, next_id):
        root = self.__parsed_xml
        chunks = root[0]
        chunks.set('active_id', str(active_id))
        chunks.set('next_id', str(next_id))

        chunk = ETree.Element('chunk')
        s_id = str(id_)
        chunk.set('id', s_id)
        chunk.set('path', r'{}/chunk.zip'.format(s_id))
        chunks.append(chunk)

        self.__parsed_xml = root

    def copy_chunk(self, input_chunk, point_cloud=True, dense_cloud=True, elevation=True, orthomosaic=True,
                   tiled_model=True, model=True, shapes=True, thumbnails=True, depth_maps=True):

        def copy_element(elem_tags, save_elem):
            if elem_tags:
                for elem_tag in elem_tags:
                    if save_elem:
                        rel_path = os.path.dirname(elem_tag.attrib['path'])
                        src_path = os.path.join(chunk.active_frame.path, rel_path)
                        dst_path = os.path.join(new_frame_dir, rel_path)
                        shutil.copytree(src_path, dst_path)
                    else:
                        frame_xml.remove(elem_tag)

        if self.__chunks is None:
            self.__parse_project_xml()

        if isinstance(input_chunk, int):
            chunk = self.chunks[input_chunk]
        else:
            chunk = input_chunk

        new_chunk_id = self.__next_chunk_id
        new_chunk_dir = os.path.join(self.directory, str(new_chunk_id))

        while os.path.exists(new_chunk_dir):
            new_chunk_id += 1
            new_chunk_dir = os.path.join(self.directory, str(new_chunk_id))

        new_frame_dir = os.path.join(new_chunk_dir, '0')
        os.makedirs(new_frame_dir)

        chunk_doc_path = os.path.join(chunk.path, 'chunk.zip')
        new_chunk_doc_path = os.path.join(new_chunk_dir, 'chunk.zip')

        frame_doc_path = os.path.join(chunk.active_frame.path, 'frame.zip')
        new_frame_doc_path = os.path.join(new_frame_dir, 'frame.zip')

        shutil.copy(chunk_doc_path, new_chunk_doc_path)
        shutil.copy(frame_doc_path, new_frame_doc_path)

        frame = FrameProperties(new_frame_dir, 0)
        frame_xml = frame.parsed_xml

        copy_element([frame.shapes] if frame.shapes is not None else [], shapes)
        copy_element([frame.thumbnails] if frame.thumbnails is not None else [], thumbnails)
        copy_element([frame.point_cloud] if frame.point_cloud is not None else [], point_cloud)

        copy_element(frame.depth_maps, depth_maps)
        copy_element(frame.dense_clouds, dense_cloud)
        copy_element(frame.elevations, elevation)
        copy_element(frame.orthomosaics, orthomosaic)
        copy_element(frame.tiled_models, tiled_model)
        copy_element(frame.models, model)

        self.__add_chunk_in_xml_tree(new_chunk_id, new_chunk_id, new_chunk_id+1)

        write_doc_in_archive(frame_xml, new_frame_doc_path)
        write_doc_in_archive(self.__parsed_xml, os.path.join(self.directory, 'project.zip'))

        self.__parse_project_xml()
        return self.active_chunk


class ChunkProperties:
    def __init__(self, path, key):
        self.path = path
        self.key = key

        self.__active_frame = None
        self.__reference_wkt = None
        self.__parsed_xml = None


    @property
    def active_frame(self):
        if self.__active_frame is None:
            self.__get_active_frame()
        return self.__active_frame

    @property
    def active_frame_path(self):
        lst = (self.path, self.active_frame.key)
        lst = map(str, lst)
        return os.path.join(*lst)

    @property
    def reference(self):
        if self.__reference_wkt is None:
            self.__parse_chunk_xml()
        return self.__reference_wkt

    def __get_active_frame(self):
        # Unstable :)
        key = 0
        self.__active_frame = FrameProperties(os.path.join(self.path, str(key)), key)

    def __parse_chunk_xml(self):
        chunk_xml = get_doc_from_archive(os.path.join(self.path, 'chunk.zip'))
        root = ETree.fromstring(chunk_xml)
        ref = root.find('reference')
        self.__reference_wkt = ref.text


class FrameProperties:
    def __init__(self, path, key):
        self.path = path
        self.key = key

        self.__parsed_xml = False
        self.__parsed_xml = None

        self.__point_cloud = None
        self.__dense_clouds = None
        self.__tiled_models = None
        self.__models = None
        self.__elevations = None
        self.__orthomosaics = None
        self.__shapes = None
        self.__markers = None
        self.__cameras = None
        self.__thumbnails = None
        self.__depth_maps = None

    @property
    def parsed_xml(self):
        if not self.__parsed_xml:
            self.__parse_frame_xml()
        return self.__parsed_xml

    @property
    def point_cloud(self):
        if not self.__parsed_xml:
            self.__parse_frame_xml()
        return self.__point_cloud

    @property
    def dense_clouds(self):
        if not self.__parsed_xml:
            self.__parse_frame_xml()
        return self.__dense_clouds

    @property
    def tiled_models(self):
        if not self.__parsed_xml:
            self.__parse_frame_xml()
        return self.__tiled_models

    @property
    def models(self):
        if not self.__parsed_xml:
            self.__parse_frame_xml()
        return self.__models

    @property
    def elevations(self):
        if not self.__parsed_xml:
            self.__parse_frame_xml()
        return self.__elevations

    @property
    def orthomosaics(self):
        if not self.__parsed_xml:
            self.__parse_frame_xml()
        return self.__orthomosaics

    @property
    def shapes(self):
        if not self.__parsed_xml:
            self.__parse_frame_xml()
        return self.__shapes

    @property
    def markers(self):
        if not self.__parsed_xml:
            self.__parse_frame_xml()
        return self.__markers

    @property
    def cameras(self):
        if not self.__parsed_xml:
            self.__parse_frame_xml()
        return self.__cameras

    @property
    def thumbnails(self):
        if not self.__parsed_xml:
            self.__parse_frame_xml()
        return self.__thumbnails

    @property
    def depth_maps(self):
        if not self.__parsed_xml:
            self.__parse_frame_xml()
        return self.__depth_maps

    @property
    def point_cloud_exists(self):
        return self.point_cloud is not None

    @property
    def dense_cloud_exists(self):
        return self.dense_clouds is not None

    @property
    def tiled_model_exists(self):
        return self.tiled_models is not None

    @property
    def model_exists(self):
        return self.models is not None

    @property
    def elevation_exists(self):
        return self.elevations is not None

    @property
    def orthomosaic_exists(self):
        return self.orthomosaics is not None

    @property
    def shapes_exists(self):
        return self.shapes is not None

    @property
    def markers_exists(self):
        return self.markers is not None

    @property
    def cameras_exists(self):
        return self.cameras is not None

    @property
    def thumbnails_exists(self):
        return self.thumbnails is not None

    @property
    def depth_maps_exists(self):
        return self.depth_maps is not None

    def __parse_frame_xml(self):
        frame_xml = get_doc_from_archive(os.path.join(self.path, 'frame.zip'))
        root = ETree.fromstring(frame_xml)

        self.__point_cloud = root.find('point_cloud')
        self.__depth_maps = root.findall('depth_maps')
        self.__dense_clouds = root.findall('dense_cloud')
        self.__tiled_models = root.findall('tiled_model')
        self.__models = root.findall('model')
        self.__elevations = root.findall('elevation')
        self.__orthomosaics = root.findall('orthomosaic')
        self.__shapes = root.find('shapes')
        self.__markers = root.find('markers')
        self.__cameras = root.find('cameras')
        self.__thumbnails = root.find('thumbnails')

        self.__parsed_xml = root


def get_doc_from_archive(path):
    with zipfile.ZipFile(path) as archive:
        doc_xml = archive.open(archive.namelist()[0]).read().decode('utf-8')
    return doc_xml


def write_doc_in_archive(doc, path):
    data = ETree.tostring(doc, encoding='utf8')
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('doc.xml', data)


if __name__ == '__main__':
    path_ = r'\\storage-nas-6\data\201606_D013u_Tulskaya\PS_scripts\__dev\ins\projects\056.psx'
    pp = ProjectProperties(path_)
    print(pp.active_chunk.key)
    print(pp.active_frame_tuple)
    print(pp.active_frame_path)
    print(pp.active_chunk.reference)
    print(pp.active_chunk.active_frame.markers)
    print(pp.active_chunk.active_frame.point_cloud)
    print(bool(pp.active_chunk.active_frame.point_cloud))

    pp.copy_chunk(
        input_chunk=101,
        point_cloud=False,
        dense_cloud=False,
        elevation=False,
        orthomosaic=False,
        tiled_model=False,
        shapes=False,
        thumbnails=False,
        depth_maps=False
    )