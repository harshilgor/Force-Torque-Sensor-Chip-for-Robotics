#include "kernel.hpp"

#include "../common/ftfusion_core.hpp"

extern "C" void ftfusion_batch(
    const AwsInputSample* input,
    AwsOutputSample* output,
    std::uint32_t sample_count,
    std::int32_t alpha,
    std::int32_t torque_constant,
    std::int32_t current_offset,
    std::int32_t strain_offset,
    std::int32_t temperature_coefficient,
    std::int32_t reference_temperature) {
#pragma HLS INTERFACE m_axi port=input offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=output offset=slave bundle=gmem1
#pragma HLS INTERFACE s_axilite port=input bundle=control
#pragma HLS INTERFACE s_axilite port=output bundle=control
#pragma HLS INTERFACE s_axilite port=sample_count bundle=control
#pragma HLS INTERFACE s_axilite port=alpha bundle=control
#pragma HLS INTERFACE s_axilite port=torque_constant bundle=control
#pragma HLS INTERFACE s_axilite port=current_offset bundle=control
#pragma HLS INTERFACE s_axilite port=strain_offset bundle=control
#pragma HLS INTERFACE s_axilite port=temperature_coefficient bundle=control
#pragma HLS INTERFACE s_axilite port=reference_temperature bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    const ftfusion_hls::Config config{
        alpha,
        torque_constant,
        current_offset,
        strain_offset,
        temperature_coefficient,
        reference_temperature,
    };
    ftfusion_hls::FilterState state{};
    ftfusion_hls::reset(state);

    for (std::uint32_t index = 0; index < sample_count; ++index) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=1 max=1048576
        const AwsInputSample input_sample = input[index];
        const ftfusion_hls::Sample sample{
            input_sample.strain_torque,
            input_sample.phase_current,
            input_sample.encoder_position,
            input_sample.temperature,
        };
        const ftfusion_hls::Output result = ftfusion_hls::process_sample(
            sample,
            input_sample.valid != 0,
            config,
            state);
        output[index] = AwsOutputSample{
            result.fused_torque,
            result.corrected_strain,
            result.current_torque,
            result.encoder_position,
            result.status,
        };
    }
}
