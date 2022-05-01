#include <boost/python.hpp>
#include <boost/python/numpy.hpp>
#include <iostream>

#include <FastNoise/FastNoise.h>

using namespace boost::python;
using namespace FastNoise;
namespace np = boost::python::numpy;

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

static void SetDomainAxisScale(DomainAxisScale* self, Dim dim, float value)
{
    switch(dim)
    {
    case Dim::X: return self->SetScale<Dim::X>(value);
    case Dim::Y: return self->SetScale<Dim::Y>(value);
    case Dim::Z: return self->SetScale<Dim::Z>(value);
    default: return self->SetScale<Dim::W>(value);
    }
}

static void SetNewDimensionPosition(AddDimension* self, Generator* src_node)
{
    SmartNode<Generator> sptr;
    sptr.reset(src_node);
    self->SetNewDimensionPosition(sptr);
}

// cf. https://cosmiccoding.com.au/tutorials/boost
static tuple GenUniformGrid2D(Generator* self, np::ndarray & array, 
                             int xStart, int yStart,
                             int xSize,  int ySize,
                             float frequency, int seed )
{
    // Make sure we get doubles
    if (array.get_dtype() != np::dtype::get_builtin<float>()) {
        PyErr_SetString(PyExc_TypeError, "Incorrect array data type");
        throw_error_already_set();
    }
    
    float* data = reinterpret_cast<float*>(array.get_data());
    OutputMinMax res = self->GenUniformGrid2D(data, xStart, yStart, xSize, ySize, frequency, seed);

     tuple minmax = make_tuple(res.min, res.max);
     return minmax;
}

BOOST_PYTHON_MODULE(pyfn2)
{
    Py_Initialize();
    np::initialize();

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
        .def("GenUniformGrid2D", &GenUniformGrid2D)
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
        .def("SetOffset", &SetDomainOffsetFloat)
        .def("SetOffset", &SetDomainOffsetSource)
        ;

    class_<DomainRotate, SmartNode<DomainRotate>, bases<Generator>, boost::noncopyable>("DomainRotate", no_init)
        .def("New", &NewNode<DomainRotate>).staticmethod("New")
        .def("SetSource", &SetSource<DomainRotate>)
        .def("SetYaw", &DomainRotate::SetYaw)
        .def("SetPitch", &DomainRotate::SetPitch)
        .def("SetRoll", &DomainRotate::SetRoll)
        ;

    class_<SeedOffset, SmartNode<SeedOffset>, bases<Generator>, boost::noncopyable>("SeedOffset", no_init)
        .def("New", &NewNode<SeedOffset>).staticmethod("New")
        .def("SetSource", &SetSource<SeedOffset>)
        .def("SetOffset", &SeedOffset::SetOffset)
        ;

    class_<Remap, SmartNode<Remap>, bases<Generator>, boost::noncopyable>("Remap", no_init)
        .def("New", &NewNode<Remap>).staticmethod("New")
        .def("SetSource", &SetSource<Remap>)
        .def("SetRemap", &Remap::SetRemap)
        ;

    class_<ConvertRGBA8, SmartNode<ConvertRGBA8>, bases<Generator>, boost::noncopyable>("ConvertRGBA8", no_init)
        .def("New", &NewNode<ConvertRGBA8>).staticmethod("New")
        .def("SetSource", &SetSource<ConvertRGBA8>)
        .def("SetMinMax", &ConvertRGBA8::SetMinMax)
        ;

    class_<Terrace, SmartNode<Terrace>, bases<Generator>, boost::noncopyable>("Terrace", no_init)
        .def("New", &NewNode<Terrace>).staticmethod("New")
        .def("SetSource", &SetSource<Terrace>)
        .def("SetMultiplier", &Terrace::SetMultiplier)
        .def("SetSmoothness", &Terrace::SetSmoothness)
        ;

    class_<DomainAxisScale, SmartNode<DomainAxisScale>, bases<Generator>, boost::noncopyable>("DomainAxisScale", no_init)
        .def("New", &NewNode<DomainAxisScale>).staticmethod("New")
        .def("SetSource", &SetSource<DomainAxisScale>)
        .def("SetScale", &SetDomainAxisScale)
        ;

    class_<AddDimension, SmartNode<AddDimension>, bases<Generator>, boost::noncopyable>("AddDimension", no_init)
        .def("New", &NewNode<AddDimension>).staticmethod("New")
        .def("SetSource", &SetSource<AddDimension>)
        .def<void (AddDimension::*)(float)>("SetNewDimensionPosition", &AddDimension::SetNewDimensionPosition)
        .def("SetNewDimensionPosition", &SetNewDimensionPosition)
        ;

    class_<RemoveDimension, SmartNode<RemoveDimension>, bases<Generator>, boost::noncopyable>("RemoveDimension", no_init)
        .def("New", &NewNode<RemoveDimension>).staticmethod("New")
        .def("SetSource", &SetSource<RemoveDimension>)
        .def("SetRemoveDimension", &RemoveDimension::SetRemoveDimension)
        ;

    class_<GeneratorCache, SmartNode<GeneratorCache>, bases<Generator>, boost::noncopyable>("GeneratorCache", no_init)
        .def("New", &NewNode<GeneratorCache>).staticmethod("New")
        .def("SetSource", &SetSource<GeneratorCache>)
        ;

    // implicitly_convertible< SmartNode<Simplex>, SmartNode<Generator> >();
    // implicitly_convertible< SmartNode<OpenSimplex2>, SmartNode<Generator> >();
    // implicitly_convertible< SmartNode<Perlin>, SmartNode<Generator> >();
    // implicitly_convertible< SmartNode<Value>, SmartNode<Generator> >();
    // implicitly_convertible< SmartNode<DomainScale>, SmartNode<Generator> >();
};
