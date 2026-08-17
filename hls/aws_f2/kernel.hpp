#pragma once

#include <cstdint>

struct AwsInputSample {
    std::int32_t strain_torque;
    std::int32_t phase_current;
    std::int32_t encoder_position;
    std::int32_t temperature;
    std::uint32_t valid;
};

struct AwsOutputSample {
    std::int32_t fused_torque;
    std::int32_t corrected_strain;
    std::int32_t current_torque;
    std::int32_t encoder_position;
    std::uint32_t status;
};

static_assert(sizeof(AwsInputSample) == 20, "AWS input ABI must remain stable");
static_assert(sizeof(AwsOutputSample) == 20, "AWS output ABI must remain stable");

extern "C" void ftfusion_batch(
    const AwsInputSample* input,
    AwsOutputSample* output,
    std::uint32_t sample_count,
    std::int32_t alpha,
    std::int32_t torque_constant,
    std::int32_t current_offset,
    std::int32_t strain_offset,
    std::int32_t temperature_coefficient,
    std::int32_t reference_temperature);
