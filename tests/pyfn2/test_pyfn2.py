"""Test module for pyfn2 module"""

# import sys
# print(sys.path)
import numpy as np
from dist.bin import pyfn2


class TestBindings():
    """Test class pyfn2 bindings"""

    def test_sanity(self):
        """Sanity check"""
        assert 1 == 1

    def test_hello(self):
        """Test simple hello function"""
        pyfn2.hello()

    def test_simplex(self):
        """Test create a simplex object"""
        node = pyfn2.Simplex.New()

        # get the SIMD level:
        lvl = node.GetSIMDLevel()
        print(f"Simplex SIMD level: {lvl}")
        assert lvl >= 0

    def test_opensimplex2(self):
        """Test create a opensimplex2 object"""
        node = pyfn2.OpenSimplex2.New()

        lvl = node.GetSIMDLevel()
        print(f"OpenSimplex2 SIMD level: {lvl}")
        assert lvl >= 0

    def test_perlin(self):
        """Test create a Perlin object"""
        node = pyfn2.Perlin.New()

        lvl = node.GetSIMDLevel()
        print(f"Perlin SIMD level: {lvl}")
        assert lvl >= 0

    def test_value(self):
        """Test create a Value object"""
        node = pyfn2.Value.New()

        lvl = node.GetSIMDLevel()
        print(f"Value SIMD level: {lvl}")
        assert lvl >= 0

    def test_domain_scale(self):
        """Test create a DomainScale object"""
        node = pyfn2.DomainScale.New()
        src = pyfn2.Simplex.New()
        node.SetSource(src)
        node.SetScale(3.0)

        lvl = node.GetSIMDLevel()
        print(f"DomainScale SIMD level: {lvl}")
        assert lvl >= 0

    def test_domain_offset(self):
        """Test create a DomainOffset object"""
        node = pyfn2.DomainOffset.New()
        src = pyfn2.Simplex.New()
        src2 = pyfn2.Perlin.New()
        node.SetSource(src)
        node.SetOffset(pyfn2.Dim.X, 2.0)
        node.SetOffset(pyfn2.Dim.Y, 2.5)
        node.SetOffset(pyfn2.Dim.Z, 3.5)
        node.SetOffset(pyfn2.Dim.Z, src2)

        lvl = node.GetSIMDLevel()
        print(f"DomainOffset SIMD level: {lvl}")
        assert lvl >= 0

    def test_domain_rotate(self):
        """Test create a DomainRotate object"""
        node = pyfn2.DomainRotate.New()
        src = pyfn2.Simplex.New()
        node.SetSource(src)
        node.SetYaw(0.1)
        node.SetPitch(0.2)
        node.SetRoll(0.3)

        lvl = node.GetSIMDLevel()
        print(f"DomainRotate SIMD level: {lvl}")
        assert lvl >= 0

    def test_seed_offset(self):
        """Test create a SeedOffset object"""
        node = pyfn2.SeedOffset.New()
        src = pyfn2.Simplex.New()
        node.SetSource(src)
        node.SetOffset(3)

        lvl = node.GetSIMDLevel()
        print(f"SeedOffset SIMD level: {lvl}")
        assert lvl >= 0

    def test_remap(self):
        """Test create a Remap object"""
        node = pyfn2.Remap.New()
        src = pyfn2.Simplex.New()
        node.SetSource(src)
        node.SetRemap(-0.5, 0.5, 0.0, 3.0)

        lvl = node.GetSIMDLevel()
        print(f"Remap SIMD level: {lvl}")
        assert lvl >= 0

    def test_convert_rgba8(self):
        """Test create a ConvertRGBA8 object"""
        node = pyfn2.ConvertRGBA8.New()
        src = pyfn2.Simplex.New()
        node.SetSource(src)
        node.SetMinMax(0.0, 0.8)

        lvl = node.GetSIMDLevel()
        print(f"ConvertRGBA8 SIMD level: {lvl}")
        assert lvl >= 0

    def test_terrace(self):
        """Test create a Terrace object"""
        node = pyfn2.Terrace.New()
        src = pyfn2.Simplex.New()
        node.SetSource(src)
        node.SetMultiplier(3.0)
        node.SetSmoothness(0.4)

        lvl = node.GetSIMDLevel()
        print(f"Terrace SIMD level: {lvl}")
        assert lvl >= 0

    def test_domain_axis_scale(self):
        """Test create a DomainAxisScale object"""
        node = pyfn2.DomainAxisScale.New()
        src = pyfn2.Simplex.New()
        node.SetSource(src)
        node.SetScale(pyfn2.Dim.X, 2.0)
        node.SetScale(pyfn2.Dim.Y, 2.5)
        node.SetScale(pyfn2.Dim.Z, 3.5)
        node.SetScale(pyfn2.Dim.W, 4.5)

        lvl = node.GetSIMDLevel()
        print(f"DomainAxisScale SIMD level: {lvl}")
        assert lvl >= 0

    def test_add_dimension(self):
        """Test create a AddDimension object"""
        node = pyfn2.AddDimension.New()
        src = pyfn2.Simplex.New()
        src2 = pyfn2.Perlin.New()
        node.SetSource(src)
        node.SetNewDimensionPosition(3.0)
        node.SetNewDimensionPosition(src2)

        lvl = node.GetSIMDLevel()
        print(f"AddDimension SIMD level: {lvl}")
        assert lvl >= 0

    def test_remove_dimension(self):
        """Test create a RemoveDimension object"""
        node = pyfn2.RemoveDimension.New()
        src = pyfn2.Simplex.New()
        node.SetSource(src)
        node.SetRemoveDimension(pyfn2.Dim.W)

        lvl = node.GetSIMDLevel()
        print(f"RemoveDimension SIMD level: {lvl}")
        assert lvl >= 0

    def test_generator_cache(self):
        """Test create a GeneratorCache object"""
        node = pyfn2.GeneratorCache.New()
        src = pyfn2.Simplex.New()
        node.SetSource(src)

        lvl = node.GetSIMDLevel()
        print(f"GeneratorCache SIMD level: {lvl}")
        assert lvl >= 0

    def test_generator_gen2d(self):
        """Test generate on 2d grid"""

        arr = np.zeros((10, 10), dtype=np.float32)

        node = pyfn2.Simplex.New()
        offset = pyfn2.DomainOffset.New()
        offset.SetSource(node)
        offset.SetOffset(pyfn2.Dim.X, 2.0)
        offset.SetOffset(pyfn2.Dim.Y, 2.0)
        nrange = offset.GenUniformGrid2D(arr, 0, 0, 10, 10, 1.0, 123)
        # node.GenUniformGrid2D(0, 0, 10, 10, 0.1, 123)
        print(f"Generated array is: {arr}")
        print(f"Range is: {nrange}")
        mini = np.amin(arr)
        maxi = np.amax(arr)
        assert nrange[0] == mini
        assert nrange[1] == maxi
