# Builds plaid_rt64.dll: RT64 (static) behind Plaid's C ABI (ADR-0163).
#   cmake -S runtime/rt64 -B target/rt64-shim -DRT64_DIR=<pinned rt64 checkout>
cmake_minimum_required(VERSION 3.20)
project(plaid_rt64 LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)

set(RT64_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../.refs/rt64" CACHE PATH "pinned RT64 checkout")
set(RT64_STATIC ON CACHE BOOL "" FORCE)
add_subdirectory("${RT64_DIR}" rt64)
include(patches.cmake)

add_library(plaid_rt64 SHARED plaid_rt64.cpp)
add_executable(plaid_rt64_contract test_rdp.cpp)
add_dependencies(plaid_rt64 plaid_rt64_contract)
foreach(plaid_target plaid_rt64 plaid_rt64_contract)
# RT64 sets these per directory, so its consumers repeat them.
target_compile_definitions(${plaid_target} PRIVATE NOMINMAX __PRFCHWINTRIN_H HLSL_CPU FFX_GCC IMGUI_IMPL_VULKAN_NO_PROTOTYPES)
target_include_directories(${plaid_target} PRIVATE
    "${RT64_DIR}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/include"
    "${RT64_DIR}/src"
    "${RT64_DIR}/src/contrib"
    "${RT64_DIR}/src/contrib/plume"
    "${RT64_DIR}/src/contrib/imgui"
    "${RT64_DIR}/src/contrib/hlslpp/include"
    "${RT64_DIR}/src/contrib/dxc/inc")
target_link_directories(${plaid_target} PRIVATE "${RT64_DIR}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/lib/x64")
target_link_libraries(${plaid_target} PRIVATE rt64)
endforeach()

# Runtime DLLs RT64 loads from next to the executable.
add_custom_command(TARGET plaid_rt64 POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${RT64_DIR}/src/contrib/dxc/bin/x64/dxcompiler.dll"
        "${RT64_DIR}/src/contrib/dxc/bin/x64/dxil.dll"
        "${RT64_DIR}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/lib/x64/SDL2.dll"
        "$<TARGET_FILE_DIR:plaid_rt64>"
    COMMAND "$<TARGET_FILE:plaid_rt64_contract>")

include(CTest)
if(BUILD_TESTING AND WIN32)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_test(NAME plaid_rt64_fill_scissor
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/test_scissor.py"
            "$<TARGET_FILE:plaid_rt64>")
endif()
