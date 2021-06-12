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

import numpy as np
from scipy.optimize import linear_sum_assignment
from common.utils.markers import get_marker_position_or_location
from common.utils.bridge import camera_coordinates_to_geocentric

def transform_rf_to_array(reference, found):
    src = []
    dst = []
    for ref in reference:
        ref_location = get_marker_position_or_location(ref)
        src.append(camera_coordinates_to_geocentric(ref_location))
    for f in found:
        dst.append(camera_coordinates_to_geocentric(f.position))
    return np.array(src), np.array(dst)


def find_distances_indices(src, dst, mindist=10):
    distances = np.zeros((src.shape[0], dst.shape[0]))
    for p1 in range(src.shape[0]):
        for p2 in range(dst.shape[0]):
            distances[p1][p2] = np.linalg.norm(src[p1] - dst[p2])
    # solve linera assignment problem to find marker correspndence
    row_ind, col_ind = linear_sum_assignment(distances)
    indices = np.ones(src.shape[0], dtype=np.uint32) * (-1)
    res_dist = np.ones(src.shape[0], dtype=np.float32) * 100
    maxdist = 0
    worst_col = 0
    for col, row in zip(col_ind, row_ind):
        d = distances[row][col]
        if d > maxdist:
            maxdist = d
            worst_col = col
    # w = np.mean(distances, axis=0)
    if (maxdist > mindist) and dst.shape[0] > 3:
        # worst found marker
        good_indices = np.array([i for i in range(dst.shape[0]) if i != worst_col])
        mapping = {o: g for g, o in zip(good_indices, range(dst.shape[0]))}
        # try to solve this problem without worst marker
        res_dist, indices = find_distances_indices(src, dst[good_indices], mindist)
        # restore indices
        for idx in range(indices.shape[0]):
            if indices[idx] != -1:
                indices[idx] = mapping[indices[idx]]
        return res_dist, indices

    for col, row in zip(col_ind, row_ind):
        indices[row] = col
        res_dist[row] = distances[row][col]
    return res_dist, indices


def best_fit_transform(A, B):
    '''
    Calculates the least-squares best-fit transform between corresponding 3D points A->B
    Input:
      A: Nx3 numpy array of corresponding 3D points
      B: Nx3 numpy array of corresponding 3D points
    Returns:
      T: 4x4 homogeneous transformation matrix
      R: 3x3 rotation matrix
      t: 3x1 column vector
    '''

    assert len(A) == len(B)

    # translate points to their centroids
    centroid_A = np.mean(A, axis=0)
    centroid_B = np.mean(B, axis=0)
    AA = A - centroid_A
    BB = B - centroid_B

    # rotation matrix
    H = np.dot(AA.T, BB)
    U, S, Vt = np.linalg.svd(H)
    R = np.dot(Vt.T, U.T)

    # special reflection case
    if np.linalg.det(R) < 0:
       Vt[2,:] *= -1
       R = np.dot(Vt.T, U.T)

    # translation
    t = centroid_B.T - np.dot(R,centroid_A.T)

    # homogeneous transformation
    T = np.identity(4)
    T[0:3, 0:3] = R
    T[0:3, 3] = t

    return T, R, t

def icp(A, B, mindist=10, max_iterations=20, tolerance=0.001):
    '''
    The Iterative Closest Point method
    Input:
        A: Nx3 numpy array of source 3D points
        B: Nx3 numpy array of destination 3D point
        init_pose: 4x4 homogeneous transformation
        max_iterations: exit algorithm after max_iterations
        tolerance: convergence criteria
    Output:
        T: final homogeneous transformation
        distances: Euclidean distances (errors) of the nearest neighbor
    '''
    src = np.ones((4,A.shape[0]))
    dst = np.ones((4,B.shape[0]))
    src[0:3,:] = np.copy(A.T)
    dst[0:3,:] = np.copy(B.T)

    prev_error = 0

    for i in range(max_iterations):
        # find the best correspondence between the current source and destination points
        distances, indices = find_distances_indices(src[0:3,:].T, dst[0:3,:].T, mindist)

        src_indices = []
        dst_indices = []
        for i, idx in enumerate(indices):
            if idx != -1:
                src_indices.append(i)
                dst_indices.append(idx)

        # compute the transformation between the current source and nearest destination points
        T,_,_ = best_fit_transform(src[0:3,src_indices].T, dst[0:3,dst_indices].T)

        # update the current source
        src = np.dot(T, src)

        # check error
        mean_error = np.mean(distances[indices != -1])
        if abs(prev_error-mean_error) < tolerance:
            break
        prev_error = mean_error

    # calculate final transformation
    T,_,_ = best_fit_transform(A, src[0:3,:].T)

    return T, distances, indices
