#==============================================================================#
#  Author:       Dominik Müller                                                #
#  Copyright:    2022 IT-Infrastructure for Translational Medical Research,    #
#                University of Augsburg                                        #
#                                                                              #
#  This program is free software: you can redistribute it and/or modify        #
#  it under the terms of the GNU General Public License as published by        #
#  the Free Software Foundation, either version 3 of the License, or           #
#  (at your option) any later version.                                         #
#                                                                              #
#  This program is distributed in the hope that it will be useful,             #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of              #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               #
#  GNU General Public License for more details.                                #
#                                                                              #
#  You should have received a copy of the GNU General Public License           #
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.       #
#==============================================================================#
#-----------------------------------------------------#
#                   Library imports                   #
#-----------------------------------------------------#
# External libraries
import numpy as np
# Internal libraries
from aucmedi import Image_Augmentation, Volume_Augmentation, DataGenerator
from aucmedi.ensembler.aggregate import aggregate_dict
from aucmedi.data_processing.io_loader import image_loader

#-----------------------------------------------------#
#       Ensemble Learning: Inference Augmenting       #
#-----------------------------------------------------#
def predict_augmenting(model, samples, path_imagedir, n_cycles=10, data_aug=None,
                       aggregate="mean", image_format=None, batch_size=32,
                       resize=(224, 224), grayscale=False, subfunctions=[],
                       standardize_mode="z-score", loader=image_loader,
                       seed=None, workers=1, **kwargs):
    """ Inference Augmenting function for automatically augmenting unknown images for prediction.

    The predictions of the augmented images are aggregated together via the provided aggregate function.

    ???+ example
        ```python
        # Initialize desired Data Augmentation
        test_aug = Image_Augmentation(flip=True, rotate=True, brightness=False, contrast=False,
                                      saturation=False, hue=False, scale=False, crop=False,
                                      grid_distortion=False, compression=False, gamma=False,
                                      gaussian_noise=False, gaussian_blur=False,
                                      downscaling=False, elastic_transform=False)

        # Compute predictions
        preds = predict_augmenting(model, samples, "dataset/images/",
                                   n_cycles=15, img_aug=test_aug, aggregate="majority_vote",
                                   image_format=image_format, batch_size=32,
                                   resize=model.meta_input, standardize_mode=model.meta_standardize)
        ```

    The aggregate function can be either self initialized with an AUCMEDI aggregate function
    or a custom made aggregate function, or by calling an AUCMEDI aggregate function by name.

    !!! info
        Possible aggregate function names: ["mean", "median", "majority_vote", "softmax"]

        More about aggregate functions can be found here: [aggregate][aucmedi.ensembler.aggregate]

    The Data Augmentation class instance which will be used for inference augmenting,
    can be either predefined or leaving `None`.
    If the `data_aug` is `None`, a Data Augmentation class instance is automatically created
    which applies rotation and flipping augmentations.

    Args:
        model (Neural_Network):                 Instance of a AUCMEDI neural network class.
        samples (list of str):                  List of sample/index encoded as Strings.
        path_imagedir (str):                    Path to the directory containing the images.
        n_cycles (int):                         Number of image augmentations, which should be created per sample.
        data_aug (Data Augmentation):           Data Augmentation class instance which performs diverse augmentation techniques.
        aggregate (str or aggregate Function):  Aggregate function class instance or a string for an AUCMEDI aggregate function.
        image_format (str):                     Image format to add at the end of the sample index for image loading.
        batch_size (int):                       Number of samples inside a single batch.
        resize (tuple of int):                  Resizing shape consisting of a X and Y size. (optional Z size for Volumes)
        grayscale (bool):                       Boolean, whether images are grayscale or RGB.
        subfunctions (list of Subfunctions):    List of Subfunctions class instances which will be SEQUENTIALLY executed on the data set.
        standardize_mode (str):                 Standardization modus in which image intensity values are scaled.
                                                Calls the [Standardize][aucmedi.data_processing.subfunctions.standardize] Subfunction.
        loader (io_loader function):            Function for loading samples/images from disk.
        seed (int):                             Seed to ensure reproducibility for random function.
        workers (int):                          Number of workers. If n_workers > 1 = use multi-threading for image preprocessing.
        **kwargs (dict):                        Additional parameters for the sample loader.
    """
    # Initialize aggregate function if required
    if isinstance(aggregate, str) and aggregate in aggregate_dict:
        agg_fun = aggregate_dict[aggregate]()
    else : agg_fun = aggregate

    # Initialize image augmentation if none provided (only flip, rotate)
    if data_aug is None and len(model.input_shape) == 3:
        data_aug = Image_Augmentation(flip=True, rotate=True, scale=False,
                                     brightness=False, contrast=False,
                                     saturation=False, hue=False, crop=False,
                                     grid_distortion=False, compression=False,
                                     gamma=False, gaussian_noise=False,
                                     gaussian_blur=False, downscaling=False,
                                     elastic_transform=False)
    elif data_aug is None and len(model.input_shape) == 4:
        data_aug = Volume_Augmentation(flip=True, rotate=True, scale=False,
                                      brightness=False, contrast=False,
                                      saturation=False, hue=False, crop=False,
                                      grid_distortion=False, compression=False,
                                      gamma=False, gaussian_noise=False,
                                      gaussian_blur=False, downscaling=False,
                                      elastic_transform=False)
    # Multiply sample list for prediction according to number of cycles
    samples_aug = np.repeat(samples, n_cycles)

    # Create DataGenerator for inference
    aug_gen = DataGenerator(samples_aug, path_imagedir, labels=None,
                            batch_size=batch_size, data_aug=data_aug, seed=seed,
                            subfunctions=subfunctions, shuffle=False,
                            standardize_mode=standardize_mode, resize=resize,
                            grayscale=grayscale, prepare_images=False,
                            sample_weights=None, image_format=image_format,
                            loader=loader, workers=workers, **kwargs)

    # Compute predictions with provided model
    preds_all = model.predict(aug_gen)

    # Ensemble inferences via aggregate function
    preds_ensembled = []
    for i in range(0, len(samples)):
        # Identify subset for a single sample
        j = i*n_cycles
        subset = preds_all[j:j+n_cycles]
        # Aggregate predictions
        pred_sample = agg_fun.aggregate(subset)
        # Add prediction to prediction list
        preds_ensembled.append(pred_sample)
    # Convert prediction list to NumPy
    preds_ensembled = np.asarray(preds_ensembled)

    # Return ensembled predictions
    return preds_ensembled
