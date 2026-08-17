#include "complementary_filter.hpp"

#include <cassert>
#include <cmath>
#include <cstdint>

namespace {

std::int32_t q16(double value) {
    return static_cast<std::int32_t>(std::round(value * 65536.0));
}

}  // namespace

int main() {
    ftfusion_hls::Config config{
        q16(0.9813269859720434),
        q16(1.0),
        q16(0.0),
        q16(0.0),
        q16(0.01),
        q16(25.0),
    };
    ftfusion_hls::Output output{};

    complementary_filter_step(
        q16(1.1),
        q16(0.0),
        q16(0.25),
        q16(35.0),
        true,
        true,
        config,
        output);
    assert((output.status & ftfusion_hls::kValid) != 0);
    assert(std::abs(output.corrected_strain - q16(1.0)) <= 2);
    assert(output.fused_torque == output.corrected_strain);

    config.temperature_coefficient = 0;
    complementary_filter_step(
        0, 0, 0, q16(25.0), true, true, config, output);
    complementary_filter_step(
        0, q16(1.0), 0, q16(25.0), true, false, config, output);
    assert(output.current_torque == q16(1.0));
    assert(output.fused_torque == config.alpha);

    const std::int32_t last_valid = output.fused_torque;
    complementary_filter_step(
        0, 0, 0, 0, false, false, config, output);
    assert(output.status == ftfusion_hls::kInputInvalid);
    assert(output.fused_torque == last_valid);
    return 0;
}
