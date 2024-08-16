cmake_minimum_required(VERSION 3.5)

project(Welle.Io VERSION 0.0.0 LANGUAGES C CXX)

if(NOT WELLE-IO_VERSION)
  set(WELLE-IO_VERSION ${PROJECT_VERSION})
endif()

set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 14)

option(BUILD_WELLE_PY    "Build Welle Python Interface"          ON  )
option(RTLSDR            "Compile with RTL-SDR support"          ON )

add_definitions(-Wall)
add_definitions(-g)
add_definitions(-DDABLIN_AAC_FAAD2)

if(MINGW)
    add_definitions(-municode)
endif()

if(NOT CMAKE_BUILD_TYPE)
   set(CMAKE_BUILD_TYPE "Release")
   message(STATUS "Build type not specified: defaulting to release.")
endif(NOT CMAKE_BUILD_TYPE)
#set(CMAKE_BUILD_TYPE ${CMAKE_BUILD_TYPE} CACHE STRING "")

list(INSERT CMAKE_MODULE_PATH 0 ${CMAKE_SOURCE_DIR}/cmake/Modules)

if(PROFILING)
    add_definitions(-DWITH_PROFILING)
endif()

find_package(FFTW3f REQUIRED)
find_package(Faad REQUIRED)
find_package(Threads REQUIRED)
find_package (Python COMPONENTS Interpreter Development REQUIRED)

if (RTLSDR)
    find_package(LibRTLSDR REQUIRED)
endif()

include_directories(
    src
    src/backend
    src/output
    src/various
    src/input
    src/gui
    src/libs/fec
    ${FFTW3F_INCLUDE_DIRS}
    ${FAAD_INCLUDE_DIRS}
    ${LIBRTLSDR_INCLUDE_DIRS}
    ${Python_INCLUDE_DIRS}
)

set(backend_sources
    src/backend/dab-audio.cpp
    src/backend/decoder_adapter.cpp
    src/backend/dabplus_decoder.cpp
    src/backend/charsets.cpp
    src/backend/dab-constants.cpp
    src/backend/mot_manager.cpp
    src/backend/pad_decoder.cpp
    src/backend/eep-protection.cpp
    src/backend/fib-processor.cpp
    src/backend/fic-handler.cpp
    src/backend/msc-handler.cpp
    src/backend/freq-interleaver.cpp
    src/backend/ofdm-decoder.cpp
    src/backend/ofdm-processor.cpp
    src/backend/phasereference.cpp
    src/backend/phasetable.cpp
    src/backend/tii-decoder.cpp
    src/backend/protTables.cpp
    src/backend/radio-receiver.cpp
    src/backend/tools.cpp
    src/backend/uep-protection.cpp
    src/backend/viterbi.cpp
    src/various/Socket.cpp
    src/various/Xtan2.cpp
    src/various/channels.cpp
    src/various/fft.cpp
    src/various/profiling.cpp
    src/various/wavfile.c
    src/libs/fec/decode_rs_char.c
    src/libs/fec/encode_rs_char.c
    src/libs/fec/init_rs_char.c
)

set(welle_py_sources
    src/welle-python/welle-python.cpp
)

set(input_sources
    src/input/input_factory.cpp
    src/input/null_device.cpp
)

if(LIBRTLSDR_FOUND)
    add_definitions (-DHAVE_RTLSDR)
    set(input_sources  ${input_sources} src/input/rtl_sdr.cpp)
endif()

if(NOT GIT_COMMIT_HASH)
  execute_process(
    COMMAND git rev-parse --short HEAD
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    OUTPUT_VARIABLE GIT_COMMIT_HASH
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
endif()

if(GIT_COMMIT_HASH)
  add_definitions("-DGITHASH=\"${GIT_COMMIT_HASH}\"")
endif()

if(NOT GIT_DESCRIBE)
  execute_process(
    COMMAND git describe --tags --long
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    OUTPUT_VARIABLE GIT_DESCRIBE
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
endif()

if(GIT_DESCRIBE)
  add_definitions("-DGITDESCRIBE=\"${GIT_DESCRIBE}\"")
endif()

STRING(TIMESTAMP BUILD_DATE "%s" UTC)
add_definitions("-DBUILD_DATE=\"${BUILD_DATE}\"")

if(BUILD_WELLE_PY)
    set(objectName welle_py)
    add_library (${objectName} SHARED ${welle_py_sources} ${backend_sources} ${input_sources})

    if(CMAKE_BUILD_TYPE MATCHES Debug)
      SET_TARGET_PROPERTIES(${objectName} PROPERTIES COMPILE_FLAGS "-O2")
#      SET_TARGET_PROPERTIES(${objectName} PROPERTIES COMPILE_FLAGS "-O2 -fno-omit-frame-pointer -fsanitize=address")
#      SET_TARGET_PROPERTIES(${objectName} PROPERTIES LINK_FLAGS "-fno-omit-frame-pointer -fsanitize=address")
    endif(CMAKE_BUILD_TYPE MATCHES Debug)

    target_include_directories (${objectName} PUBLIC src/welle-python)
    target_link_libraries (${objectName}
      ${LIBRTLSDR_LIBRARIES}
      ${FFTW3F_LIBRARIES}
      ${FAAD_LIBRARIES}
      ${Python_LIBRARIES}
      ${CMAKE_DL_LIBS}
      Threads::Threads
    )

endif()

configure_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/cmake_uninstall.cmake.in"
    "${CMAKE_CURRENT_BINARY_DIR}/cmake_uninstall.cmake"
    IMMEDIATE @ONLY)

add_custom_target(uninstall
    COMMAND ${CMAKE_COMMAND} -P ${CMAKE_CURRENT_BINARY_DIR}/cmake_uninstall.cmake)
