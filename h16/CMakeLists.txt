cmake_minimum_required(VERSION 3.15)
project(BooleanNetworkAnalyzer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

if(MSVC)
    add_compile_options(/W4 /O2)
else()
    add_compile_options(-Wall -Wextra -O2)
endif()

include_directories(${CMAKE_SOURCE_DIR}/include)

option(BN_WITH_HDF5 "Enable HDF5 output support" OFF)

if(BN_WITH_HDF5)
    find_package(HDF5 COMPONENTS CXX REQUIRED)
    include_directories(${HDF5_INCLUDE_DIRS})
    add_definitions(-DBN_WITH_HDF5)
endif()

add_executable(bn_analyzer
    src/boolean_network.cpp
    src/main.cpp
)

if(BN_WITH_HDF5)
    target_link_libraries(bn_analyzer ${HDF5_CXX_LIBRARIES})
endif()

enable_testing()
add_test(NAME test_simple_network COMMAND bn_analyzer -s 100 -b 500 ${CMAKE_SOURCE_DIR}/examples/simple_network.txt)
add_test(NAME test_cycle_network COMMAND bn_analyzer -s 200 -b 1000 ${CMAKE_SOURCE_DIR}/examples/cycle_network.txt)
