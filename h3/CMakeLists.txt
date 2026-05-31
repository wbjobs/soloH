cmake_minimum_required(VERSION 3.16)
project(IzhikevichNetworkSim LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Eigen3 3.3 REQUIRED NO_MODULE)
find_package(Qt6 COMPONENTS Core Gui Widgets Charts QUIET)

if(Qt6_FOUND)
    set(QT_AVAILABLE TRUE)
    message(STATUS "Qt6 found - building with real-time visualization")
else()
    find_package(Qt5 COMPONENTS Core Gui Widgets Charts QUIET)
    if(Qt5_FOUND)
        set(QT_AVAILABLE TRUE)
        message(STATUS "Qt5 found - building with real-time visualization")
    else()
        set(QT_AVAILABLE FALSE)
        message(STATUS "Qt not found - building without visualization (use Python script for plotting)")
    endif()
endif()

find_package(Threads REQUIRED)

set(SOURCES
    src/main.cpp
    src/izhikevich_neuron.cpp
    src/network_simulator.cpp
)

set(HEADERS
    include/izhikevich_neuron.h
    include/network_simulator.h
)

if(QT_AVAILABLE)
    list(APPEND SOURCES src/real_time_plot.cpp)
    list(APPEND HEADERS include/real_time_plot.h)
endif()

add_executable(${PROJECT_NAME} ${SOURCES} ${HEADERS})

target_include_directories(${PROJECT_NAME} PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_link_libraries(${PROJECT_NAME}
    Eigen3::Eigen
    Threads::Threads
)

if(QT_AVAILABLE)
    if(Qt6_FOUND)
        target_link_libraries(${PROJECT_NAME} Qt6::Core Qt6::Gui Qt6::Widgets Qt6::Charts)
    else()
        target_link_libraries(${PROJECT_NAME} Qt5::Core Qt5::Gui Qt5::Widgets Qt5::Charts)
    endif()
    target_compile_definitions(${PROJECT_NAME} PRIVATE USE_QT_CHARTS)
endif()

target_compile_options(${PROJECT_NAME} PRIVATE
    -O3
    -march=native
    -ffast-math
)
