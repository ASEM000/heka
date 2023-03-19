from __future__ import annotations

import functools as ft
from typing import Callable

import jax
import jax.numpy as jnp
import jax.random as jr
import pytreeclass as pytc

from serket.nn.callbacks import init_func_cb, instance_cb_factory
from serket.nn.lazy_class import LAZY_KW, lazy_class

frozen_int_or_tuple_cb = [instance_cb_factory((int, tuple)), pytc.freeze]
frozen_tuple_cb = [instance_cb_factory(tuple), pytc.freeze]


@ft.lru_cache(maxsize=128)
def _multilinear_einsum_string(degree: int) -> str:
    """Generate einsum string for a linear layer of degree n
    Example:
        >>> _multilinear_einsum_string(1)
        '...a,ab->....b'
        >>> _multilinear_einsum_string(2)
        '...a,...b,abc->....c'
    """
    alpha = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    if not (1 <= degree <= len(alpha) - 1):
        msg = f"degree must be between 1 and {len(alpha)-1}, got {degree}"
        raise ValueError(msg)

    xs_string = [f"...{i}" for i in alpha[:degree]]
    output_string = ",".join(xs_string)
    output_string += f",{alpha[:degree+1]}->...{alpha[degree]}"
    return output_string


@ft.lru_cache(maxsize=128)
def _general_linear_einsum_string(*axes: tuple[int, ...]) -> str:
    """Return the einsum string for a general linear layer.
    Example:
        # apply linear layer to last axis
        >>> _general_linear_einsum_string(-1)
        '...a,ab->...b'

        # apply linear layer to last two axes
        >>> _general_linear_einsum_string(-1,-2)
        '...ab,abc->...c'

        # apply linear layer to second last axis
        >>> _general_linear_einsum_string(-2)
        '...ab,ac->...bc'

        # apply linear layer to last and third last axis
        >>> _general_linear_einsum_string(-1,-3)
        '...abc,acd->...bd'
    """
    if not all([i < 0 for i in axes]):
        raise ValueError("axes should be negative")

    axes = sorted(axes)
    total_axis = abs(min(axes))  # get the total number of axes
    alpha = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    input_string = "..." + alpha[:total_axis]
    weight_string = "".join([input_string[axis] for axis in axes]) + alpha[total_axis]
    result_string = "".join([ai for ai in input_string if ai not in weight_string])
    result_string += alpha[total_axis]
    return f"{input_string},{weight_string}->{result_string}"


def infer_func(self, *a, **k):
    return (tuple(xi.shape[-1] for xi in a),)


@ft.partial(lazy_class, lazy_keywords=["in_features"], infer_func=infer_func)
@pytc.treeclass
class Multilinear:
    weight: jax.Array
    bias: jax.Array

    in_features: tuple[int, ...] | None = pytc.field(callbacks=[*frozen_int_or_tuple_cb])  # fmt: skip
    out_features: int = pytc.field(callbacks=[pytc.freeze])

    def __init__(
        self,
        in_features: int | tuple[int, ...] | None,
        out_features: int,
        *,
        weight_init_func: str | Callable = "he_normal",
        bias_init_func: str | Callable = "ones",
        key: jr.KeyArray = jr.PRNGKey(0),
    ):
        """Linear layer with arbitrary number of inputs applied to last axis of each input

        Args:
            in_features: number of input features for each input
            out_features: number of output features
            weight_init_func: function to initialize the weights
            bias_init_func: function to initialize the bias
            key: key for the random number generator

        Example:
            # Bilinear layer
            >>> layer = Multilinear((5,6), 7)
            >>> layer(jnp.ones((1,5)), jnp.ones((1,6))).shape
            (1, 7)

            # Trilinear layer
            >>> layer = Multilinear((5,6,7), 8)
            >>> layer(jnp.ones((1,5)), jnp.ones((1,6)), jnp.ones((1,7))).shape
            (1, 8)

            * Use with lazy initialization
            >>> x = jnp.linspace(0, 1, 100)[:, None]
            >>> lhs = Multilinear(None, 10)
            >>> assert lhs(x, x, x).shape == (100, 10)
            # here a trilinear layer is created with in_features=(1, 1, 1)
            # with weight shape (1, 1, 1, 10) and bias shape (10,)
        """
        if not isinstance(in_features, (tuple, int)):
            msg = f"Expected tuple or int for in_features, got {type(in_features)}"
            raise ValueError(msg)

        self.in_features = in_features
        self.out_features = out_features

        self.weight_init_func = init_func_cb(weight_init_func)
        self.bias_init_func = init_func_cb(bias_init_func)

        weight_shape = (*self.in_features, out_features)
        self.weight = self.weight_init_func(key, weight_shape)

        if self.bias_init_func is None:
            self.bias = None
        else:
            self.bias = self.bias_init_func(key, (out_features,))

    def __call__(self, *x, **k) -> jax.Array:
        einsum_string = _multilinear_einsum_string(len(self.in_features))
        x = jnp.einsum(einsum_string, *x, self.weight)

        if self.bias is None:
            return x
        return x + self.bias


@pytc.treeclass
class Linear(Multilinear):
    """Linear layer with 1 input applied to last axis of input

    Args:
        in_features: number of input features
        out_features: number of output features
        weight_init_func: function to initialize the weights
        bias_init_func: function to initialize the bias
        key: key for the random number generator

    Example:
        >>> layer = Linear(5, 6)
        >>> layer(jnp.ones((1,5))).shape
        (1, 6)

        * Use with lazy initialization
        >>> x = jnp.linspace(0, 1, 100)[:, None]
        >>> lhs = Linear(None, 10)
        >>> assert lhs(x).shape == (100, 10)
        # here a linear layer is created with in_features=1
        # with weight shape (1, 10) and bias shape (10,)
    """

    def __init__(
        self,
        in_features: int | None,
        out_features: int,
        *,
        weight_init_func: str | Callable = "he_normal",
        bias_init_func: str | Callable = "ones",
        key: jr.KeyArray = jr.PRNGKey(0),
    ):
        super().__init__(
            (in_features,),
            out_features,
            weight_init_func=weight_init_func,
            bias_init_func=bias_init_func,
            key=key,
        )


@pytc.treeclass
class Bilinear(Multilinear):
    def __init__(
        self,
        in1_features: int | None,
        in2_features: int | None,
        out_features: int,
        *,
        weight_init_func: str | Callable = "he_normal",
        bias_init_func: str | Callable = "ones",
        key: jr.KeyArray = jr.PRNGKey(0),
    ):
        """Bilinear layer

        Args:
            in1_features: number of input features for the first input
            in2_features: number of input features for the second input
            out_features: number of output features
            weight_init_func: function to initialize the weights
            bias_init_func: function to initialize the bias
            key: key for the random number generator

        Example:
            >>> layer = Bilinear(5, 6, 7)
            >>> layer(jnp.ones((1,5)), jnp.ones((1,6))).shape
            (1, 7)
        """
        super().__init__(
            (in1_features, in2_features),
            out_features,
            weight_init_func=weight_init_func,
            bias_init_func=bias_init_func,
            key=key,
        )


def infer_func(self, *a, **k):
    in_axes = getattr(self, LAZY_KW).keywords["in_axes"]
    return (tuple(a[0].shape[i] for i in in_axes),)


@ft.partial(lazy_class, lazy_keywords=["in_features"], infer_func=infer_func)
@pytc.treeclass
class GeneralLinear:
    weight: jax.Array
    bias: jax.Array

    in_features: tuple[int, ...] | None = pytc.field(callbacks=[*frozen_tuple_cb])
    out_features: tuple[int, ...] | None = pytc.field(callbacks=[pytc.freeze])
    in_axes: tuple[int, ...] | None = pytc.field(callbacks=[*frozen_tuple_cb])

    def __init__(
        self,
        in_features: tuple[int, ...] | None,
        out_features: int,
        *,
        in_axes: tuple[int, ...],
        weight_init_func: str | Callable = "he_normal",
        bias_init_func: str | Callable = "ones",
        key: jr.KeyArray = jr.PRNGKey(0),
    ):
        """Apply a Linear Layer to input at in_axes

        Args:
            in_features: number of input features corresponding to in_axes
            out_features: number of output features
            in_axes: axes to apply the linear layer to
            weight_init_func: weight initialization function
            bias_init_func: bias initialization function
            key: random key

        Example:
            >>> x = jnp.ones([1, 2, 3, 4])
            >>> layer = GeneralLinear(in_features=(1, 2), in_axes=(0, 1), out_features=5)
            >>> assert layer(x).shape == (3, 4, 5)

        Note:
            This layer is similar to to flax linen's DenseGeneral, the difference is that
            this layer uses einsum to apply the linear layer to the specified axes.
        """

        self.in_features = in_features
        self.out_features = out_features
        self.in_axes = in_axes

        if len(in_axes) != len(in_features):
            msg = "Expected in_axes and in_features to have the same length,"
            msg += f"got {len(in_axes)} and {len(in_features)}"
            raise ValueError(msg)

        self.weight_init_func = init_func_cb(weight_init_func)
        self.bias_init_func = init_func_cb(bias_init_func)
        self.weight = self.weight_init_func(key, (*self.in_features, self.out_features))

        if self.bias_init_func is None:
            self.bias = None
        else:
            self.bias = self.bias_init_func(key, (self.out_features,))

    def __call__(self, x: jax.Array, **k) -> jax.Array:
        # ensure negative axes
        axes = map(lambda i: i if i < 0 else i - x.ndim, self.in_axes)
        einsum_string = _general_linear_einsum_string(*axes)
        x = jnp.einsum(einsum_string, x, self.weight)
        return x


@pytc.treeclass
class Identity:
    """Identity layer"""

    def __call__(self, x: jax.Array, **k) -> jax.Array:
        return x
