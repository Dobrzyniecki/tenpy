"""Provide test configuration for backends etc."""
# Copyright 2023-2023 TeNPy Developers, GNU GPLv3

import numpy as np
import pytest

from tenpy.linalg import backends
from tenpy.linalg.symmetries import groups, spaces
from tenpy.linalg import tensors
from tenpy.linalg.backends.abstract_backend import Dtype


@pytest.fixture
def np_random() -> np.random.Generator:
    return np.random.default_rng(seed=12345)


@pytest.fixture(params=[groups.no_symmetry,
                        groups.u1_symmetry,
                        groups.z2_symmetry,
                        groups.ZNSymmetry(4, "My_Z4_symmetry"),
                        groups.ProductSymmetry([groups.u1_symmetry, groups.z3_symmetry]),
                        # groups.su2_symmetry,  # TODO reintroduce once SU2 is implemented
                        ],
                ids=repr)
def symmetry(request):
    return request.param


@pytest.fixture(params=[spaces.VectorSpace, backends.abelian.AbelianBackendVectorSpace],
                ids=lambda cls: cls.__name__)
def VectorSpace(request):
    return request.param


@pytest.fixture(ids=lambda cls:cls.__name__)
def ProductSpace(VectorSpace):
    return VectorSpace.ProductSpace


def random_symmetry_sectors(symmetry: groups.Symmetry, np_random: np.random.Generator, len_=None) -> groups.SectorArray:
    """random non-sorted, but unique symmetry sectors"""
    if len_ is None:
        len_ = np_random.integers(3,7)
    if isinstance(symmetry, groups.SU2Symmetry):
        return np.arange(0, 2*len_, 2, dtype=int)[:, np.newaxis]
    elif isinstance(symmetry, groups.U1Symmetry):
        vals = list(range(-len_, len_)) + [123]
        return np_random.choice(vals, replace=False, size=(len_, 1))
    elif symmetry.num_sectors < np.inf:
        if symmetry.num_sectors <= len_:
            return symmetry.all_sectors()
        return np_random.choice(symmetry.all_sectors(), size=len_)
    elif isinstance(symmetry, groups.ProductSymmetry):
        factor_len = max(3, len_ // len(symmetry.factors))
        factor_sectors = [random_symmetry_sectors(factor, np_random, factor_len)
                          for factor in symmetry.factors]
        combs = np.indices([len(s) for s in factor_sectors]).T.reshape((-1, len(factor_sectors)))
        if len(combs) > len_:
            combs = np_random.choice(combs, replace=False, size=len_)
        res = np.hstack([fs[i] for fs, i in zip(factor_sectors, combs.T)])
        return res
    pytest.skip("don't know how to get symmetry sectors")  # raises Skipped


@pytest.fixture
def symmetry_sectors_rng(symmetry, np_random):
    def generator(size: int):
        """generate random symmetry sectors"""
        return random_symmetry_sectors(symmetry, np_random, len_=size)
    return generator


def random_vector_space(symmetry, max_num_blocks=5, max_block_size=5, np_random=None, VectorSpace=spaces.VectorSpace):
    if np_random is None:
        np_ranodm = np.random.default_rng()
    len_ = np_random.integers(1, max_num_blocks, endpoint=True)
    sectors = random_symmetry_sectors(symmetry, np_random, len_)
    mults = np_random.integers(1, max_block_size, size=(len(sectors),), endpoint=True)
    dual = np_random.random() < 0.5
    return VectorSpace(symmetry, sectors, mults, is_real=False, _is_dual=dual)


@pytest.fixture
def vector_space_rng(symmetry, symmetry_sectors_rng, np_random):
    def generator(max_num_blocks: int = 4, max_block_size=8, VectorSpace=spaces.VectorSpace):
        """generate random spaces.VectorSpace instances."""
        return random_vector_space(symmetry, max_num_blocks, max_block_size, np_random, VectorSpace)
    return generator


@pytest.fixture
def default_backend():
    return backends.backend_factory.get_default_backend()


@pytest.fixture(params=['numpy']) # TODO: reintroduce 'torch'])
def block_backend(request):
    if request.param == 'torch':
        torch = pytest.importorskip('torch', reason='torch not installed')
    return request.param


@pytest.fixture
def backend(symmetry, block_backend):
    return backends.backend_factory.get_backend(symmetry, block_backend)


@pytest.fixture
def block_rng(backend, np_random):
    def generator(size, real=True):
        block = np_random.normal(size=size)
        if not real:
            block = block + 1.j * np_random.normal(size=size)
        return backend.block_from_numpy(block)
    return generator


@pytest.fixture
def backend_data_rng(backend, block_rng, np_random):
    def generator(legs, real=True):
        data = backend.from_block_func(block_rng, legs, func_kwargs=dict(real=real))
        if isinstance(backend, backends.abelian.AbstractAbelianBackend):
            if np_random.random() < 0.5:  # with 50% probability
                # keep roughly half of the blocks
                keep = (np_random.random(len(data.blocks)) < 0.5)
                data.blocks = [block for block, k in zip(data.blocks, keep) if k]
                data.block_inds = data.block_inds[keep]
        return data
    return generator


@pytest.fixture
def tensor_rng(backend, backend_data_rng, vector_space_rng):
    def generator(legs=None, num_legs=2, labels=None, max_num_blocks=5, max_block_size=5, real=True):
        if labels is not None:
            num_legs = len(labels)
        if legs is None:
            legs = [vector_space_rng(max_num_blocks, max_block_size, backend.VectorSpaceCls)
                    for _ in range(num_legs)]
        else:
            legs = list(legs)
            for i, leg in enumerate(legs):
                if leg is None:
                    legs[i] = vector_space_rng(max_num_blocks, max_block_size, backend.VectorSpaceCls)
                else:
                    legs[i] = backend.convert_vector_space(leg)
        data = backend_data_rng(legs, real=real)
        return tensors.Tensor(data, backend=backend, legs=legs, labels=labels)
    return generator