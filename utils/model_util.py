"""Utils used in s2s"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf

# copied from tensorflow/nmt project


def create_attention_mechanism(attention_option, num_units, memory,
                               memory_sequence_length):
    """Create attention mechanism based on the attention_option."""
    # Mechanism
    if attention_option == "luong":
        attention_mechanism = tf.contrib.seq2seq.LuongAttention(
            num_units, memory, memory_sequence_length=memory_sequence_length)
    elif attention_option == "scaled_luong":
        attention_mechanism = tf.contrib.seq2seq.LuongAttention(
            num_units,
            memory,
            memory_sequence_length=memory_sequence_length,
            scale=True)
    elif attention_option == "bahdanau":
        attention_mechanism = tf.contrib.seq2seq.BahdanauAttention(
            num_units, memory, memory_sequence_length=memory_sequence_length)
    elif attention_option == "normed_bahdanau":
        attention_mechanism = tf.contrib.seq2seq.BahdanauAttention(
            num_units,
            memory,
            memory_sequence_length=memory_sequence_length,
            normalize=True)
    else:
        raise ValueError("Unknown attention option %s" % attention_option)

    return attention_mechanism


def get_optimizer(opt):
    """
    A function to get optimizer.

    :param opt: optimizer function name
    :returns: the optimizer function
    :raises assert error: raises an assert error
    """
    if opt == "adam":
        optfn = tf.train.AdamOptimizer
    elif opt == "sgd":
        optfn = tf.train.GradientDescentOptimizer
    else:
        assert False
    return optfn


def create_emb_for_encoder_and_decoder(share_vocab,
                                       src_vocab_size,
                                       tgt_vocab_size,
                                       src_embed_size,
                                       tgt_embed_size,
                                       dtype=tf.float32,
                                       scope=None):
    """Create embedding matrix for both encoder and decoder.
    Args:
    share_vocab: A boolean. Whether to share embedding matrix for both
        encoder and decoder.
    src_vocab_size: An integer. The source vocab size.
    tgt_vocab_size: An integer. The target vocab size.
    src_embed_size: An integer. The embedding dimension for the encoder's
        embedding.
    tgt_embed_size: An integer. The embedding dimension for the decoder's
        embedding.
    dtype: dtype of the embedding matrix. Default to float32.
    scope: VariableScope for the created subgraph. Default to "embedding".
    Returns:
    embedding_encoder: Encoder's embedding matrix.
    embedding_decoder: Decoder's embedding matrix.
    Raises:
    ValueError: if use share_vocab but source and target have different vocab
        size.
    """
    with tf.variable_scope(scope or "embeddings", dtype=dtype) as scope:
        # Share embedding
        if share_vocab:
            if src_vocab_size != tgt_vocab_size:
                raise ValueError("Share embedding but different src/tgt vocab sizes"
                                 " %d vs. %d" % (src_vocab_size, tgt_vocab_size))
            embedding = tf.get_variable(
                "embedding_share", [src_vocab_size, src_embed_size], dtype, initializer=tf.random_uniform_initializer(-1, 1))
            embedding_encoder = embedding
            embedding_decoder = embedding
        else:
            with tf.variable_scope("encoder"):
                embedding_encoder = tf.get_variable(
                    "embedding_encoder", [src_vocab_size, src_embed_size], dtype, initializer=tf.random_uniform_initializer(-1, 1))

            with tf.variable_scope("decoder"):
                embedding_decoder = tf.get_variable(
                    "embedding_decoder", [tgt_vocab_size, tgt_embed_size], dtype, initializer=tf.random_uniform_initializer(-1, 1))

    return embedding_encoder, embedding_decoder


def single_rnn_cell(cell_name, num_units, train_phase=True, keep_prob=0.75, device_str=None, residual_connection=False):
    """
    Get a single rnn cell
    """
    cell_name = cell_name.upper()
    if cell_name == "GRU":
        cell = tf.contrib.rnn.GRUCell(num_units)
    elif cell_name == "LSTM":
        cell = tf.contrib.rnn.LSTMCell(num_units)
    else:
        cell = tf.contrib.rnn.BasicRNNCell(num_units)

    # dropout wrapper
    if train_phase and keep_prob < 1.0:
        cell = tf.contrib.rnn.DropoutWrapper(
            cell=cell,
            input_keep_prob=keep_prob,
            output_keep_prob=keep_prob)

    # Residual
    if residual_connection:
        cell = tf.contrib.rnn.ResidualWrapper(cell)

    # device wrapper
    if device_str:
        cell = tf.contrib.rnn.DeviceWrapper(cell, device_str)
    return cell


def get_device_str(device_id, num_gpus):
    """Return a device string for multi-GPU setup."""
    if num_gpus == 0:
        return "/cpu:0"
    device_str_output = "/gpu:%d" % (device_id % num_gpus)
    return device_str_output


def get_cell_list(cell_name, num_units, num_layers, num_residual_layers=0,
                  train_phase=True, num_gpus=1, base_gpu=0, keep_prob=0.8):
    """Create a list of RNN cells."""
    # Multi-GPU
    cell_list = []
    for i in range(num_layers):
        single_cell = single_rnn_cell(
            cell_name=cell_name,
            num_units=num_units,
            keep_prob=keep_prob,
            train_phase=train_phase,
            residual_connection=(i >= num_layers - num_residual_layers),
            device_str=get_device_str(i + base_gpu, num_gpus),
        )
        cell_list.append(single_cell)

    return cell_list

def multi_rnn_cell(cell_name, dim_size, num_layers=1, train_phase=True, keep_prob=0.80, num_residual_layers=0, num_gpus=1, base_gpu=0):
    """
    Get multi layer rnn cell
    """
    cells = get_cell_list(cell_name, dim_size, num_layers,
                          num_residual_layers, train_phase, num_gpus, base_gpu, keep_prob)
    if len(cells) > 1:
        final_cell = tf.contrib.rnn.MultiRNNCell(cells=cells)
    else:
        final_cell = cells[0]
    return final_cell
