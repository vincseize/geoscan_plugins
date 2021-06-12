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
import re
import numpy as np

try:
    from . import tif_worker as tw
except SystemError:
    import tif_worker as tw


class TiledTifWorker:
    """
    Working with tiled tif raster
    Requirements:
    1) All tiles contains in matrix with files names pattern: "tile-<i>-<j>.tif", where i, j - position of tile in matrix
    2) All tiles, except left and bottom borders, have fixed size. In terms of this module, this size named "control size" and file with this size named "control file"
    Allowed:
    1) Matrix can contain holes (tif file miss, as example this tile may contain nodata only)
    2) Matrix can contain only left or/and bottom borders 
    """

    def __init__(self, containig_folder_path):
        """
        Initial constructor
        @param containig_folder_path: path to tiles containing folder
        @type containig_folder_path: str
        @return TiledTifWorker object
        @rtype: TiledTifWorker
        """
        if not os.path.isdir(containig_folder_path):
            raise Exception("Path \"" + containig_folder_path + "\" is not folder!")
        self.__containg_folder_path = containig_folder_path
        self.__need_store_internal_data = True
        self.__files = None
        self.__control_file = None
        self.__matr_dim = None
        self.__tile_name_pattern = "tile-([0-9]+)-([0-9]+)\.tif"

    def store_internal_data(self, flag) -> None:
        """
        Store ps_tif_worker internal data for better performance. If flag is True - all internal data will computing
        only once in first request
        @param flag: is need store internal data
        @type flag: bool
        """
        self.__need_store_internal_data = flag

    def __check_for_tif_tile(self, name) -> bool:
        """
        Check, that file with specified name, is til tile
        @param name: file name without path
        @type name: str
        @return: True, if tile, and False otherwise
        @rtype: bool
        """
        res = re.search(self.__tile_name_pattern, name)
        if res is None:
            return False
        return True

    def __get_tif_files_names(self) -> [str]:
        """
        Get tif tiles names
        @return: list of file names without paths
        @rtype: [str]
        """
        if self.__need_store_internal_data and self.__files is not None:
            return self.__files

        res = [name for name in os.listdir(self.__containg_folder_path) if
               os.path.isfile(os.path.join(self.__containg_folder_path, name)) and self.__check_for_tif_tile(name)]

        if len(res) < 1:
            raise Exception("Folder \"" + self.__containg_folder_path + "\" does't contain any tif tiles!")

        if self.__need_store_internal_data:
            self.__files = res

        return res

    def __get_tif_file_index(self, name) -> np.array:
        """
        Get tif tile index in tiles matrix
        @param name: file name
        @type name: str
        @return: index like [i, j] as numpy array
        @rtype: np.array or None
        """
        res = re.search(self.__tile_name_pattern, name)
        if res is None:
            return None

        idx = res.groups()
        return np.array([int(idx[0]), int(idx[1])], np.uint32)

    def __get_control_tif_file(self) -> [str, np.array]:
        """
        Get control tif tile file name
        @return: file name without path and and index of control file  
        @rtype: [str, np.array] or None
        """
        if self.__need_store_internal_data and self.__control_file is not None:
            return self.__control_file

        max_x, max_y = self.get_tif_files_matrix_dim()

        # calc maximum size of __files by finding one in range from [0, 0] to [max_x - 1, max_y - 1]
        res = None
        for i in range(0, max_x - 1):
            for j in range(0, max_y - 1):
                file_name = "tile-{}-{}.tif".format(i, j)
                if os.path.isfile(os.path.join(self.__containg_folder_path, file_name)):
                    res = [file_name, np.array([i, j])]

        if self.__need_store_internal_data:
            self.__control_file = res

        return res

    def set_tiles_name_pattern(self, regexp) -> None:
        """
        Set tiles __files names pattern as regexp 
        @param regexp: string with regexp
        """
        self.__tile_name_pattern = regexp

    def get_tif_files_matrix_dim(self) -> np.array:
        """
        Get tif tiles matrix dimensions
        @return: matrix dimensions [N, M] as numpy array
        @rtype: np.array
        """
        if self.__need_store_internal_data and self.__matr_dim is not None:
            return self.__matr_dim

        matr_dim = np.array([0, 0], dtype=np.uint32)
        files = self.__get_tif_files_names()

        # get max and min tif files positions
        files_cnt = len(files)
        if files_cnt < 1:
            return matr_dim

        # get positions of files
        positions = []
        for name in files:
            positions.append(self.__get_tif_file_index(name))

        matr_dim[0] = np.max([[val[0]] for val in positions]) + 1
        matr_dim[1] = np.max([[val[1]] for val in positions]) + 1

        if self.__need_store_internal_data:
            self.__matr_dim = matr_dim

        return matr_dim

    def get_tif_transform(self) -> [float]:
        """
        Return transform of full raster
        @return: GDAL transform as [x, dx, a1, y, a2, dy]
        @rtype: [float]
        """
        control_file = self.__get_control_tif_file()

        if control_file is not None:
            file, index = control_file
            file_path = os.path.join(self.__containg_folder_path, file)
            size = tw.get_tif_size(file_path)

            offset = size * index
            transform = tw.get_tif_tranfsorm(file_path)
        else:
            max_x, max_y = self.get_tif_files_matrix_dim()

            left_bottom_file = os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(0, max_y - 1))
            right_top_file = os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(max_x - 1, 0))
            size = np.array([tw.get_tif_size(left_bottom_file)[0],
                             tw.get_tif_size(right_top_file)[1]], dtype=np.uint32)

            offset = size * self.__get_tif_file_index(left_bottom_file)
            transform = tw.get_tif_tranfsorm(left_bottom_file)

        x, dx, a1, y, a2, dy = transform
        x = x - dx * offset[0]
        y = y - dy * offset[1]

        return [x, dx, a1, y, a2, dy]

    def get_tif_nodata(self) -> float:
        """
        Get gdal nodata value from tif file
        @return: nodata value if successful or None otherwise
        @rtype: float or None
        """
        file = self.__get_tif_files_names()[0]
        return tw.get_tif_nodata(os.path.join(self.__containg_folder_path, file))

    def get_raster_size(self) -> np.array:
        """
        Get raster size in pixels
        @return: Raster size [x_size, y_size] as numpy array
        @rtype: np.array or None
        """
        files_cnt = self.get_tif_files_matrix_dim()

        control_file = self.__get_control_tif_file()
        if control_file is not None:
            file = control_file[0]
            size = tw.get_tif_size(os.path.join(self.__containg_folder_path, file))

            # find additional sizes in right and bottom borders
            size = size * np.array([files_cnt[0] - 1, files_cnt[1] - 1], dtype=np.uint32)

            y_size = 0
            for i in range(0, files_cnt[0]):
                file_name = os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(i, files_cnt[1] - 1))
                if os.path.isfile(file_name):
                    y_size = tw.get_tif_size(file_name)[1]
                    break
            size[1] = size[1] + y_size

            x_size = 0
            for j in range(0, files_cnt[1]):
                file_name = os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(files_cnt[0] - 1, j))
                if os.path.isfile(file_name):
                    x_size = tw.get_tif_size(file_name)[0]
                    break
            size[0] = size[0] + x_size
        else:
            size = np.array([tw.get_tif_size(os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(0, files_cnt[1] - 1)))[0],
                             tw.get_tif_size(os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(files_cnt[0] - 1, 0)))[1]], dtype=np.uint32)
            last_size = np.array([tw.get_tif_size(os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(files_cnt[0] - 1, 0)))[0],
                                  tw.get_tif_size(os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(0, files_cnt[1] - 1)))[1]], dtype=np.uint32)
            size = size * (files_cnt - np.array([1, 1])) + last_size

        return size

    def get_tif_attributes(self) -> [float]:
        """
        Get raster attributes
        @return: list of attributes as [transform, [x_size, y_size], nodata, projection]
        @rtype: [float] 
        """
        file = self.__get_tif_files_names()[0]

        attr = tw.get_tif_attributes(os.path.join(self.__containg_folder_path, file))
        attr[0] = self.get_tif_transform()

        return attr

    def load_tifs(self, region=None) -> np.array:
        """
        Load image from the containing folder
        @param region: optional: coordinates of rectangle of interest in pixels for load just region [[x_left, y_top], [x_right, y_bottom]]
        @return: raster image if succeed, None otherwise
        @rtype: np.array or None
        """
        raster_size = self.get_raster_size()
        if region is None:
            region = [np.array([0, 0], dtype=np.uint32), raster_size]
        else:
            # check for region intersection with full_raster is not none
            if region[1][0] > raster_size[0] or region[1][1] > raster_size[1]:
                return None

        file = self.__get_tif_files_names()[0]
        chunk_size = tw.get_tif_size(os.path.join(self.__containg_folder_path, file))
        begin_idx = np.array(region[0] / chunk_size, dtype=np.uint32)
        end_idx = np.array(region[1] / chunk_size, dtype=np.uint32)

        full_raster = np.zeros((region[1][1] - region[0][1], region[1][0] - region[0][0]), dtype=np.float32)
        full_raster.fill(tw.get_tif_nodata(os.path.join(self.__containg_folder_path, file)))

        for i in range(begin_idx[0], end_idx[0] + 1):
            for j in range(begin_idx[1], end_idx[1] + 1):
                file_path = os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(i, j))
                if os.path.isfile(file_path):
                    size = tw.get_tif_size(file_path)
                    cur_pos = np.array([i, j], dtype=np.uint32) * chunk_size
                    cur_rect = [cur_pos, cur_pos + size]

                    intersect = tw.rectangle_intersect(cur_rect, region)
                    if intersect is not None:
                        raster_part = [intersect[0] - region[0], intersect[1] - region[0]]
                        full_raster[int(raster_part[0][1]):int(raster_part[1][1]),
                                    int(raster_part[0][0]):int(raster_part[1][0])] = tw.load_tif(file_path, [intersect[0] - cur_pos, intersect[1] - cur_pos])
        return full_raster

    def load_tif_by_chunks(self, chunks_matr_dim, callable_fnc, additional_params=None, overlap_size=0):
        """
        Loading tif by chunks
        @param chunks_matr_dim: Chunks count in 2 dimensions [size_x, size_y]
        @param callable_fnc: Callable function with params: {cur_raster, cur_chunk, raster_params, optional: additional_params}
        @param additional_params: Additional parameters, translated in callable function [transform, [raster_x_size, raster_y_size], nodata, projection]
        @param overlap_size: Optional: overlap against chunks
        """
        size = self.get_raster_size()
        file = self.__get_tif_files_names()[0]
        raster_params = tw.get_tif_attributes(os.path.join(self.__containg_folder_path, file))
        chunks = tw.divide_rectangle_by_chunks([[0, 0], size], chunks_matr_dim, overlap_size)
        if chunks is None:
            raise Exception("Can't divide by chunks!")

        for i in range(0, chunks_matr_dim[0]):
            for j in range(0, chunks_matr_dim[1]):
                offset, cur_size = chunks[i][j]
                cur_region = [np.array(offset, dtype=np.uint32),
                              np.array([offset[0] + cur_size[0], offset[1] + cur_size[1]], dtype=np.uint32)]

                cur_raster = self.load_tifs(cur_region)

                if additional_params is not None:
                    callable_fnc(cur_raster, [offset, cur_size, i, j], raster_params, additional_params)
                else:
                    callable_fnc(cur_raster, [offset, cur_size, i, j], raster_params)

    def save_tif(self, img, tile_size, attributes=None):
        """
        Save image like tiled GTiff 
        @param img: image source
        @type img: nd.array
        @param tile_size: size of one tile as
        @type tile_size: nd.array
        @param attributes: [transform, [x_size, y_size], nodata, projection]
        """

        img_size = np.array([img.shape[0], img.shape[1]], dtype=np.float32)
        tiles_cnt = np.array(img_size / tile_size, dtype=np.uint)

        additional_tile = np.mod(img_size, tile_size)
        # tiles_cnt[0] = img.shape[0] / tile_size[0] if img.shape[0] % tile_size[0] else img.shape[0] / tile_size[0] + 1
        # tiles_cnt[1] = img.shape[1] / tile_size[1] if img.shape[1] % tile_size[1] else img.shape[1] / tile_size[1] + 1

        for i in range(tiles_cnt[0]):
            for j in range(tiles_cnt[1]):
                if attributes is not None and attributes[2] is not None:
                    img_to_export.fill(attributes[2])

                img_to_export = img[i * tile_size[0]: (i + 1) * tile_size[0], j * tile_size[1]: (j + 1) * tile_size[1]].copy()
                tw.save_tif(img_to_export, os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(i, j)), attributes)

            if additional_tile[1] > 0:
                img_to_export = np.zeros((tile_size[0], tile_size[1]), dtype=np.uint8)
                if attributes is not None and attributes[2] is not None:
                    img_to_export.fill(attributes[2])

                img_to_export[:, 0: img_size[1] - (j - 1) * tile_size[1], :] = img[i * tile_size[0]: (i + 1) * tile_size[0], (j - 1) * tile_size[1]: img_size[1], :].copy()
                tw.save_tif(img_to_export, os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(i, j)), attributes)

        if additional_tile[0] > 0:
            for j in range(tiles_cnt[1]):
                img_to_export = np.zeros((tile_size[0], tile_size[1]), dtype=np.float32)
                if attributes is not None and attributes[2] is not None:
                    img_to_export.fill(attributes[2])

                img_to_export[0: img_size[0] - (i - 1) * tile_size[0], :] = img[(i - 1) * tile_size[0]: img_size[0], j * tile_size[1]: (j + 1) * tile_size[1]].copy()
                tw.save_tif(img_to_export, os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(i, j)), attributes)

            if additional_tile[1] > 0:
                img_to_export = np.zeros((tile_size[0], tile_size[1]), dtype=np.float32)
                if attributes is not None and attributes[2] is not None:
                    img_to_export.fill(attributes[2])

                img_to_export[0: img_size[0] - (i - 1) * tile_size[0], 0: img_size[1] - (j - 1) * tile_size[1]] = img[(i - 1) * tile_size[0]: img_size[0], (j - 1) * tile_size[1]: img_size[1]].copy()
                tw.save_tif(img_to_export, os.path.join(self.__containg_folder_path, "tile-{}-{}.tif".format(i, j)), attributes)


if __name__ == "__main__":
    raster = tw.load_tif("D:\\projects\\tif_worker\\part3.tif")
    worker = TiledTifWorker("D:\\projects\\tif_worker\\res")
    worker.save_tif(raster, np.array([10000, 10000]), tw.get_tif_attributes("D:\\projects\\tif_worker\\part3.tif"))
