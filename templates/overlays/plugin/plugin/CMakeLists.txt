# This file is maintained by zkg. Do not edit.
# Put required additional cmake functionality into @PACKAGE_SLUG@.cmake.
cmake_minimum_required(VERSION 3.5 FATAL_ERROR)

project(ZeekPlugin@PACKAGE_SLUG@)

include(ZeekPlugin)

zeek_plugin_begin(@PACKAGE_NAMESPACE@ @PACKAGE_SLUG@)

file(GLOB cc_files "src/*.cc")
foreach(file ${cc_files})
    zeek_plugin_cc(${file})
endforeach ()

file(GLOB bif_files "src/*.bif")
foreach(file ${big_files})
    zeek_plugin_bif(${file})
endforeach ()

zeek_plugin_dist_files(README CHANGES COPYING VERSION)
zeek_plugin_end()

file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/VERSION" VERSION LIMIT_COUNT 1)

include(@PACKAGE_SLUG@ OPTIONAL)

if ("${PROJECT_SOURCE_DIR}" STREQUAL "${CMAKE_SOURCE_DIR}")
    # Allows building rpm/deb packages via "make package" in build dir.
    include(ConfigurePackaging)
    ConfigurePackaging(${VERSION})
endif ()
