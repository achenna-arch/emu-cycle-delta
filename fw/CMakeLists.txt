cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(emu_cycle_delta)

# pad.S comes first so that its section sits ahead of the kernel text.
target_sources(app PRIVATE src/pad.S src/main.c)

# A layout file sets the order of the text sections at link time.
if(BENCH_LAYOUT)
  zephyr_link_libraries(-Wl,--section-ordering-file=${BENCH_LAYOUT})
endif()
