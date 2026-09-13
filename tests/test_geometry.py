import itertools
import numpy as np
import pytest
from materials_structure_core import minimum_image_in_plane, plane_frame


def test_skew_image_and_nonperiodic_direction():
    cell = np.array([[3.,0,0],[2.7,1.3,0],[4,0,20]])
    v = np.array([.49,.49,0]) @ cell
    result, image = minimum_image_in_plane(v, cell)
    assert np.linalg.norm(result) == pytest.approx(.66949085131912)
    np.testing.assert_allclose(result, v-image@cell[:2])
    result, _ = minimum_image_in_plane([0,0,39], cell)
    assert result[2] == 39


def test_random_oracle_and_large_integer_rebasis():
    rng = np.random.default_rng(734)
    base = np.array([[3.,0,0],[.7,2.,0],[0,0,20.]])
    vectors = rng.uniform(-2,2,(80,3))
    shifts = np.array(list(itertools.product(range(-5,6),repeat=2)))
    expected = np.min(np.linalg.norm(vectors[:,None]-shifts@base[:2],axis=2),axis=1)
    # Equivalent, very unreduced lattice: a' = a + 37 b.
    rebased = base.copy(); rebased[0] += 37*base[1]
    for cell in [base, rebased]:
        result, images = minimum_image_in_plane(vectors,cell,block_size=7)
        np.testing.assert_allclose(np.linalg.norm(result,axis=1),expected,atol=1e-10)
        np.testing.assert_allclose(result,vectors-images@cell[:2],atol=1e-10)


def test_rotation_frame_empty_and_invalid():
    cell=np.diag([3.,4.,20.])
    q,_=np.linalg.qr(np.random.default_rng(1).normal(size=(3,3)))
    v=np.array([2.,3.,5.])
    a,_=minimum_image_in_plane(v,cell)
    b,_=minimum_image_in_plane(v@q,cell@q)
    np.testing.assert_allclose(b,a@q,atol=1e-12)
    f=plane_frame(cell@q)
    np.testing.assert_allclose(f.T@f,np.eye(3),atol=1e-12)
    assert minimum_image_in_plane(np.empty((0,3)),cell)[0].shape==(0,3)
    with pytest.raises(ValueError): minimum_image_in_plane(v,[[1,0,0],[2,0,0]])
