SET(TARGET_NAME "%TARGET_NAME%")
SET(TARGET_DIR ".")

include_directories(${BOOST_DIR}/include)
link_directories(${BOOST_DIR}/lib)

include_directories(src)

file(GLOB_RECURSE PUBLIC_HEADERS "src/*.h")

file(GLOB_RECURSE SOURCE_FILES "src/*.cpp" )

add_definitions(-D_CRT_SECURE_NO_WARNINGS)

set(STATIC_SUFFIX "")
set(ADDITIONAL_LIBS "")
if(%PROJ_PREFIX_UPPER%_STATIC_BUILD)
	add_definitions(-D%PROJ_PREFIX_UPPER%_LIB_STATIC)
	set(STATIC_SUFFIX "_static")
	# sef(ADDITIONAL_LIBS nvView_static luaDX12_static luaCore_static luaView_static luaOCCT_static)

	if(MSVC)
		# set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} /NODEFAULTLIB:MSVCRT")
		set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} /NODEFAULTLIB:LIBCMT")
	endif()
endif()

# if(NOT MSVC)
#	set(BOOST_LIBS boost_program_options)
# endif()

add_executable(${TARGET_NAME} ${SOURCE_FILES})
target_link_libraries(${TARGET_NAME} 
	#nvCore${STATIC_SUFFIX} 
	${BOOST_LIBS}
	${ADDITIONAL_LIBS})

set_target_properties(${TARGET_NAME} PROPERTIES PREFIX "")

# compress_binary_target()

install(TARGETS ${TARGET_NAME}
	RUNTIME DESTINATION ${TARGET_DIR}
	LIBRARY DESTINATION ${TARGET_DIR})

# install_pdb()
