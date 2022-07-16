set(TARGET_NAME "%TARGET_NAME%_static")

add_definitions(-D%PROJ_PREFIX_UPPER%_LIB_STATIC)

add_library(${TARGET_NAME} ${PUBLIC_HEADERS} ${SOURCE_FILES})

target_link_libraries(${TARGET_NAME} ${FLAVOR_LIBS} ${BOOST_LIBS})
target_precompile_headers(${TARGET_NAME} PRIVATE "../src/%LIB_NAME_LOWER%_precomp.h")
