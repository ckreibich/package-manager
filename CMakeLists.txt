cmake_minimum_required(VERSION 2.6.3 FATAL_ERROR)
project(zkg)

set(CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/cmake ${CMAKE_MODULE_PATH})
set(PREFIX "${CMAKE_INSTALL_PREFIX}")

include(FindRequiredPackage)
FindRequiredPackage(PythonInterp)

install(CODE "execute_process(COMMAND ${PYTHON_EXECUTABLE} -m pip install --prefix ${CMAKE_INSTALL_PREFIX} ${CMAKE_CURRENT_SOURCE_DIR})")
