cmake_minimum_required(VERSION 3.20)
project(phyllo_f411_candidate C ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
get_filename_component(FW "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
set(HAL "${FW}/vendor/stm32f4xx-hal-driver")
set(CMSIS "${FW}/vendor/cmsis-device-f4")
find_package(Python3 REQUIRED COMPONENTS Interpreter)
execute_process(COMMAND "${Python3_EXECUTABLE}" "${FW}/bootstrap_sources.py"
  RESULT_VARIABLE vendor_result)
if(NOT vendor_result EQUAL 0)
  message(FATAL_ERROR "Official source verification failed")
endif()
add_compile_options(-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
  -Os -g3 -ffunction-sections -fdata-sections -fstack-usage -Wall -Wextra)
add_compile_definitions(STM32F411xE USE_HAL_DRIVER HSE_VALUE=25000000U)
include_directories(include "${FW}/include" "${HAL}/Inc" "${CMSIS}/Include"
  "${FW}/vendor/cmsis-core/Include" "${CMAKE_CURRENT_BINARY_DIR}")
add_library(st_hal STATIC
  "${HAL}/Src/stm32f4xx_hal.c" "${HAL}/Src/stm32f4xx_hal_cortex.c"
  "${HAL}/Src/stm32f4xx_hal_rcc.c" "${HAL}/Src/stm32f4xx_hal_rcc_ex.c"
  "${HAL}/Src/stm32f4xx_hal_pwr.c" "${HAL}/Src/stm32f4xx_hal_pwr_ex.c"
  "${HAL}/Src/stm32f4xx_hal_gpio.c" "${HAL}/Src/stm32f4xx_hal_dma.c"
  "${HAL}/Src/stm32f4xx_hal_i2s.c" "${HAL}/Src/stm32f4xx_hal_i2s_ex.c"
  "${HAL}/Src/stm32f4xx_hal_tim.c" "${HAL}/Src/stm32f4xx_hal_tim_ex.c"
  "${HAL}/Src/stm32f4xx_hal_uart.c")
add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/layout_generated.h"
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/generate_layout.py"
    "${CMAKE_CURRENT_BINARY_DIR}/layout_generated.h"
  DEPENDS generate_layout.py "${FW}/../shared/layout.json" "${FW}/../shared/chain.json")
add_executable(phyllo_candidate.elf main.c board.c led_dma.c
  "${CMAKE_CURRENT_BINARY_DIR}/layout_generated.h" "${FW}/src/phyllo.c"
  "${CMSIS}/Source/Templates/system_stm32f4xx.c"
  "${CMSIS}/Source/Templates/gcc/startup_stm32f411xe.s")
target_compile_options(phyllo_candidate.elf PRIVATE $<$<COMPILE_LANGUAGE:C>:-Werror;-Wshadow;-Wconversion>)
target_link_libraries(phyllo_candidate.elf PRIVATE st_hal m)
target_link_options(phyllo_candidate.elf PRIVATE
  -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
  -nostartfiles --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections
  "-T${CMAKE_CURRENT_SOURCE_DIR}/stm32f411ce.ld"
  "-Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/phyllo_candidate.map" -Wl,--print-memory-usage)
set_property(TARGET phyllo_candidate.elf APPEND PROPERTY LINK_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/stm32f411ce.ld")
add_custom_command(TARGET phyllo_candidate.elf POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:phyllo_candidate.elf> phyllo_candidate.bin
  COMMAND ${CMAKE_OBJCOPY} -O ihex $<TARGET_FILE:phyllo_candidate.elf> phyllo_candidate.hex
  COMMAND ${CMAKE_SIZE} $<TARGET_FILE:phyllo_candidate.elf>)
