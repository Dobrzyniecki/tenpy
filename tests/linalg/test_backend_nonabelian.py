"""A collection of tests for tenpy.linalg.backends.nonabelian"""
# Copyright (C) TeNPy Developers, GNU GPLv3
from tenpy.linalg.backends import nonabelian, get_backend
from tenpy.linalg.spaces import ProductSpace


def test_block_sizes(symmetry, block_backend, vector_space_rng, symmetry_sectors_rng, np_random,
                     num_spaces=4):
    backend = get_backend('nonabelian', block_backend)

    are_dual = np_random.choice([True, False], size=num_spaces)
    spaces = [vector_space_rng(is_dual=is_dual) for is_dual in are_dual]
    domain = ProductSpace(spaces, backend, symmetry)

    for coupled in symmetry_sectors_rng(10):
        expect = sum(nonabelian.forest_block_size(domain, uncoupled, coupled)
                    for uncoupled in domain.iter_uncoupled())
        res = nonabelian.block_size(domain, coupled)
        assert res == expect
