#include "complementary_filter.hpp"

void complementary_filter_step(
    std::int32_t strain_torque,
    std::int32_t phase_current,
    std::int32_t encoder_position,
    std::int32_t temperature,
    bool input_valid,
    bool reset_state,
    const ftfusion_hls::Config& config,
    ftfusion_hls::Output& output) {
#ifdef __SYNTHESIS__
#pragma HLS INTERFACE mode=s_axilite port=config bundle=control
#pragma HLS INTERFACE mode=s_axilite port=return bundle=control
#pragma HLS PIPELINE II=1
#endif

    static ftfusion_hls::FilterState state{false, 0, 0};
    if (reset_state) {
        ftfusion_hls::reset(state);
    }
    const ftfusion_hls::Sample sample{
        strain_torque,
        phase_current,
        encoder_position,
        temperature,
    };
    output = ftfusion_hls::process_sample(
        sample,
        input_valid,
        config,
        state);
}
