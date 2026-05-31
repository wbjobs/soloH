cmake_minimum_required(VERSION 3.16)
project(ChaosAnalyzer VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS
    Core
    Gui
    Widgets
    OpenGLWidgets
    Charts
    Multimedia
)

find_package(OpenGL REQUIRED)

set(PROJECT_SOURCES
    main.cpp
    mainwindow.cpp
    mainwindow.h
    mainwindow.ui
    odesolver.h
    odesolver.cpp
    chaoticsystems.h
    chaoticsystems.cpp
    lyapunovcalculator.h
    lyapunovcalculator.cpp
    fftanalyzer.h
    fftanalyzer.cpp
    phaseplot3d.h
    phaseplot3d.cpp
    plotwidget.h
    plotwidget.cpp
    dataexporter.h
    dataexporter.cpp
)

qt_add_executable(ChaosAnalyzer
    ${PROJECT_SOURCES}
)

target_link_libraries(ChaosAnalyzer PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
    Qt6::OpenGLWidgets
    Qt6::Charts
    OpenGL::GL
    OpenGL::GLU
)

if(WIN32)
    set_target_properties(ChaosAnalyzer PROPERTIES
        WIN32_EXECUTABLE TRUE
    )
endif()
