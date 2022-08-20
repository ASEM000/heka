from typing import Callable, Sequence

import jax
import jax.numpy as jnp
import jax.random as jr
import pytreeclass as pytc


@pytc.treeclass
class Linear:
    weight: jnp.ndarray
    bias: jnp.ndarray

    in_features: int = pytc.static_field()
    out_features: int = pytc.static_field()
    weight_init_func: Callable = pytc.static_field()
    bias_init_func: Callable = pytc.static_field()

    def __init__(
        self,
        in_features: int,
        out_features: int,
        *,
        weight_init_func: Callable = jax.nn.initializers.he_normal(),
        bias_init_func: Callable = lambda key, shape: jnp.ones(shape),
        key: jr.PRNGKey = jr.PRNGKey(0),
    ):

        self.in_features = in_features
        self.out_features = out_features
        self.weight_init_func = weight_init_func
        self.bias_init_func = bias_init_func

        self.weight = weight_init_func(key, (in_features, out_features))
        self.bias = (
            bias_init_func(key, (out_features,)) if (bias_init_func is not None) else 0
        )

    def __call__(self, x):
        return x @ self.weight + self.bias


@pytc.treeclass
class MLP:
    act_func: Callable = pytc.static_field()
    names: Sequence[str] = pytc.static_field(repr=False)

    def __init__(
        self,
        layers,
        *,
        act_func: Callable = jax.nn.relu,
        weight_init_func: Callable = jax.nn.initializers.he_normal(),
        bias_init_func: Callable = lambda key, shape: jnp.ones(shape),
        key=jr.PRNGKey(0),
    ):

        keys = jr.split(key, len(layers))
        self.names = []
        self.act_func = act_func

        # Done like this for better __repr__/summary/tree_diagram
        # in essence instead of using a python container (list/tuple) to store the layers
        # we register each layer to the class
        for i, (ki, in_dim, out_dim) in enumerate(zip(keys, layers[:-1], layers[1:])):
            self.register_node(
                Linear(
                    in_dim,
                    out_dim,
                    weight_init_func=weight_init_func,
                    bias_init_func=bias_init_func,
                    key=ki,
                ),
                name=f"Linear_{i}",
            )
            self.names.append(f"Linear_{i}")

    def __call__(self, x):
        for name in self.names[:-1]:
            x = self.__dict__[name](x)
            x = self.act_func(x)
        return self.__dict__[self.names[-1]](x)
