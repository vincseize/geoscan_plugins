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

from osgeo import gdal
import numpy as np
import cv2


def get_tif_tranfsorm(path):
    """
    Get transform from tif file
    @param path: path to file
    @return: transform as [x, dx, a1, y, a2, dy] if successful or None otherwise
    """
    data = gdal.Open(path, gdal.GA_ReadOnly)
    if data is None:
        return None
    return data.GetGeoTransform()


def get_tif_size(path):
    """
    Get size of tif file
    @param path: path to file
    @return: size as [size_x, size_y] if successful or None otherwise
    """
    data = gdal.Open(path, gdal.GA_ReadOnly)
    if data is None:
        return None
    return np.array([data.RasterXSize, data.RasterYSize], dtype=np.uint32)


def get_tif_nodata(path):
    """
    Get gdal nodata value from tif file
    @param path: path to file
    @return: nodata value if successful or None otherwise
    """
    data = gdal.Open(path, gdal.GA_ReadOnly)
    if data is None:
        return None
    return data.GetRasterBand(data.RasterCount).GetNoDataValue()


def get_tif_attributes(path):
    """
    Get all tif file attributes
    @param path: path to file
    @return: [transform, [x_size, y_size], nodata, projection] if successful or None otherwise
    """
    data = gdal.Open(path, gdal.GA_ReadOnly)
    if data is None:
        return None

    res = [data.GetGeoTransform(), [data.RasterXSize, data.RasterYSize], data.GetRasterBand(data.RasterCount).GetNoDataValue(), data.GetProjection()]
    return res


def load_tif(path, region=None):
    """
    Load tif file
    @param path: path to file
    @param region: optional: file region coordinates in pixels, in image cs, for load just region [[x_left, y_top], [x_right, y_bottom]]
    @return: image if successful or None otherwise
    """
    def read_band(band):
        if region is None:
            return band.ReadAsArray()
        else:
            return band.ReadAsArray(int(region[0][0]), int(region[0][1]), int(region[1][0] - region[0][0]),
                                             int(region[1][1] - region[0][1]))

    data = gdal.Open(path, gdal.GA_ReadOnly)
    if data is None:
        return None

    raster_band = data.GetRasterBand(1)

    if data.RasterCount == 1:
        raster = read_band(raster_band)
    else:
        first_band = read_band(raster_band)
        raster = np.zeros((first_band.shape[0], first_band.shape[1], data.RasterCount), dtype=first_band.dtype)
        raster[:, :, 0] = first_band

        for i in range(1, data.RasterCount):
            cur_raster_band = data.GetRasterBand(i + 1)
            raster[:, :, i] = read_band(cur_raster_band)

    return raster


def rectangle_intersect(rectangle1, rectangle2):
    """
    Get rectangles intersection
    @param rectangle1: rectangle as [left_top, right_bottom]
    @param rectangle2: rectangle as [left_top, right_bottom]
    @return: intersection as rectangle as [left_top, right_bottom] is intersection exists, None otherwise
    """
    res = [np.maximum(rectangle1[0], rectangle2[0]), np.minimum(rectangle1[1], rectangle2[1])]
    if not (res[0][0] < res[1][0] and res[0][1] < res[1][1]):
        return None
    return res


def save_tif(raster, path, attributes=None):
    """
    Save tif file
    @param raster: image
    @param path: path to save
    @param attributes: [transform, [x_size, y_size], nodata, projection]
    @return: none
    """
    driver = gdal.GetDriverByName("GTiff")

    image_types = {
        'uint8': gdal.GDT_UInt16,
        'float32': gdal.GDT_Float32
    }

    print(len(raster.shape))
    print(image_types[str(raster.dtype)])

    out_raster = driver.Create(path, raster.shape[1], raster.shape[0], raster.shape[2] if len(raster.shape) > 2 else 1, image_types[str(raster.dtype)])

    if out_raster is None:
        raise Exception("Can't save raster")

    if attributes is not None:
        transform, _, _, projection = attributes
        out_raster.SetGeoTransform(transform)
        out_raster.SetProjection(projection)

    if len(raster.shape) > 2:
        for i in range(raster.shape[2]):
            out_raster.GetRasterBand(i + 1).WriteArray(raster[:, :, i])
    else:
        out_raster.GetRasterBand(1).WriteArray(raster)

    out_raster.FlushCache()


def cut_raster(shape, raster, nodata=None, offset=None):
    """
    Cut *.tif __files from directory. If 'nodata' is not None raster will fill by 'nodata' outside shape
    @param shape: shape in image coordinates, that use for cut
    @param raster: raster image to cut
    @param nodata: optional: nodata value for fill raster outside contour. If nodata doesn't set, filling contour outside not provided
    @param offset: optional: returning value of returning raster offset, from original as [[x_offset, y_offset]]
    @return: raster image
    """
    dem_rect = [np.array([0, 0]), np.array([raster.shape[1], raster.shape[0]])]
    x, y, w, h = cv2.boundingRect(shape)
    shape_rect = [np.array([x, y]), np.array([x + w, y + h])]
    bound_rect = rectangle_intersect(dem_rect, shape_rect)

    if bound_rect is None:
        return None

    res = raster[bound_rect[0][1]:bound_rect[1][1], bound_rect[0][0]:bound_rect[1][0]]

    if nodata is not None:
        mask = cv2.drawContours(np.zeros((bound_rect[1][1] - bound_rect[0][1], bound_rect[1][0] - bound_rect[0][0]), dtype=np.uint8), [shape], -1, 1, cv2.FILLED)
        idx = (mask == 0)
        res[idx] = nodata
    if offset is not None:
        offset.append(-1 * bound_rect[0])

    return res


def divide_rectangle_by_chunks(rectangle, chunks_matr_dim, overlap_size=0):
    """
    Divide rectangles by rectangular chunks
    @param rectangle: rectangle to divide as [left_top_point, right_bottom_point]
    @param chunks_matr_dim: new chunks count in two dimensions as [x_cnt, y_cnt]
    @param overlap_size: optional: set overlap between chunks
    @return: list of chunks if overlap size less then rectangle size, None otherwise. Every chunk as [left_point, chunk_size]
    """
    size = np.array([rectangle[1][0] - rectangle[0][0], rectangle[1][1] - rectangle[0][1]])
    if overlap_size > size[0] or overlap_size > size[1] or chunks_matr_dim[0] < 1 or chunks_matr_dim[1] < 1:
        return None

    chunks = np.empty((chunks_matr_dim[0], chunks_matr_dim[1], 2, 2), dtype=np.int32)

    if chunks_matr_dim[0] < 2 and chunks_matr_dim[1] < 2:
        chunks[0][0] = [np.array([0, 0]), size]
        return chunks

    chunk_size = np.array([int(size[0] / chunks_matr_dim[0]), int(size[1] / chunks_matr_dim[1])], dtype=np.int32)
    modulo = size - chunk_size * chunks_matr_dim  # need for modulo consider
    offset = np.array([0, 0], dtype=np.int32)
    prev_size = np.array([0, 0], dtype=np.int32)
    overlap_vec = (0.5 * np.array([overlap_size, overlap_size])).astype(np.uint32)

    for j in range(0, chunks_matr_dim[1]):
        cur_modulo = modulo.copy()
        for i in range(0, chunks_matr_dim[0]):
            offset[0] = offset[0] + prev_size[0]
            cur_size = chunk_size.copy()

            if cur_modulo[0] > 0:
                cur_size[0] = cur_size[0] + 1
                cur_modulo[0] = cur_modulo[0] - 1
            if cur_modulo[1] > 0:
                cur_size[1] = cur_size[1] + 1

            prev_size = cur_size.copy()
            cur_offset = offset - overlap_vec
            cur_size = cur_size + overlap_vec
            cur_offset[cur_offset < 0] = 0

            if cur_offset[0] + cur_size[0] > size[0]:
                cur_size[0] = size[0] - cur_offset[0]
            if cur_offset[1] + cur_size[1] > size[1]:
                cur_size[1] = size[1] - cur_offset[1]

            chunks[i][j] = [cur_offset, cur_size]

        offset[0] = 0
        offset[1] = offset[1] + prev_size[1]
        prev_size[0] = 0

        if modulo[1] > 0:
            modulo[1] = modulo[1] - 1

    return chunks


def load_tif_by_chunks(path, chunks_matr_dim, callable_func, additional_params=None, overlap_size=0):
    """
    Loading tif by chunks
    @param path: Path to file
    @param chunks_matr_dim: Chunks count in 2 dimensions [size_x, size_y]
    @param callable_func: Callable function with params: {raster, cur_chunk, raster_params, optional: additional_params}
    @param additional_params: Additional parameters, translated in callable function [geotransform, [RasterXSize, RasterYSize], nodata_value]
    @param overlap_size: Optional: overlap against chunks
    @return: 
    """
    data = gdal.Open(path, gdal.GA_ReadOnly)
    raster_params = [data.GetGeoTransform(), np.array([data.RasterXSize, data.RasterYSize], dtype=np.uint32),
                     data.GetRasterBand(data.RasterCount).GetNoDataValue()]
    size = [data.RasterXSize, data.RasterYSize]

    chunks = divide_rectangle_by_chunks([[0, 0], size], chunks_matr_dim, overlap_size)
    if chunks is None:
        raise Exception("Can't divide by chunks!")

    for i in range(0, chunks_matr_dim[0]):
        for j in range(0, chunks_matr_dim[1]):
            offset, cur_size = chunks[i][j]
            r = data.GetRasterBand(1)
            raster = r.ReadAsArray(offset[0], offset[1], cur_size[0], cur_size[1])

            if additional_params is not None:
                callable_func(raster, [offset, cur_size, i, j], raster_params, additional_params)
            else:
                callable_func(raster, [offset, cur_size, i, j], raster_params)
