# Copyright 2023-2023 TeNPy Developers, GNU GPLv3
import pytest
import numpy as np
from numpy.testing import assert_array_equal

from tenpy.linalg.symmetries import spaces, groups
from tenpy.linalg.backends import abelian


symmetries = dict(
    no_symmetry=groups.no_symmetry,
    z4=groups.z4_symmetry,
    z4_named=groups.ZNSymmetry(4, 'foo'),
    z4_z5=groups.z4_symmetry * groups.z5_symmetry,
    z4_z5_named=groups.ZNSymmetry(4, 'foo') * groups.ZNSymmetry(5, 'bar'),
    # su2=groups.su2_symmetry,  # TODO (JU) : reintroduce once n symbol is implemented
)


def _get_four_sectors(symm: groups.Symmetry) -> groups.SectorArray:
    if isinstance(symm, groups.SU2Symmetry):
        res = np.arange(0, 8, 2, dtype=int)[:, None]
    elif symm.num_sectors >= 8:
        res = symm.all_sectors()[:8:2]
    elif symm.num_sectors >= 4:
        res = symm.all_sectors()[:4]
    else:
        res = np.tile(symm.all_sectors()[:, 0], 4)[:4, None]
    assert res.shape == (4, symm.sector_ind_len)
    return res


def test_vector_space(symmetry, symmetry_sectors_rng, np_random):
    sectors = symmetry_sectors_rng(10)
    mults = np_random.integers(1, 10, size=len(sectors))

    # TODO (JU) test real (as in "not complex") vectorspaces

    s1 = spaces.VectorSpace(symmetry=symmetry, sectors=sectors, multiplicities=mults)
    s2 = spaces.VectorSpace.without_symmetry(dim=8)

    print('checking VectorSpace.sectors')
    assert_array_equal(s2.sectors, groups.no_symmetry.trivial_sector[None, :])
    assert_array_equal(s1.dual.sectors, symmetry.dual_sectors(s1.sectors))

    print('checking str and repr')
    _ = str(s1)
    _ = str(s2)
    _ = repr(s1)
    _ = repr(s2)

    print('checking duality and equality')
    assert s1 == s1
    assert s1 != s1.dual
    assert s1 != s2
    wrong_mults = mults.copy()
    if len(mults) > 2:
        wrong_mults[-2] += 1
    else:
        wrong_mults[0] += 1
    assert s1 != spaces.VectorSpace(symmetry=symmetry, sectors=sectors, multiplicities=wrong_mults)
    assert s1.dual == spaces.VectorSpace(symmetry=symmetry, sectors=sectors, multiplicities=mults,
                                         _is_dual=True)
    assert s1.can_contract_with(s1.dual)
    assert not s1.can_contract_with(s1)
    assert not s1.can_contract_with(s2)

    print('checking is_trivial')
    assert not s1.is_trivial
    assert not s2.is_trivial
    assert spaces.VectorSpace.without_symmetry(dim=1).is_trivial
    assert spaces.VectorSpace(symmetry=symmetry, sectors=symmetry.trivial_sector[np.newaxis, :]).is_trivial

    print('checking is_subspace_of')
    print(f'{len(sectors)=}')
    same_sectors_less_mults = spaces.VectorSpace(
        symmetry=symmetry, sectors=sectors, multiplicities=[max(1, m - 1) for m in mults]
    )
    same_sectors_different_mults = spaces.VectorSpace(
       symmetry=symmetry, sectors=sectors,
       multiplicities=[max(1, m + (+1 if i % 2 == 0 else -1)) for i, m in enumerate(mults)]
    )  # but at least one mult is larger than for s1
    if len(sectors) > 2:
        which1 = [0, -1]
        which2 = [1, -2]
    else:
        # if there are only two sectors, we cant have different sets of sectors,
        # both of which have multiple entries
        which1 = [0]
        which2 = [-1]
    fewer_sectors1 = spaces.VectorSpace(symmetry=symmetry, sectors=[sectors[i] for i in which1],
                                        multiplicities=[mults[i] for i in which1])
    fewer_sectors2 = spaces.VectorSpace(symmetry=symmetry, sectors=[sectors[i] for i in which2],
                                        multiplicities=[mults[i] for i in which2])
    assert s1.is_subspace_of(s1)
    assert not s1.dual.is_subspace_of(s1)
    assert same_sectors_less_mults.is_subspace_of(s1)
    assert not s1.is_subspace_of(same_sectors_less_mults)
    assert not same_sectors_different_mults.is_subspace_of(s1)
    assert len(sectors) == 1 or not s1.is_subspace_of(same_sectors_different_mults)
    assert fewer_sectors1.is_subspace_of(s1)
    if len(sectors) == 1:
        # if there is only one sector, the "fewer_sectors*" spaces dont actually have fewer sectors
        # and are both equal to s1
        assert s1.is_subspace_of(fewer_sectors1)
        assert fewer_sectors1.is_subspace_of(fewer_sectors2)
        assert fewer_sectors2.is_subspace_of(fewer_sectors1)
    else:
        assert not s1.is_subspace_of(fewer_sectors1)
        assert not fewer_sectors1.is_subspace_of(fewer_sectors2)
        assert not fewer_sectors2.is_subspace_of(fewer_sectors1)

    # TODO (JU) test num_parameters when ready

    print('check idx_to_sector and parse_idx')
    idx = 0
    for n, s in enumerate(s1.sectors):
        for m in range(s1.multiplicities[n]):
            sector_idx, mult_idx = s1.parse_index(idx)
            assert sector_idx == n
            assert mult_idx == m
            assert np.all(s1.idx_to_sector(idx) == s)
            idx += 1

    print('check sector lookup')
    for expect in [2, 3, 4]:
        expect = expect % s1.num_sectors
        assert s1.sectors_where(s1.sectors[expect]) == expect
        assert s1._non_dual_sorted_sectors_where(s1._non_dual_sorted_sectors[expect]) == expect
        assert s1.sector_multiplicity(s1.sectors[expect]) == s1.multiplicities[expect]


def test_product_space(symmetry, symmetry_sectors_rng, np_random):
    sectors = symmetry_sectors_rng(10)
    mults = np_random.integers(1, 10, size=len(sectors))

    # TODO (JU) test real (as in "not complex") vectorspaces

    s1 = spaces.VectorSpace(symmetry=symmetry, sectors=sectors, multiplicities=mults)
    s2 = spaces.VectorSpace(symmetry=symmetry, sectors=sectors[:2], multiplicities=mults[:2])
    s3 = spaces.VectorSpace(symmetry=symmetry, sectors=sectors[::2], multiplicities=mults[::2])

    p1 = spaces.ProductSpace([s1, s2, s3])
    p2 = spaces.ProductSpace([s1, s2])
    p3 = spaces.ProductSpace([spaces.ProductSpace([s1, s2]), s3])

    assert_array_equal(p1.sectors, p3.sectors)

    _ = str(p1)
    _ = str(p3)
    _ = repr(p1)
    _ = repr(p3)

    assert p1 == p1
    assert p1 != s1
    assert s1 != p1
    assert p1 != p3
    assert p2 == spaces.ProductSpace([s1.dual, s2.dual], _is_dual=True).dual
    for p in [p1, p2, p3]:
        assert p.can_contract_with(p.dual)
    assert p2 == spaces.ProductSpace([s1, s2], _is_dual=True).flip_is_dual()
    assert p2.can_contract_with(spaces.ProductSpace([s1.dual, s2.dual], _is_dual=False).flip_is_dual())
    assert p2.can_contract_with(spaces.ProductSpace([s1.dual, s2.dual]))  # check default _is_dual
    assert p2.can_contract_with(spaces.ProductSpace([s1.dual, s2.dual], _is_dual=True))
    p1_s = p1.as_VectorSpace()
    assert isinstance(p1_s, spaces.VectorSpace)
    assert p1_s.is_equal_or_dual(p1)  # this function does not check ProductSpace vs VectorSpace
    assert p1_s != p1  # but direct comparison does
    assert p1 != p1_s


def all_str_repr_demos():
    # python -c "import test_spaces; test_spaces.all_str_repr_demos()"
    print()
    print('----------------------')
    print('VectorSpace.__repr__()')
    print('----------------------')
    demo_VectorSpace_repr(repr)
    
    print()
    print('---------------------')
    print('VectorSpace.__str__()')
    print('---------------------')
    demo_VectorSpace_repr(str)
    
    print()
    print('-----------------------')
    print('ProductSpace.__repr__()')
    print('-----------------------')
    demo_ProductSpace_repr(repr)
    
    print()
    print('----------------------')
    print('ProductSpace.__str__()')
    print('----------------------')
    demo_ProductSpace_repr(str)


def demo_VectorSpace_repr(fun=repr):
    from tests.linalg import conftest
    for symmetry in conftest.symmetry._pytestfixturefunction.params:
        space = conftest.random_vector_space(symmetry, max_num_blocks=20)
        print()
        print(fun(space))


def demo_ProductSpace_repr(fun=repr):
    from tests.linalg import conftest
    for symmetry in conftest.symmetry._pytestfixturefunction.params:
        num = 1 + np.random.choice(3)
        is_dual = np.random.choice([True, False, None])
        spaces_ = [conftest.random_vector_space(symmetry) for _ in range(num)]
        space = spaces.ProductSpace(spaces_, _is_dual=is_dual)
        print()
        print(fun(space))
