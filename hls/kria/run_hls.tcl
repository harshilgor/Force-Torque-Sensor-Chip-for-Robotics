open_project -reset ftfusion_kria_hls
set_top complementary_filter_step

add_files complementary_filter.cpp -cflags {-I../common}
add_files complementary_filter.hpp
add_files ../common/ftfusion_core.hpp
add_files -tb test_complementary.cpp -cflags {-I../common}

open_solution -reset solution_q16_16 -flow_target vivado
set_part {xck26-sfvc784-2LV-c}
create_clock -period 5.0 -name default

csim_design
csynth_design
cosim_design

exit
