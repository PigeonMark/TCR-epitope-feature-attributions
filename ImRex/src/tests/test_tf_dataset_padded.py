import tensorflow as tf

from ImRex.src.bio.feature_builder import CombinedPeptideFeatureBuilder
from ImRex.src.bio.peptide_feature import parse_features, parse_operator
from ImRex.src.config import PROJECT_ROOT
from ImRex.src.data.control_cdr3_source import ControlCDR3Source
from ImRex.src.data.vdjdb_source import VdjdbSource
from ImRex.src.processing.data_stream import DataStream
from ImRex.src.processing.padded_batch_generator import padded_batch_generator
from ImRex.src.processing.padded_dataset_generator import (
    # augment_pairs,
    padded_dataset_generator,
)


features_list = parse_features("hydrophob,isoelectric,mass,hydrophil,charge")
operator = parse_operator("absdiff")
feature_builder = CombinedPeptideFeatureBuilder(features_list, operator)


def test_tf_dataset_shuffle():
    """Test whether sequential iteration through tf.data.DataSet objects results in different batches.

    E.g. during every epoch, the generated batches should ideally be different every time.

    When using a DataSet object that was created from a NumPy array, this behaviour is controlled by the
    shuffle(buffer_size=len(x), seed=42, reshuffle_each_iteration=True)
    reshuffle_each_iteration argument.

    However, when using a custom generator, the behaviour is controlled by the underlying generator code.
    """
    data_source = VdjdbSource(
        filepath=PROJECT_ROOT / "src/tests/test_vdjdb.csv",
        headers={"cdr3_header": "cdr3", "epitope_header": "antigen.epitope"},
    )
    data_source.add_pos_labels()
    data_stream = DataStream(data_source)

    tf_dataset = padded_batch_generator(
        data_stream=data_stream,
        feature_builder=feature_builder,
        neg_ratio=0.5,
        cdr3_range=(10, 20),
        epitope_range=(8, 11),
        negative_ref_stream=None,
    )

    tf_dataset = tf_dataset.batch(10)

    iteration_1 = [i[1] for i in list(tf_dataset.as_numpy_iterator())]
    iteration_2 = [i[1] for i in list(tf_dataset.as_numpy_iterator())]

    # list of arrays where each array is a batch. equality of np.arrays results in array of bools per comparison
    # [array([False, False, False, False,  True]), array([False, False, False, False, False]), ...
    # print([i == j for i, j in zip(iteration_1, iteration_2)])

    # [False, False, False, ...] per array/batch
    # print([all(a) for a in [i == j for i, j in zip(iteration_1, iteration_2)]])

    # as long as not all arrays/batches are completely identical, there is shuffling happening between iterations
    assert not all([all(a) for a in [i == j for i, j in zip(iteration_1, iteration_2)]])


def test_tf_dataset_shuffle_array():
    """Same as above, but create the tf.data.DataSet object from numpy arrays. """
    # NOTE: DataStream needs to be re-created, because it will be exhausted by previous test otherwise.
    data_source = VdjdbSource(
        filepath=PROJECT_ROOT / "src/tests/test_vdjdb.csv",
        headers={"cdr3_header": "cdr3", "epitope_header": "antigen.epitope"},
    )
    data_source.add_pos_labels()
    data_stream = DataStream(data_source)

    full_dataset_path = PROJECT_ROOT / "src/tests/test_vdjdb.csv"

    tf_dataset = padded_dataset_generator(
        data_stream=data_stream,
        feature_builder=feature_builder,
        cdr3_range=(10, 20),
        epitope_range=(8, 11),
        neg_shuffle=True,
        full_dataset_path=full_dataset_path,
    )

    tf_dataset = tf_dataset.shuffle(
        buffer_size=len(data_stream), seed=42, reshuffle_each_iteration=True
    ).batch(10)

    iteration_1 = [i[1] for i in list(tf_dataset.as_numpy_iterator())]
    iteration_2 = [i[1] for i in list(tf_dataset.as_numpy_iterator())]

    assert not all([all(a) for a in [i == j for i, j in zip(iteration_1, iteration_2)]])


def test_tf_dataset_shuffle_array_neg_ref():
    """Same as above, but create the tf.data.DataSet object from numpy arrays. """
    # NOTE: DataStream needs to be re-created, because it will be exhausted by previous test otherwise.
    data_source = VdjdbSource(
        filepath=PROJECT_ROOT / "src/tests/test_vdjdb.csv",
        headers={"cdr3_header": "cdr3", "epitope_header": "antigen.epitope"},
    )
    data_source.add_pos_labels()

    negative_source = ControlCDR3Source(
        filepath=PROJECT_ROOT / "src/tests/test_CDR3_control.tsv",
        min_length=10,
        max_length=20,
    )
    data_source.generate_negatives_from_ref(negative_source)

    data_stream = DataStream(data_source)

    tf_dataset = padded_dataset_generator(
        data_stream=data_stream,
        feature_builder=feature_builder,
        cdr3_range=(10, 20),
        epitope_range=(8, 11),
        neg_shuffle=False,
    )

    tf_dataset = tf_dataset.shuffle(
        buffer_size=len(data_stream), seed=42, reshuffle_each_iteration=True
    ).batch(10)

    iteration_1 = [i[1] for i in list(tf_dataset.as_numpy_iterator())]
    iteration_2 = [i[1] for i in list(tf_dataset.as_numpy_iterator())]

    assert not all([all(a) for a in [i == j for i, j in zip(iteration_1, iteration_2)]])


def test_output_shape():
    """ Check if the tf DataSet object contains double the amount of examples of the correct shape (i.e. a negative example for every positive one)."""
    data_source = VdjdbSource(
        filepath=PROJECT_ROOT / "src/tests/test_vdjdb.csv",
        headers={"cdr3_header": "cdr3", "epitope_header": "antigen.epitope"},
    )
    data_source.add_pos_labels()
    n_pos = len(data_source)

    negative_source = ControlCDR3Source(
        filepath=PROJECT_ROOT / "src/tests/test_CDR3_control.tsv",
        min_length=10,
        max_length=20,
    )
    data_source.generate_negatives_from_ref(negative_source)

    data_stream = DataStream(data_source)

    tf_dataset = padded_dataset_generator(
        data_stream=data_stream,
        feature_builder=feature_builder,
        cdr3_range=(10, 20),
        epitope_range=(8, 11),
        neg_shuffle=False,
    )

    assert len(list(tf_dataset.as_numpy_iterator())) == 2 * n_pos

    assert tf_dataset.element_spec == (
        tf.TensorSpec(shape=(20, 11, len(features_list)), dtype=tf.float64, name=None),
        tf.TensorSpec(shape=(), dtype=tf.int64, name=None),
    )

    # repeat without negative reference set

    data_source = VdjdbSource(
        filepath=PROJECT_ROOT / "src/tests/test_vdjdb.csv",
        headers={"cdr3_header": "cdr3", "epitope_header": "antigen.epitope"},
    )
    data_source.add_pos_labels()
    n_pos = len(data_source)

    data_stream = DataStream(data_source)

    full_dataset_path = PROJECT_ROOT / "src/tests/test_vdjdb.csv"

    tf_dataset = padded_dataset_generator(
        data_stream=data_stream,
        feature_builder=feature_builder,
        cdr3_range=(10, 20),
        epitope_range=(8, 11),
        neg_shuffle=True,
        full_dataset_path=full_dataset_path,
    )

    assert len(list(tf_dataset.as_numpy_iterator())) == 2 * n_pos

    assert tf_dataset.element_spec == (
        tf.TensorSpec(shape=(20, 11, len(features_list)), dtype=tf.float64, name=None),
        tf.TensorSpec(shape=(), dtype=tf.int64, name=None),
    )
