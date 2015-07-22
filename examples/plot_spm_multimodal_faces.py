"""
Minimal script for preprocessing single-subject data (two session)

Author: DOHMATOB Elvis, Bertrand Thirion, 2015

Note: this example takes a lot of time because the input are lists of 3D images
sampled in different position (encoded by different) affine functions.
"""


# standard imports
import os
import nibabel
import numpy as np
from scipy.io import loadmat
import matplotlib.pyplot as plt

# imports for GLM business
from pandas import DataFrame
from nilearn.image import concat_imgs, resample_img, mean_img
from nistats.design_matrix import make_design_matrix
from nistats.glm import FMRILinearModel
from nistats.datasets import fetch_spm_multimodal_fmri

# fetch spm multimodal_faces data
subject_data = fetch_spm_multimodal_fmri()
dataset_dir = os.path.dirname(os.path.dirname(os.path.dirname(
    subject_data.anat)))
output_dir = 'results'

# experimental paradigm meta-params
tr = 2.
drift_model = 'Cosine'
hrf_model = 'Canonical With Derivative'
hfcut = 128.

# make design matrices
first_level_effects_maps = []
mask_images = []
design_matrices = []
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# resample the images 
subject_data.func = [concat_imgs(subject_data.func1, auto_resample=True),
                     concat_imgs(subject_data.func2, auto_resample=True)]
affine, shape = subject_data.func[0].get_affine(), subject_data.func[0].shape
subject_data.func[1] = resample_img(subject_data.func[1], affine, shape[:3])

for x in range(2):
    # build paradigm
    n_scans = subject_data.func[x].shape[-1]
    timing = loadmat(getattr(subject_data, "trials_ses%i" % (x + 1)),
                     squeeze_me=True, struct_as_record=False)

    faces_onsets = timing['onsets'][0].ravel()
    scrambled_onsets = timing['onsets'][1].ravel()
    onsets = np.hstack((faces_onsets, scrambled_onsets))
    onsets *= tr  # because onsets were reporting in 'scans' units
    conditions = ['faces'] * len(faces_onsets) + ['scrambled'] * len(
        scrambled_onsets)
    paradigm = DataFrame({'name': conditions, 'onset': onsets})

    # build design matrix
    frametimes = np.linspace(0, (n_scans - 1) * tr, n_scans)
    design_matrix = make_design_matrix(
        frametimes, paradigm, hrf_model=hrf_model, drift_model=drift_model,
        hfcut=hfcut)
    design_matrices.append(design_matrix)

# specify contrasts
contrasts = {}
n_columns = len(design_matrix.names)
for i in xrange(2):
    contrasts['%s' % design_matrix.names[2 * i]] = np.eye(n_columns)[2 * i]

# more interesting contrasts
contrasts['faces-scrambled'] = contrasts['faces'] - contrasts['scrambled']
contrasts['scrambled-faces'] = -contrasts['faces-scrambled']
contrasts['effects_of_interest'] = np.vstack((contrasts['faces'],
                                              contrasts['scrambled']))

# fit GLM
print 'Fitting a GLM (this takes time)...'
fmri_glm = FMRILinearModel(
    subject_data.func,
    [design_matrix.matrix for design_matrix in design_matrices],
    mask='compute')
fmri_glm.fit(do_scaling=True, model='ar1')

# Create mean image for display
mean_image = mean_img(subject_data.func)

# compute contrast maps
from nilearn.plotting import plot_stat_map
for contrast_id, contrast_val in contrasts.iteritems():
    print "\tcontrast id: %s" % contrast_id
    z_map, t_map, effects_map, var_map = fmri_glm.contrast(
        [contrast_val] * 2, con_id=contrast_id, output_z=True,
        output_stat=True, output_effects=True, output_variance=True)
    for map_type, out_map in zip(['z', 't', 'effects', 'variance'],
                              [z_map, t_map, effects_map, var_map]):
        map_dir = os.path.join(output_dir, '%s_maps' % map_type)
        if not os.path.exists(map_dir):
            os.makedirs(map_dir)
        map_path = os.path.join(map_dir, '%s.nii.gz' % contrast_id)
        nibabel.save(out_map, map_path)
    plot_stat_map(z_map, bg_img=mean_image, threshold=3.0,
                  display_mode='z', cut_coords=3, black_bg=True,
                  title=contrast_id)

plt.show()
