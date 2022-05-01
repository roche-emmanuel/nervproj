"""Test module for pyfn2 module"""

# import sys
# print(sys.path)
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

    # def test_domain_scale(self):
    #     """Test create a DomainScale object"""
    #     node = pyfn2.DomainScale.New()
    #     src = pyfn2.Simplex.New()
    #     node.SetSource(src)
    #     node.SetScale(3.0)

    #     lvl = node.GetSIMDLevel()
    #     print(f"DomainScale SIMD level: {lvl}")
    #     assert lvl >= 0
