from __future__ import annotations

import functools as ft

import jax.numpy as jnp
import jax.random as jr
import pytreeclass as pytc

from serket.nn.callbacks import range_cb_factory, validate_spatial_in_shape

frozen_in_zero_one_cbs = [range_cb_factory(0, 1), pytc.freeze]


@pytc.treeclass
class Dropout:
    r"""Randomly zeroes some of the elements of the input
    tensor with probability :attr:`p` using samples from a Bernoulli
    distribution.

    Args:
        p: probability of an element to be zeroed. Default: 0.5

    Example:
        >>> import serket as sk
        >>> import pytreeclass as pytc
        >>> layer = sk.nn.Dropout(0.5)
        >>> # change `p` to 0.0 to turn off dropout
        >>> layer = layer.at["p"].set(0.0, is_leaf=pytc.is_frozen)
    Note:
        Use `p`= 0.0 to turn off dropout.
    """

    p: float = pytc.field(default=0.5, callbacks=[*frozen_in_zero_one_cbs])

    def __call__(self, x, *, key: jr.KeyArray = jr.PRNGKey(0)):
        return jnp.where(jr.bernoulli(key, (1 - self.p), x.shape), x / (1 - self.p), 0)


@pytc.treeclass
class DropoutND:
    """Drops full feature maps along the channel axis.

    Args:
        p: fraction of an elements to be zeroed out

    Note:
        See:
            https://keras.io/api/layers/regularization_layers/spatial_dropout1d/
            https://arxiv.org/abs/1411.4280

    Example:
        >>> layer = DropoutND(0.5, spatial_ndim=1)
        >>> layer(jnp.ones((1, 10)))
        [[2., 2., 2., 2., 2., 2., 2., 2., 2., 2.]]
    """

    spatial_ndim: int = pytc.field(callbacks=[pytc.freeze])
    p: float = pytc.field(default=0.5, callbacks=[*frozen_in_zero_one_cbs])

    @ft.partial(validate_spatial_in_shape, attribute_name="spatial_ndim")
    def __call__(self, x, *, key=jr.PRNGKey(0)):
        mask = jr.bernoulli(key, 1 - self.p, shape=(x.shape[0],))
        return jnp.where(mask, x / (1 - self.p), 0)


@pytc.treeclass
class Dropout1D(DropoutND):
    def __init__(self, p: float = 0.5):
        """Drops full feature maps along the channel axis.

        Args:

            p: fraction of an elements to be zeroed out

        Note:

            See:
                https://keras.io/api/layers/regularization_layers/spatial_dropout1d/
                https://arxiv.org/abs/1411.4280

        Example:
            >>> layer = DropoutND(0.5, spatial_ndim=1)
            >>> layer(jnp.ones((1, 10)))
            [[2., 2., 2., 2., 2., 2., 2., 2., 2., 2.]]
        """
        super().__init__(p=p, spatial_ndim=1)


@pytc.treeclass
class Dropout2D(DropoutND):
    def __init__(self, p: float = 0.5):
        """Drops full feature maps along the channel axis.

        Args:

            p: fraction of an elements to be zeroed out

        Note:

            See:
                https://keras.io/api/layers/regularization_layers/spatial_dropout1d/
                https://arxiv.org/abs/1411.4280

        Example:
            >>> layer = DropoutND(0.5, spatial_ndim=1)
            >>> layer(jnp.ones((1, 10)))
            [[2., 2., 2., 2., 2., 2., 2., 2., 2., 2.]]
        """
        super().__init__(p=p, spatial_ndim=2)


@pytc.treeclass
class Dropout3D(DropoutND):
    def __init__(self, p: float = 0.5):
        """Drops full feature maps along the channel axis.

        Args:

            p: fraction of an elements to be zeroed out

        Note:

            See:
                https://keras.io/api/layers/regularization_layers/spatial_dropout1d/
                https://arxiv.org/abs/1411.4280

        Example:
            >>> layer = DropoutND(0.5, spatial_ndim=1)
            >>> layer(jnp.ones((1, 10)))
            [[2., 2., 2., 2., 2., 2., 2., 2., 2., 2.]]
        """
        super().__init__(p=p, spatial_ndim=3)
