#include "kernel.hpp"

#include "../common/ftfusion_core.hpp"

#include <xrt/xrt_bo.h>
#include <xrt/xrt_device.h>
#include <xrt/xrt_kernel.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

struct Options {
    std::string xclbin;
    std::string vectors;
    double sample_rate_hz = 10000.0;
    double crossover_hz = 30.0;
    double torque_constant = 0.12;
    double current_offset = 0.0;
    double strain_offset = 0.0;
    double temperature_coefficient = 0.002;
    double reference_temperature = 25.0;
    double tolerance_nm = 0.001;
};

struct VectorData {
    std::vector<AwsInputSample> input;
    std::vector<double> golden_fused_nm;
};

std::vector<std::string> split_csv(const std::string& line) {
    std::vector<std::string> fields;
    std::size_t start = 0;
    while (true) {
        const std::size_t comma = line.find(',', start);
        fields.push_back(line.substr(start, comma - start));
        if (comma == std::string::npos) {
            break;
        }
        start = comma + 1;
    }
    return fields;
}

std::int32_t q16(double value) {
    const double scaled = std::round(value * 65536.0);
    const double minimum =
        static_cast<double>(std::numeric_limits<std::int32_t>::min());
    const double maximum =
        static_cast<double>(std::numeric_limits<std::int32_t>::max());
    return static_cast<std::int32_t>(
        std::min(maximum, std::max(minimum, scaled)));
}

double from_q16(std::int32_t value) {
    return static_cast<double>(value) / 65536.0;
}

double parse_double_option(
    int& index,
    int argc,
    char** argv,
    const std::string& name) {
    if (++index >= argc) {
        throw std::runtime_error("missing value for " + name);
    }
    return std::stod(argv[index]);
}

Options parse_options(int argc, char** argv) {
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if ((argument == "-x" || argument == "--xclbin") && ++index < argc) {
            options.xclbin = argv[index];
        } else if (
            (argument == "-i" || argument == "--input") && ++index < argc) {
            options.vectors = argv[index];
        } else if (argument == "--sample-rate") {
            options.sample_rate_hz =
                parse_double_option(index, argc, argv, argument);
        } else if (argument == "--crossover") {
            options.crossover_hz =
                parse_double_option(index, argc, argv, argument);
        } else if (argument == "--torque-constant") {
            options.torque_constant =
                parse_double_option(index, argc, argv, argument);
        } else if (argument == "--current-offset") {
            options.current_offset =
                parse_double_option(index, argc, argv, argument);
        } else if (argument == "--strain-offset") {
            options.strain_offset =
                parse_double_option(index, argc, argv, argument);
        } else if (argument == "--temperature-coefficient") {
            options.temperature_coefficient =
                parse_double_option(index, argc, argv, argument);
        } else if (argument == "--reference-temperature") {
            options.reference_temperature =
                parse_double_option(index, argc, argv, argument);
        } else if (argument == "--tolerance") {
            options.tolerance_nm =
                parse_double_option(index, argc, argv, argument);
        } else {
            throw std::runtime_error("unknown or incomplete option: " + argument);
        }
    }
    if (options.xclbin.empty() || options.vectors.empty()) {
        throw std::runtime_error(
            "usage: ftfusion_aws_host -x KERNEL.xclbin -i VECTORS.csv");
    }
    return options;
}

VectorData load_vectors(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) {
        throw std::runtime_error("cannot open vector CSV: " + path);
    }
    std::string line;
    if (!std::getline(stream, line)) {
        throw std::runtime_error("vector CSV is empty");
    }
    const std::vector<std::string> header = split_csv(line);
    std::unordered_map<std::string, std::size_t> column;
    for (std::size_t index = 0; index < header.size(); ++index) {
        column.emplace(header[index], index);
    }
    const std::vector<std::string> required{
        "strain_torque_nm",
        "phase_current_a",
        "encoder_position_rad",
        "temperature_c",
        "fixed_fused_nm",
    };
    for (const std::string& name : required) {
        if (column.find(name) == column.end()) {
            throw std::runtime_error("missing vector column: " + name);
        }
    }

    VectorData vectors;
    while (std::getline(stream, line)) {
        if (line.empty()) {
            continue;
        }
        const std::vector<std::string> fields = split_csv(line);
        if (fields.size() != header.size()) {
            throw std::runtime_error("malformed vector CSV row");
        }
        vectors.input.push_back(AwsInputSample{
            q16(std::stod(fields[column.at("strain_torque_nm")])),
            q16(std::stod(fields[column.at("phase_current_a")])),
            q16(std::stod(fields[column.at("encoder_position_rad")])),
            q16(std::stod(fields[column.at("temperature_c")])),
            1,
        });
        vectors.golden_fused_nm.push_back(
            std::stod(fields[column.at("fixed_fused_nm")]));
    }
    if (vectors.input.empty()) {
        throw std::runtime_error("vector CSV contains no samples");
    }
    return vectors;
}

double elapsed_us(
    std::chrono::steady_clock::time_point start,
    std::chrono::steady_clock::time_point end) {
    return std::chrono::duration<double, std::micro>(end - start).count();
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parse_options(argc, argv);
        const VectorData vectors = load_vectors(options.vectors);
        if (vectors.input.size() > std::numeric_limits<std::uint32_t>::max()) {
            throw std::runtime_error("sample count exceeds kernel uint32 limit");
        }

        xrt::device device(0);
        const auto uuid = device.load_xclbin(options.xclbin);
        xrt::kernel kernel(device, uuid, "ftfusion_batch");

        const std::size_t input_bytes =
            vectors.input.size() * sizeof(AwsInputSample);
        const std::size_t output_bytes =
            vectors.input.size() * sizeof(AwsOutputSample);
        xrt::bo input_buffer(
            device, input_bytes, kernel.group_id(0));
        xrt::bo output_buffer(
            device, output_bytes, kernel.group_id(1));
        auto* mapped_input = input_buffer.map<AwsInputSample*>();
        auto* mapped_output = output_buffer.map<AwsOutputSample*>();
        std::copy(vectors.input.begin(), vectors.input.end(), mapped_input);

        const auto h2d_start = std::chrono::steady_clock::now();
        input_buffer.sync(XCL_BO_SYNC_BO_TO_DEVICE);
        const auto h2d_end = std::chrono::steady_clock::now();

        const double alpha = std::exp(
            -2.0 * 3.14159265358979323846
            * options.crossover_hz
            / options.sample_rate_hz);
        const auto kernel_start = std::chrono::steady_clock::now();
        auto run = kernel(
            input_buffer,
            output_buffer,
            static_cast<std::uint32_t>(vectors.input.size()),
            q16(alpha),
            q16(options.torque_constant),
            q16(options.current_offset),
            q16(options.strain_offset),
            q16(options.temperature_coefficient),
            q16(options.reference_temperature));
        run.wait();
        const auto kernel_end = std::chrono::steady_clock::now();

        const auto d2h_start = std::chrono::steady_clock::now();
        output_buffer.sync(XCL_BO_SYNC_BO_FROM_DEVICE);
        const auto d2h_end = std::chrono::steady_clock::now();

        double maximum_error_nm = 0.0;
        std::size_t invalid_outputs = 0;
        for (std::size_t index = 0; index < vectors.input.size(); ++index) {
            maximum_error_nm = std::max(
                maximum_error_nm,
                std::abs(
                    from_q16(mapped_output[index].fused_torque)
                    - vectors.golden_fused_nm[index]));
            if ((mapped_output[index].status & ftfusion_hls::kValid) == 0) {
                ++invalid_outputs;
            }
        }

        const double kernel_us = elapsed_us(kernel_start, kernel_end);
        std::cout
            << "{\n"
            << "  \"samples\": " << vectors.input.size() << ",\n"
            << "  \"h2d_us\": " << elapsed_us(h2d_start, h2d_end) << ",\n"
            << "  \"batch_kernel_us\": " << kernel_us << ",\n"
            << "  \"d2h_us\": " << elapsed_us(d2h_start, d2h_end) << ",\n"
            << "  \"kernel_samples_per_s\": "
            << vectors.input.size() * 1000000.0 / kernel_us << ",\n"
            << "  \"max_fixed_point_error_nm\": " << maximum_error_nm << ",\n"
            << "  \"invalid_outputs\": " << invalid_outputs << "\n"
            << "}\n";

        const bool passed =
            invalid_outputs == 0
            && maximum_error_nm <= options.tolerance_nm;
        std::cout << (passed ? "TEST PASSED\n" : "TEST FAILED\n");
        return passed ? 0 : 1;
    } catch (const std::exception& error) {
        std::cerr << "ERROR: " << error.what() << '\n';
        return 2;
    }
}
