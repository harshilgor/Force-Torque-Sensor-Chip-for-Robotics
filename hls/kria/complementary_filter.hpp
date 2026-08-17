#pragma once

#include "../common/ftfusion_core.hpp"

void complementary_filter_step(
    std::int32_t strain_torque,
    std::int32_t phase_current,
    std::int32_t encoder_position,
    std::int32_t temperature,
    bool input_valid,
    bool reset_state,
    const ftfusion_hls::Config& config,
    ftfusion_hls::Output& output);
