cmake_minimum_required(VERSION 3.10)
project(MotifDiscovery CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(OpenMP)

if(MSVC)
    add_compile_options(/W4 /O2)
    if(OpenMP_CXX_FOUND)
        add_compile_options(${OpenMP_CXX_FLAGS})
    endif()
else()
    add_compile_options(-Wall -Wextra -O2)
    if(OpenMP_CXX_FOUND)
        add_compile_options(${OpenMP_CXX_FLAGS})
    endif()
endif()

include_directories(${PROJECT_SOURCE_DIR}/include)

add_executable(motif_discovery
    src/main.cpp
)

if(OpenMP_CXX_FOUND)
    target_link_libraries(motif_discovery OpenMP::OpenMP_CXX)
endif()
if(NOT MSVC)
    target_link_libraries(motif_discovery pthread)
endif()

enable_testing()

add_custom_target(run_example
    COMMAND motif_discovery -i ${PROJECT_SOURCE_DIR}/example.fasta -w 8
    DEPENDS motif_discovery
    WORKING_DIRECTORY ${PROJECT_BINARY_DIR}
)
