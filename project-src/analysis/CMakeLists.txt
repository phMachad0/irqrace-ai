cmake_minimum_required(VERSION 3.13.4)
project(irqrace-analysis C CXX)

# SVF is built out-of-tree against the system LLVM 14. Point SVF_DIR at the
# checkout (scripts/setup-svf.sh puts it at ../toolchain/SVF by default).
if(NOT DEFINED SVF_DIR)
  set(SVF_DIR $ENV{SVF_DIR})
endif()
if(NOT SVF_DIR)
  message(FATAL_ERROR "SVF_DIR not set. Run scripts/setup-svf.sh, then source scripts/env.sh.")
endif()
set(SVF_BUILD "${SVF_DIR}/Release-build")

find_package(LLVM 14 REQUIRED CONFIG)
message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION} in ${LLVM_DIR}")

# SVF is built -fno-rtti -fno-exceptions to match LLVM; anything linking it must be too.
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_compile_options(-fno-rtti -fno-exceptions)

find_library(Z3_LIBRARIES NAMES z3 HINTS ${Z3_DIR} ENV Z3_DIR PATH_SUFFIXES lib bin)
if(NOT Z3_LIBRARIES)
  message(FATAL_ERROR "Z3 not found")
endif()

llvm_map_components_to_libnames(llvm_libs
  bitwriter core ipo irreader instcombine instrumentation target linker
  analysis scalaropts support transformutils)

add_executable(irqrace-probe src/irqrace-probe.cpp)
target_include_directories(irqrace-probe PRIVATE
  ${SVF_DIR}/svf/include
  ${SVF_DIR}/svf-llvm/include
  ${SVF_BUILD}/include
  ${LLVM_INCLUDE_DIRS})
target_link_libraries(irqrace-probe
  ${SVF_BUILD}/svf-llvm/libSvfLLVM.a
  ${SVF_BUILD}/svf/libSvfCore.a
  ${llvm_libs}
  ${Z3_LIBRARIES})
set_target_properties(irqrace-probe PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
