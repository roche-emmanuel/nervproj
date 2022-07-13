macro(ADD_MSVC_PRECOMPILED_HEADER PrecompiledHeader PrecompiledSource
      SourcesVar)
  if(MSVC)
    file(GLOB_RECURSE to_remove "*${PrecompiledSource}")
    list(REMOVE_ITEM ${SourcesVar} ${to_remove})

    get_filename_component(PrecompiledBasename ${PrecompiledHeader} NAME_WE)
    set(PrecompiledBinary
        "${CMAKE_CURRENT_BINARY_DIR}/${PrecompiledBasename}.pch")
    set(Sources ${${SourcesVar}})

    set_source_files_properties(
      ${PrecompiledSource}
      PROPERTIES COMPILE_FLAGS
                 "/Yc\"${PrecompiledHeader}\" /Fp\"${PrecompiledBinary}\""
                 OBJECT_OUTPUTS "${PrecompiledBinary}")
    set_source_files_properties(
      ${Sources}
      PROPERTIES
        COMPILE_FLAGS
        "/Yu\"${PrecompiledBinary}\" /FI\"${PrecompiledBinary}\" /Fp\"${PrecompiledBinary}\""
        OBJECT_DEPENDS "${PrecompiledBinary}")
    # Add precompiled header to SourcesVar
    list(APPEND ${SourcesVar} ${PrecompiledSource})
  endif(MSVC)
endmacro(ADD_MSVC_PRECOMPILED_HEADER)

macro(ADD_FILES file_list regex)
  file(GLOB_RECURSE TEMP_FILES ${regex})
  list(APPEND ${file_list} ${TEMP_FILES})
endmacro(ADD_FILES)

macro(COMPRESS_BINARY_TARGET)
  if(USE_UPX_COMPRESSION)
    if(MSVC)
      set(THE_TARGET "${TARGET_NAME}")
      message("Adding compression for ${THE_TARGET}")

      add_custom_command(
        TARGET ${THE_TARGET}
        POST_BUILD
        COMMAND echo "Compressing ${THE_TARGET}..."
        COMMAND ${UPX_PATH} --best "$<TARGET_FILE:${THE_TARGET}>"
        COMMAND echo "Compression done.")
    endif()
  endif()
endmacro(COMPRESS_BINARY_TARGET)

# MACRO(INSTALL_PDB _destdir)
macro(INSTALL_PDB)
  if(WITH_DEBUG_INFO
     AND MSVC
     AND NOT NV_STATIC_BUILD)
    set(_destdir "./")
    install(
      FILES "$<TARGET_FILE_DIR:${TARGET_NAME}>/${TARGET_NAME}.pdb"
      DESTINATION "${_destdir}"
      CONFIGURATIONS Release)
    install(
      FILES "$<TARGET_FILE_DIR:${TARGET_NAME}>/${TARGET_NAME}.map"
      DESTINATION "${_destdir}"
      CONFIGURATIONS Release)
  endif()
endmacro()
