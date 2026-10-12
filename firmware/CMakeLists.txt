cmake_minimum_required(VERSION 3.13)

# Configure with the SDK on the path, e.g.:
#   cmake -B build -DPICO_SDK_PATH=$HOME/pico-sdk -DPICO_BOARD=pico
#   cmake --build build -j
include($ENV{PICO_SDK_PATH}/pico_sdk_init.cmake)

project(avionics_test_bench C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()

add_executable(bench_validator main.c)

target_link_libraries(bench_validator
    pico_stdlib
    hardware_i2c
    hardware_spi
    hardware_adc
    hardware_uart
)

# validate.py speaks to the USB CDC serial port, so stdio goes over USB.
pico_enable_stdio_usb(bench_validator 1)
pico_enable_stdio_uart(bench_validator 0)

pico_add_extra_outputs(bench_validator)
