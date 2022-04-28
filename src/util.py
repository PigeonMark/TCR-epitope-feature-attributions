import datetime
import logging
import os

import numpy as np
import pandas as pd
import tensorflow as tf
import torch

from Bio.PDB import PDBParser, Selection
from Bio.Data.IUPACData import protein_letters_3to1
from Bio import Align
from colour import Color
from matplotlib.colors import ListedColormap


def get_cmap():
    cmap = [c.rgb for c in list(Color('lime').range_to(Color('blue'), 256))]
    cmap = ListedColormap(cmap)
    cmap.set_bad("white")
    return cmap


def split_line(s, max_len):
    if len(s) > max_len:
        words = s.split(' ')
        new_s = ""
        curr_len = 0
        for word in words:
            if curr_len + len(word) < max_len:
                if curr_len == 0:
                    new_s += word
                    curr_len += len(word)
                else:
                    new_s += ' ' + word
                    curr_len += len(word) + 1
            else:
                new_s += '\n' + word
                curr_len = len(word)
        return new_s
    return s


def list_feature_list_to_list_imgs(z):
    return tf.convert_to_tensor(np.reshape(z, (-1, 20, 11, 4)))


def get_mean_feature_values(all_imgs):
    return np.mean(all_imgs, axis=0)


def img_to_feature_list(img):
    if isinstance(img, np.ndarray):
        return img.flatten()
    else:
        return img.numpy().flatten()


def imgs_to_list_of_feature_lists(imgs):
    return imgs.reshape(imgs.shape[0], -1)


def duplicate_input_pair_lists(l, r):
    return l.repeat(2, 1), r.repeat(2, 1)


def concatted_inputs_to_input_pair_lists(concatted_inputs):
    return torch.stack([torch.tensor(i[:25]) for i in concatted_inputs]), torch.stack(
        [torch.tensor(i[25:]) for i in concatted_inputs])


def imrex_remove_padding(m, width, height):
    ver_padding = m.shape[0] - width
    hor_padding = m.shape[1] - height

    ver_before = ver_padding // 2
    ver_after = ver_padding - ver_before

    hor_before = hor_padding // 2
    hor_after = hor_padding - hor_before

    m = m[ver_before:m.shape[0] - ver_after]
    m = m[:, hor_before:m.shape[1] - hor_after]

    return m


def aa_remove_padding(att, in_data):
    start_indices = np.where(in_data == 30)[0]
    end_indices = np.where(in_data == 31)[0]
    return np.concatenate((att[start_indices[0] + 1:end_indices[0]], att[start_indices[1] + 1:end_indices[1]]))


def aa_add_padding(aa, l, fill=np.nan):
    if len(aa) > l:
        print(f'Input {aa} already longer than padding length {l}')
    if len(aa) == l:
        return aa
    diff = l - len(aa)
    pad_before = diff // 2
    pad_after = diff - pad_before
    return np.concatenate(([fill] * pad_before, aa, [fill] * pad_after))


# Rescale [x, y] from [0, y] to [0, 1]
def normalize_2d(m):
    max_val = np.max(m)
    if max_val == 0.0:
        return m
    m = m / max_val
    return m


def error_setup(dm, att):
    dm = normalize_2d(1 / dm)
    att = normalize_2d(att)
    return dm, att


# ROOT MEAN SQUARED ERROR
def rmse(dm, att):
    dm, att = error_setup(dm, att)
    return np.sqrt(np.mean(np.square(dm - att)))


def matrix_to_aa(m, method):
    if method == 'min':
        ep_dist = np.min(m, axis=0)
        cdr3_dist = np.min(m, axis=1)
    elif method == 'max':
        ep_dist = np.max(m, axis=0)
        cdr3_dist = np.max(m, axis=1)
    else:
        logging.getLogger(__name__).error(f'Method {method} not recognized in matrix_to_aa')
        return
    return np.concatenate((ep_dist, cdr3_dist))


# fuction to generate the linear interpolations
def generate_path_inputs(baseline, input, alphas):
    # Expand dimensions for vectorized computation of interpolations.
    alphas_x = alphas[:, tf.newaxis, tf.newaxis, tf.newaxis]
    baseline_x = tf.expand_dims(baseline, axis=0)
    input_x = tf.expand_dims(input, axis=0)
    delta = input_x - baseline_x
    path_inputs = baseline_x + alphas_x * delta

    return path_inputs


# Integral approximation:
# Solves the problem of discontinuous gradient feature importances by taking small steps in the feature space to compute
# local gradients between predictions and inputs across the feature space and then averages these gradients together to
# produce feature attributions.
def integral_approximation(gradients, method='riemann_trapezoidal'):
    # different ways to compute the numeric approximation with different tradeoffs
    # riemann trapezoidal usually the most accurate
    if method == 'riemann_trapezoidal':
        grads = (gradients[:-1] + gradients[1:]) / tf.constant(2.0)
    elif method == 'riemann_left':
        grads = gradients
    elif method == 'riemann_midpoint':
        grads = gradients
    elif method == 'riemann_right':
        grads = gradients
    else:
        raise AssertionError("Provided Riemann approximation method is not valid.")

    # average integration approximation
    integrated_gradients = tf.math.reduce_mean(grads, axis=0)

    return integrated_gradients


def pdb2fasta_mapper(pdb_filepath, pdb_id, model, chain, fasta_seq):
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure(pdb_id, pdb_filepath)
    pdb_tcrb_chain = structure[model][chain]
    pdb_tcrb_sel = Selection.unfold_entities(pdb_tcrb_chain, "R")

    pdb_tcrb_seq = ''
    pdb_tcrb_id_seq = []
    for r in pdb_tcrb_sel:
        if r.get_id()[0] == ' ':
            pdb_tcrb_seq += protein_letters_3to1[r.get_resname().title()]
            pdb_tcrb_id_seq.append(r.get_id()[1])

    aligner = Align.PairwiseAligner()
    alignment = aligner.align(pdb_tcrb_seq, fasta_seq)[0]
    pdb_aligned, fasta_aligned = alignment.aligned

    pdb2fasta_mapper = {}
    for pdb_chunck, fasta_chunk in zip(pdb_aligned, fasta_aligned):
        for pdb_chunck_id, fasta_chunk_id in zip(range(pdb_chunck[0], pdb_chunck[1]),
                                                 range(fasta_chunk[0], fasta_chunk[1])):
            pdb_numbering_id = pdb_tcrb_id_seq[pdb_chunck_id]
            pdb2fasta_mapper[pdb_numbering_id] = fasta_chunk_id

    return pdb2fasta_mapper


def residue_distance_min(res1, res2):
    dist = np.inf
    for a1 in res1:
        for a2 in res2:
            d = a1 - a2
            if d < dist:
                dist = d
    return dist


def get_distance_matrices():
    tcr3df = pd.read_csv("data/tcr3d_imrex_output.csv")
    complex_data_df = pd.read_csv('data/complex_data_original.csv', index_col=0)
    distance_matrices = {}
    for pdb_id in tcr3df['PDB_ID']:
        complex_data = complex_data_df.loc[pdb_id]
        ep_chain_id = complex_data['epitope_chain']
        tcrb_chain_id = complex_data['tcrb_chain']

        parser = PDBParser(QUIET=True)
        structure = parser.get_structure(pdb_id, f'data/pdb/{pdb_id.lower()}.pdb')[0]
        ep_chain = structure[ep_chain_id]
        tcrb_chain = structure[tcrb_chain_id]

        mapper = pdb2fasta_mapper(f'data/pdb/{pdb_id.lower()}.pdb', pdb_id, 0, tcrb_chain_id, complex_data['tcrb_seq'])
        pdb_mapper = {v: k for k, v in mapper.items()}

        dist_matrix = np.zeros((len(complex_data['cdr3']), len(complex_data['antigen.epitope'])))
        for i, mi in zip(range(int(complex_data['CDR3_start']), int(complex_data['CDR3_end']) + 1),
                         range(dist_matrix.shape[0])):
            if i in pdb_mapper:
                for ep, mj in zip(ep_chain, range(dist_matrix.shape[1])):
                    dist_matrix[mi][mj] = residue_distance_min(tcrb_chain[pdb_mapper[i]], ep)
        distance_matrices[pdb_id] = dist_matrix
    return distance_matrices


def setup_logger(name):
    log_file = f"logs/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S_')}{name}.log"
    level = logging.INFO
    # create file logger
    log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(filename=log_file, level=level, format=log_fmt)
    # apply settings to root logger, so that loggers in modules can inherit both the file and console logger
    logger = logging.getLogger()
    # add console logger
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(log_fmt))
    logger.addHandler(console)

    # suppress tf logging
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"  # ERROR
    logging.getLogger("tensorflow").setLevel(logging.ERROR)
    logging.getLogger("shap").setLevel(logging.WARNING)

    return logging.getLogger(__name__)
