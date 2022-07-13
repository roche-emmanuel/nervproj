set(TARGET_DIR ".")

include_directories(${BOOST_DIR}/include)
link_directories(${BOOST_DIR}/lib)

include_directories(src)

# add_definitions(-DNOMINMAX)
# add_definitions(-D_CRT_SECURE_NO_WARNINGS)

file(GLOB_RECURSE PUBLIC_HEADERS "src/*.h")

file(GLOB_RECURSE SOURCE_FILES "src/*.cpp" )

if(%PROJ_PREFIX_UPPER%_STATIC_BUILD)
	add_subdirectory(static)
else()
	add_subdirectory(shared)
endif()