# Copyright 2023 Serket authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Define dispatchers for custom tree transformations."""

from __future__ import annotations

import functools as ft
from typing import Any, Callable, TypeVar

import jax

import serket as sk

T = TypeVar("T")


class NoState(sk.TreeClass):
    """No state placeholder."""

    def __init__(self, _: Any, __: Any):
        del _, __


def tree_state(tree: T, array: jax.Array | None = None) -> T:
    """Build state for a tree of layers.

    Some layers require state to be initialized before training. For example,
    :class:`nn.BatchNorm` layers requires ``running_mean`` and ``running_var`` to be initialized
    before training. This function initializes the state for a tree of layers,
    based on the layer defined ``state`` rule using ``tree_state.def_state``.

    Args:
        tree: A tree of layers.
        array: (Optional) array to use for initializing state required by some layers
            (e.g. :class:`nn.ConvGRU1DCell`). default: ``None``.

    Returns:
        A tree of state leaves if it has state, otherwise ``None``.

    Example:
        >>> import jax.numpy as jnp
        >>> import serket as sk
        >>> tree = [1, 2, sk.nn.BatchNorm(5)]
        >>> sk.tree_state(tree)
        [NoState(), NoState(), BatchNormState(
          running_mean=f32[5](μ=0.00, σ=0.00, ∈[0.00,0.00]),
          running_var=f32[5](μ=1.00, σ=0.00, ∈[1.00,1.00])
        )]

    Example:
        >>> # define state initialization rule for a custom layer
        >>> import jax
        >>> import serket as sk
        >>> class LayerWithState(sk.TreeClass):
        ...    pass
        >>> # state function accept the `layer` and optional input array as arguments
        >>> @sk.tree_state.def_state(LayerWithState)
        ... def _(leaf):
        ...    return "some state"
        >>> sk.tree_state(LayerWithState())
        'some state'
        >>> sk.tree_state(LayerWithState(), jax.numpy.ones((1, 1)))
        'some state'
    """

    types = tuple(set(tree_state.state_dispatcher.registry) - {object})

    def is_leaf(x: Callable[[Any], bool]) -> bool:
        return isinstance(x, types)

    def dispatch_func(leaf):
        try:
            # single argument
            return tree_state.state_dispatcher(leaf)
        except TypeError:
            # with optional array argument
            return tree_state.state_dispatcher(leaf, array)

    return jax.tree_map(dispatch_func, tree, is_leaf=is_leaf)


tree_state.state_dispatcher = ft.singledispatch(NoState)
tree_state.def_state = tree_state.state_dispatcher.register


def tree_eval(tree):
    """Modify tree layers to disable any trainning related behavior.

    For example, :class:`nn.Dropout` layer is replaced by an :class:`nn.Identity` layer
    and :class:`nn.BatchNorm` layer ``evaluation`` is set to ``True`` when
    evaluating the tree.

    Args:
        tree: A tree of layers.

    Returns:
        A tree of layers with evaluation behavior of same structure as ``tree``.

    Example:
        >>> # dropout is replaced by an identity layer in evaluation mode
        >>> # by registering `tree_eval.def_eval(sk.nn.Dropout, sk.nn.Identity)`
        >>> import jax.numpy as jnp
        >>> import serket as sk
        >>> layer = sk.nn.Dropout(0.5)
        >>> sk.tree_eval(layer)
        Identity()
    """

    types = tuple(set(tree_eval.eval_dispatcher.registry) - {object})

    def is_leaf(x: Callable[[Any], bool]) -> bool:
        return isinstance(x, types)

    return jax.tree_map(tree_eval.eval_dispatcher, tree, is_leaf=is_leaf)


tree_eval.eval_dispatcher = ft.singledispatch(lambda x: x)
tree_eval.def_eval = tree_eval.eval_dispatcher.register
