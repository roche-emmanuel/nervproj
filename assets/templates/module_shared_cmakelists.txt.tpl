set(TARGET_NAME "%TARGET_NAME%")

add_definitions(-D%PROJ_PREFIX_UPPER%_%LIB_NAME_UPPER%_LIB)

add_msvc_precompiled_header("%LIB_NAME_LOWER%_precomp.h" "%LIB_NAME_LOWER%_precomp.cpp" SOURCE_FILES)

add_library(${TARGET_NAME} SHARED ${PUBLIC_HEADERS} ${SOURCE_FILES})

target_link_libraries(${TARGET_NAME} ${FLAVOR_LIBS} ${BOOST_LIBS})

install(TARGETS ${TARGET_NAME}
	RUNTIME DESTINATION ${TARGET_DIR}
	LIBRARY DESTINATION ${TARGET_DIR})
	# ARCHIVE DESTINATION ${TARGET_DIR}/lib)

# Install the pdb if applicable:
#INSTALL_PDB()
