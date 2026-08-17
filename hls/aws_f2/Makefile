TARGET ?= hw_emu
PLATFORM ?= $(SHELL_EMU_VERSION)
DURATION ?= 0.02

VPP ?= v++
CXX ?= g++
PYTHON ?= python3

KERNEL := ftfusion_batch
HOST := ftfusion_aws_host
PLATFORM_TAG := $(notdir $(basename $(PLATFORM)))
BUILD_DIR := build_dir.$(TARGET).$(PLATFORM_TAG)
TEMP_DIR := _x.$(TARGET).$(PLATFORM_TAG)
KERNEL_XO := $(BUILD_DIR)/$(KERNEL).xo
XCLBIN := $(BUILD_DIR)/$(KERNEL).xclbin
VECTORS := $(BUILD_DIR)/vectors.csv

CXXFLAGS := -std=c++17 -O2 -Wall -Wextra \
	-I$(XILINX_XRT)/include -I../common
LDFLAGS := -L$(XILINX_XRT)/lib -lxrt_coreutil -pthread
VPP_FLAGS := -t $(TARGET) --platform $(PLATFORM) \
	--temp_dir $(TEMP_DIR) --save-temps

.PHONY: all build host vectors run clean check-env

all: build

check-env:
	@test -n "$(PLATFORM)" || \
		(echo "PLATFORM is empty; source aws-fpga/vitis_setup.sh" && exit 1)
	@test -n "$(XILINX_XRT)" || \
		(echo "XILINX_XRT is empty; install/source XRT" && exit 1)

$(BUILD_DIR):
	mkdir -p $@

host: check-env $(HOST)

$(HOST): host.cpp kernel.hpp ../common/ftfusion_core.hpp
	$(CXX) $(CXXFLAGS) host.cpp -o $@ $(LDFLAGS)

$(KERNEL_XO): kernel.cpp kernel.hpp ../common/ftfusion_core.hpp | $(BUILD_DIR)
	$(VPP) $(VPP_FLAGS) -c -k $(KERNEL) \
		-I../common kernel.cpp -o $@

$(XCLBIN): $(KERNEL_XO)
	$(VPP) $(VPP_FLAGS) -l --config connectivity.cfg $< -o $@

vectors: | $(BUILD_DIR)
	cd ../.. && $(PYTHON) -m ftfusion.cli \
		--duration $(DURATION) --check \
		--vectors hls/aws_f2/$(VECTORS)

build: check-env host vectors $(XCLBIN)

run: build
	@test "$(TARGET)" = "hw_emu" || \
		(echo "Current AWS F2 Vitis flow only runs this target in hw_emu" && exit 1)
	emconfigutil --platform $(PLATFORM) --od $(TEMP_DIR)
	cp $(TEMP_DIR)/emconfig.json .
	XCL_EMULATION_MODE=hw_emu ./$(HOST) \
		-x $(XCLBIN) -i $(VECTORS)

clean:
	rm -rf build_dir.* _x.* .run *.xclbin *.xo *.log *.jou \
		emconfig.json xrt.run_summary $(HOST)
