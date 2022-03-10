#!/usr/bin/env python
# -*- coding: utf-8 -*-

# ==============================================================================
# author          :Ghislain Vieilledent
# email           :ghislain.vieilledent@cirad.fr, ghislainv@gmail.com
# web             :https://ecology.ghislainv.fr
# python_version  :>=3
# license         :GPLv3
# ==============================================================================


# Third party imports
import numpy as np
from osgeo import gdal
import scipy.ndimage

# Local application imports
from misc import progress_bar


# local_defor_rate
def local_defor_rate(input_file, output_file, win_size, time_interval,
                     blk_rows=128):
    """Computing the local deforestation rate using a moving window.

    This function computes the local deforestation rate using a moving
    window. SciPy is used for the focal analysis. The
    ``uniform_filter`` is used over the ``generic_filter``. The
    ``generic_filter`` is 40 times slower than the strides implemented
    in the ``uniform_filter``. For cells on the edge of the raster,
    the local deforestation rate is computed from a lower number of
    existing cells in the moving window using ``mode='constant'`` and
    ``cval=0``.

    :param input_file: Input raster file of forest cover change at
        three dates (123). 1: first period deforestation, 2: second
        period deforestation, 3: remaining forest at the end of the
        second period. No data value must be 0 (zero).

    :param output_file: Output raster file.

    :param win_size: Size of the moving window in number of
        cells. Must be an odd number lower or equal to ``blk_rows``.

    :param time_interval: Time interval (in years) for forest cover
        change observations.

    :param blk_rows: Number of rows for block. Must be greater or
        equal to ``win_size``. This is used to break lage raster files
        in several blocks of data that can be hold in memory.

    :return: A raster with the local deforestation rate.

    """

    # Check win_size
    if (win_size % 2) == 0:
        print("'win_size' must be an odd number.")
        return None
    if (win_size > blk_rows):
        print("'win_size' must be lower or equal to 'blk_rows'.")
        return None

    # Get raster data
    in_ds = gdal.Open(input_file)
    in_band = in_ds.GetRasterBand(1)
    # Raster size
    xsize = in_band.XSize
    ysize = in_band.YSize

    # Create output raster file
    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(output_file, xsize, ysize, 1,
                           gdal.GDT_UInt16,
                           ["COMPRESS=LZW", "PREDICTOR=2", "BIGTIFF=YES"])
    out_ds.SetProjection(in_ds.GetProjection())
    out_ds.SetGeoTransform(in_ds.GetGeoTransform())
    out_band = out_ds.GetRasterBand(1)
    out_band.SetNoDataValue(65535)

    # Iteration
    iter_block = 0

    # Loop on blocks of data
    for i in range(0, ysize, blk_rows):

        # Progress bar
        nblock = (ysize // blk_rows) + 1
        iter_block = iter_block + 1
        progress_bar(nblock, iter_block)

        # Extra lines at the bottom and top
        extra_lines = win_size // 2

        # Compute y offset and line numbers
        # For the condition, think in terms of cell index (starting from 0),
        # not cell number (starting from 1).
        if (i + blk_rows + 2 * extra_lines - 1) < ysize:
            rows = blk_rows + 2 * extra_lines
        else:
            rows = ysize - i + extra_lines
        yoff = max(0, i - extra_lines)

        # Read block data
        in_data = in_band.ReadAsArray(0, yoff, xsize, rows)
        # defor (during first period)
        defor_data = np.zeros(in_data.shape, int)
        defor_data[np.where(in_data == 1)] = 1
        win_defor = scipy.ndimage.filters.uniform_filter(
            defor_data, size=win_size, mode="constant", cval=0,
            output=float)
        # for (start of first period)
        for_data = np.zeros(in_data.shape, int)
        w = np.where(in_data > 0)
        for_data[w] = 1
        win_for = scipy.ndimage.filters.uniform_filter(
            for_data, size=win_size, mode="constant", cval=0,
            output=float)
        # percentage
        out_data = np.ones(in_data.shape, int)*65535
        # w = np.where(win_for >= (1 / win_size ** 2))
        # w = np.where(win_for > np.finfo(float).eps)
        out_data[w] = np.rint(10000 * (1 - (1 - win_defor[w] / win_for[w]) **
                                       time_interval)).astype(int)

        if yoff == 0:
            out_band.WriteArray(out_data)
        else:
            out_band.WriteArray(out_data[(extra_lines):], 0,
                                yoff + extra_lines)

    out_band.FlushCache()
    out_band.ComputeStatistics(False)
    del out_ds, in_ds


# # Test
# ws = 7
# local_defor_rate(input_file="data/fcc123.tif",
#                  output_file="outputs/ldefrate_ws{}.tif".format(ws),
#                  win_size=ws,
#                  time_interval=5,
#                  blk_rows=100)

# End