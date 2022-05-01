cmake_minimum_required(VERSION 3.13 FATAL_ERROR)

include_directories(${BOOST_DIR}/include)
link_directories(${BOOST_DIR}/lib)

include_directories(${FASTNOISE2_DIR}/include)
link_directories(${FASTNOISE2_DIR}/lib)

project(
  pyfn2
  VERSION 0.9.4
  LANGUAGES CXX)

set(TARGET_NAME pyfn2)
set(TARGET_DIR "./")
set(SOURCE_FILES bindings.cpp)

# FastNoise built as static library:
add_definitions(-DFASTNOISE_STATIC_LIB)

if(WIN32)
  add_definitions(-DBOOST_PYTHON_STATIC_LIB)
  add_definitions(-DBOOST_NUMPY_STATIC_LIB)
  include_directories(${PYTHON_DIR}/include)
  link_directories(${PYTHON_DIR}/libs)
  set(modExt ".pyd")
  set(BOOST_LIBS)
  set(PYTHON_LIBS)
  set(STD_LIBS)
else()
  include_directories(${PYTHON_DIR}/include/python3.6)
  link_directories(${PYTHON_DIR}/lib)
  set(modExt ".so")
  set(BOOST_LIBS boost_python3)
  set(PYTHON_LIBS pthread dl util python3.6)
  # cf. link options at: https://gcc.gnu.org/onlinedocs/gcc/Link-Options.html
  # SET(STD_LIBS -static-libgcc -static-libstdc++)
  set(STD_LIBS -shared-libgcc)
endif()

add_library(${TARGET_NAME} SHARED ${SOURCE_FILES})

target_link_libraries(${TARGET_NAME} ${PYTHON_LIBS} ${BOOST_LIBS} ${STD_LIBS}
                      FastNoise)

set_target_properties(${TARGET_NAME} PROPERTIES PREFIX "" SUFFIX ${modExt})

install(
  TARGETS ${TARGET_NAME}
  RUNTIME DESTINATION ${TARGET_DIR}
  LIBRARY DESTINATION ${TARGET_DIR})
