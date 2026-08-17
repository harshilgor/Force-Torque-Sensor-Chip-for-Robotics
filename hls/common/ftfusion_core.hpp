#pragma once

#include <cstdint>
#include <limits>

namespace ftfusion_hls {

constexpr std::int32_t kFractionalBits = 16;
constexpr std::int32_t kOne = 1 << kFractionalBits;

struct Config {
    std::int32_t alpha;
    std::int32_t torque_constant;
    std::int32_t current_offset;
    std::int32_t strain_offset;
    std::int32_t temperature_coefficient;
    std::int32_t reference_temperature;
};

struct Sample {
    std::int32_t strain_torque;
    std::int32_t phase_current;
    std::int32_t encoder_position;
    std::int32_t temperature;
};

struct Output {
    std::int32_t fused_torque;
    std::int32_t corrected_strain;
    std::int32_t current_torque;
    std::int32_t encoder_position;
    std::uint32_t status;
};

struct FilterState {
    bool initialized;
    std::int32_t previous_output;
    std::int32_t previous_current_torque;
};

enum Status : std::uint32_t {
    kValid = 1U << 0,
    kInputInvalid = 1U << 1,
    kSaturated = 1U << 2,
};

inline void reset(FilterState& state) {
    state.initialized = false;
    state.previous_output = 0;
    state.previous_current_torque = 0;
}

inline std::int32_t saturate(std::int64_t value, bool& saturated) {
    constexpr std::int64_t kMinimum =
        std::numeric_limits<std::int32_t>::min();
    constexpr std::int64_t kMaximum =
        std::numeric_limits<std::int32_t>::max();
    if (value < kMinimum) {
        saturated = true;
        return static_cast<std::int32_t>(kMinimum);
    }
    if (value > kMaximum) {
        saturated = true;
        return static_cast<std::int32_t>(kMaximum);
    }
    return static_cast<std::int32_t>(value);
}

inline std::int32_t multiply_q16(
    std::int32_t left,
    std::int32_t right,
    bool& saturated) {
    const std::int64_t product =
        static_cast<std::int64_t>(left) * static_cast<std::int64_t>(right);
    const std::int64_t magnitude = product >= 0 ? product : -product;
    const std::int64_t rounded =
        (magnitude + (kOne / 2)) >> kFractionalBits;
    return saturate(product >= 0 ? rounded : -rounded, saturated);
}

inline Output process_sample(
    const Sample& sample,
    bool input_valid,
    const Config& config,
    FilterState& state) {
    Output output{};
    output.encoder_position = sample.encoder_position;
    if (!input_valid) {
        output.fused_torque = state.previous_output;
        output.status = kInputInvalid;
        return output;
    }

    bool saturated = false;
    const std::int32_t temperature_delta = saturate(
        static_cast<std::int64_t>(sample.temperature)
            - config.reference_temperature,
        saturated);
    const std::int32_t temperature_correction = multiply_q16(
        config.temperature_coefficient,
        temperature_delta,
        saturated);
    output.corrected_strain = saturate(
        static_cast<std::int64_t>(sample.strain_torque)
            - config.strain_offset
            - temperature_correction,
        saturated);
    const std::int32_t current_delta = saturate(
        static_cast<std::int64_t>(sample.phase_current)
            - config.current_offset,
        saturated);
    output.current_torque = multiply_q16(
        current_delta,
        config.torque_constant,
        saturated);

    output.fused_torque = output.corrected_strain;
    if (state.initialized) {
        const std::int32_t high_pass_input = saturate(
            static_cast<std::int64_t>(state.previous_output)
                + output.current_torque
                - state.previous_current_torque,
            saturated);
        const std::int32_t high_pass_term = multiply_q16(
            config.alpha,
            high_pass_input,
            saturated);
        const std::int32_t low_pass_term = multiply_q16(
            kOne - config.alpha,
            output.corrected_strain,
            saturated);
        output.fused_torque = saturate(
            static_cast<std::int64_t>(high_pass_term) + low_pass_term,
            saturated);
    } else {
        state.initialized = true;
    }

    state.previous_output = output.fused_torque;
    state.previous_current_torque = output.current_torque;
    output.status = kValid | (saturated ? kSaturated : 0);
    return output;
}

}  // namespace ftfusion_hls
