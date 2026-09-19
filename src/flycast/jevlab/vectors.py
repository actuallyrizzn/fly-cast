"""GloVe load and the fixed projection onto inject neurons.

embed_dim is always equal to inject_count. FlyBrain.inject_token maps
vec[i % len(vec)] onto inject neuron i, and FastReservoir.inject_m does the
same. With dim == inject_count every inject neuron gets exactly one dimension.
Do not set embed_dim to 100.
"""

__all__: list[str] = []
