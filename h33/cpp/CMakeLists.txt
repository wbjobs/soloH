find_package(pybind11 CONFIG QUIET)

if(NOT pybind11_FOUND)
    execute_process(
        COMMAND ${PYTHON_EXECUTABLE} -m pybind11 --cmakedir
        OUTPUT_VARIABLE pybind11_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
        RESULT_VARIABLE pybind11_RESULT
    )
    if(pybind11_RESULT EQUAL 0)
        find_package(pybind11 CONFIG REQUIRED PATHS ${pybind11_DIR})
    endif()
endif()

include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

set(SOURCES
    src/gadget_reader.cpp
    src/fof.cpp
    src/merger_tree.cpp
)

add_library(halo_analysis_core STATIC ${SOURCES})
target_include_directories(halo_analysis_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)

if(pybind11_FOUND)
    pybind11_add_module(halo_analysis_cpp src/pybindings.cpp)
    target_link_libraries(halo_analysis_cpp PRIVATE halo_analysis_core)
    set_target_properties(halo_analysis_cpp PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/python/halo_analysis
    )
else()
    message(WARNING "pybind11 not found. Python bindings will not be built. Using Numba fallback.")
endif()
