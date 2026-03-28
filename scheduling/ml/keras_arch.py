"""Keras architectures for slot-unfitness: MLP (tabular) and small Transformer over the weekly slot sequence."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def build_mlp_model(feature_size: int = 7):
    import tensorflow as tf

    return tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=(feature_size,)),
            tf.keras.layers.Dense(32, activation="relu"),
            tf.keras.layers.Dense(16, activation="relu"),
            tf.keras.layers.Dense(1, activation="sigmoid"),
        ]
    )


def build_transformer_week_model(seq_len: int, feature_size: int = 7, *, d_model: int = 32, num_heads: int = 4, ff_dim: int = 64):
    """
    Encoder-style stack over the sequence of slots (time within week).
    Input: (batch, seq_len, feature_size), output: (batch, seq_len, 1) per-slot unfitness.
    """
    import tensorflow as tf

    inputs = tf.keras.layers.Input(shape=(seq_len, feature_size))
    x = tf.keras.layers.LayerNormalization()(inputs)
    x = tf.keras.layers.Dense(d_model)(x)
    for _ in range(2):
        attn = tf.keras.layers.MultiHeadAttention(
            num_heads=num_heads,
            key_dim=max(8, d_model // num_heads),
            dropout=0.1,
        )(x, x)
        x = tf.keras.layers.Add()([x, attn])
        x = tf.keras.layers.LayerNormalization()(x)
        ff = tf.keras.layers.Dense(ff_dim, activation="relu")(x)
        ff = tf.keras.layers.Dense(d_model)(ff)
        x = tf.keras.layers.Add()([x, ff])
        x = tf.keras.layers.LayerNormalization()(x)
    outputs = tf.keras.layers.Dense(1, activation="sigmoid")(x)
    return tf.keras.Model(inputs, outputs)
