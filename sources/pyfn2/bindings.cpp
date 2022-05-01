#include <boost/python.hpp>
#include <iostream>

#include <FastNoise/FastNoise.h>

using namespace boost::python;
using namespace FastNoise;

static void hello()
{
    std::cout << "Hello from pyfn2 binding module!"<< std::endl;
}


// cf. https://stackoverflow.com/questions/14355441/using-custom-smart-pointers-in-boost-python
// cf. http://pyplusplus.readthedocs.io/en/latest/troubleshooting_guide/smart_ptrs/bindings.cpp.html
// cf. http://boost.org/libs/python/doc/v2/register_ptr_to_python.html
// cf. https://stackoverflow.com/questions/18720165/smart-pointer-casting-in-boostpython


// some boost.python plumbing is required as you already know
namespace boost {
    namespace python {

    // here comes the magic
    template <typename T> T* get_pointer(SmartNode<T> const& p) {
        //notice the const_cast<> at this point
        //for some unknown reason, bp likes to have it like that
        return const_cast<T*>(p.get());
    }

    template <typename T> struct pointee<SmartNode<T> > {
        typedef T type;
    };

    } 
}

// auto fnSimplex = FastNoise::New<FastNoise::Simplex>();

template<typename T>
static SmartNode<T> NewNode()
{
    return New<T>();
}

template<typename T>
static void SetSource(T* dest_node, Generator* src_node)
{
    SmartNode<Generator> sptr;
    sptr.reset(src_node);
    dest_node->SetSource(sptr);
}

static void SetDomainOffsetFloat(DomainOffset* self, Dim dim, float value)
{
    switch(dim)
    {
    case Dim::X: return self->SetOffset<Dim::X>(value);
    case Dim::Y: return self->SetOffset<Dim::Y>(value);
    case Dim::Z: return self->SetOffset<Dim::Z>(value);
    default: return self->SetOffset<Dim::W>(value);
    }
}

static void SetDomainOffsetSource(DomainOffset* self, Dim dim, Generator* src_node)
{
    SmartNode<Generator> sptr;
    sptr.reset(src_node);

    switch(dim)
    {
    case Dim::X: return self->SetOffset<Dim::X>(sptr);
    case Dim::Y: return self->SetOffset<Dim::Y>(sptr);
    case Dim::Z: return self->SetOffset<Dim::Z>(sptr);
    default: return self->SetOffset<Dim::W>(sptr);
    }
}

BOOST_PYTHON_MODULE(pyfn2)
{

    def("hello", hello);

    enum_<FastSIMD::eLevel>("eLevel")
        .value("Null", FastSIMD::Level_Null)
        .value("Scalar", FastSIMD::Level_Scalar)
        .value("SSE", FastSIMD::Level_SSE)
        .value("SSE2", FastSIMD::Level_SSE2)
        .value("SSE3", FastSIMD::Level_SSE3)
        .value("SSSE3", FastSIMD::Level_SSSE3)
        .value("SSE41", FastSIMD::Level_SSE41)
        .value("SSE42", FastSIMD::Level_SSE42)
        .value("AVX", FastSIMD::Level_AVX)
        .value("AVX2", FastSIMD::Level_AVX2)
        .value("AVX512", FastSIMD::Level_AVX512)
        .value("NEON", FastSIMD::Level_NEON);

    enum_<FastNoise::Dim>("Dim")
        .value("X", FastNoise::Dim::X)
        .value("Y", FastNoise::Dim::Y)
        .value("Z", FastNoise::Dim::Z)
        .value("W", FastNoise::Dim::W);

    class_<Generator, SmartNode<Generator>, boost::noncopyable>("Generator", no_init)
        .def("GetSIMDLevel", &Generator::GetSIMDLevel)
    ;

    class_<Simplex, SmartNode<Simplex>, bases<Generator>, boost::noncopyable>("Simplex", no_init)
        .def("New", &NewNode<Simplex>).staticmethod("New")
        ;

    class_<OpenSimplex2, SmartNode<OpenSimplex2>, bases<Generator>, boost::noncopyable>("OpenSimplex2", no_init)
        .def("New", &NewNode<OpenSimplex2>).staticmethod("New")
        ;
    
    class_<Perlin, SmartNode<Perlin>, bases<Generator>, boost::noncopyable>("Perlin", no_init)
        .def("New", &NewNode<Perlin>).staticmethod("New")
        ;

    class_<Value, SmartNode<Value>, bases<Generator>, boost::noncopyable>("Value", no_init)
        .def("New", &NewNode<Value>).staticmethod("New")
        ;

    class_<DomainScale, SmartNode<DomainScale>, bases<Generator>, boost::noncopyable>("DomainScale", no_init)
        .def("New", &NewNode<DomainScale>).staticmethod("New")
        .def("SetSource", &SetSource<DomainScale>)
        .def("SetScale", &DomainScale::SetScale)
        ;

    class_<DomainOffset, SmartNode<DomainOffset>, bases<Generator>, boost::noncopyable>("DomainOffset", no_init)
        .def("New", &NewNode<DomainOffset>).staticmethod("New")
        .def("SetSource", &SetSource<DomainOffset>)
        .def("SetOffsetFloat", &SetDomainOffsetFloat)
        .def("SetOffsetSource", &SetDomainOffsetSource)
        ;

    // implicitly_convertible< SmartNode<Simplex>, SmartNode<Generator> >();
    // implicitly_convertible< SmartNode<OpenSimplex2>, SmartNode<Generator> >();
    // implicitly_convertible< SmartNode<Perlin>, SmartNode<Generator> >();
    // implicitly_convertible< SmartNode<Value>, SmartNode<Generator> >();
    // implicitly_convertible< SmartNode<DomainScale>, SmartNode<Generator> >();
};
