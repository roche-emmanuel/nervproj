cmake_minimum_required(VERSION 3.22)

project(%PROJ_NAME%)
set(PROJECT_VERSION %PROJ_VERSION%)

if(MSVC)
  message(STATUS "Building with MSVC compiler")
  # Using MSVC compiler: To build with static runtime linkage:
  if("${CMAKE_BUILD_TYPE}" STREQUAL "Debug")
    message(STATUS "Building debug version of %PROJ_NAME%")
    set(CMAKE_CXX_FLAGS "/EHsc /MDd")

    if(WITH_DEBUG_INFO)
      set(CMAKE_EXE_LINKER_FLAGS
          "${CMAKE_EXE_LINKER_FLAGS} /DEBUG /MAP /MAPINFO:EXPORTS")
      set(CMAKE_SHARED_LINKER_FLAGS
          "${CMAKE_SHARED_LINKER_FLAGS} /DEBUG /MAP /MAPINFO:EXPORTS")
      set(CMAKE_CXX_FLAGS "/EHsc /MDd /Zi")
    endif()
  else()
    message(STATUS "Building release version of %PROJ_NAME%")
    set(CMAKE_CXX_FLAGS "/EHsc /MD")

    if(WITH_DEBUG_INFO)
      set(CMAKE_EXE_LINKER_FLAGS
          "${CMAKE_EXE_LINKER_FLAGS} /DEBUG /OPT:REF,NOICF /MAP /MAPINFO:EXPORTS"
      )
      set(CMAKE_SHARED_LINKER_FLAGS
          "${CMAKE_SHARED_LINKER_FLAGS} /DEBUG /OPT:REF,NOICF /MAP /MAPINFO:EXPORTS"
      )
      set(CMAKE_CXX_FLAGS "/EHsc /MD /Zi")
    endif()
  endif()

  set(CMAKE_CXX_FLAGS_RELEASE "")
  set(CMAKE_CXX_FLAGS_DEBUG "")

  # cf.
  # https://stackoverflow.com/questions/44960715/how-to-enable-stdc17-in-vs2017-with-cmake
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /std:c++17")

elseif(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  # using regular Clang or AppleClang
  set(CMAKE_CXX_FLAGS "-std=c++17") # -fno-strict-aliasing

  # Setup optimization flags:
  set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g")
  set(CMAKE_CXX_FLAGS_RELEASE "-DNDEBUG -O3")
else()
  # Using GCC compiler
  set(CMAKE_CXX_FLAGS "-std=c++17") # -Wall -Wcomment -fno-strict-aliasing

  # Setup optimization flags:
  set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g")
  set(CMAKE_CXX_FLAGS_RELEASE "-DNDEBUG -O3 -s")

  if("${FLAVOR}" STREQUAL "WIN32")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -march=i686")
  endif()

  if("${FLAVOR}" STREQUAL "LINUX64")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fPIC")
  endif()
endif()

# prepare the source folder:
set(SRC_DIR ${PROJECT_SOURCE_DIR}/sources)

if(%PROJ_PREFIX%_STATIC_BUILD)
  message(STATUS "Building static %PROJ_NAME% libraries.")
else()
  message(STATUS "Building shared %PROJ_NAME% libraries.")
endif()

# Add the test folder
add_subdirectory(tests)
