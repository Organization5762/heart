#pragma once

#include "matrixmap.h"
#include <algorithm>
#include <cassert>
#include <cmath>
#include <span>
#include <vector>

namespace piomatter {

#ifndef HEART_PIOMATTER_SLAB_COPIES
#define HEART_PIOMATTER_SLAB_COPIES 1
#endif

constexpr int DATA_OVERHEAD = 3;
constexpr int CLOCKS_PER_DATA = 2;
constexpr int DELAY_OVERHEAD = 5;
constexpr int CLOCKS_PER_DELAY = 1;

constexpr uint32_t command_kind_shift = 30;
constexpr uint32_t command_delay = 0;
constexpr uint32_t command_row_literal = 0b10u << command_kind_shift;
constexpr uint32_t command_row_repeat = 0b11u << command_kind_shift;
constexpr uint32_t command_count_mask = (1u << command_kind_shift) - 1;
constexpr size_t slab_copy_count = HEART_PIOMATTER_SLAB_COPIES;

struct gamma_lut {
    gamma_lut(double exponent = 2.2) {
        for (int i = 0; i < 256; i++) {
            auto v = std::max(i, int(round(1023 * pow(i / 255., exponent))));
            lut[i] = v;
        }
    }

    unsigned convert(unsigned v) {
        if (v >= std::size(lut))
            return 1023;
        return lut[v];
    }

    void convert_rgb888_packed_to_rgb10(std::vector<uint32_t> &result,
                                        std::span<const uint8_t> source) {
        result.resize(source.size() / 3);
        for (size_t i = 0, j = 0; i < source.size(); i += 3) {
            uint32_t r = source[i + 0] & 0xff;
            uint32_t g = source[i + 1] & 0xff;
            uint32_t b = source[i + 2] & 0xff;
            result[j++] = (convert(r) << 20) | (convert(g) << 10) | convert(b);
        }
    }

    void convert_rgb888_to_rgb10(std::vector<uint32_t> &result,
                                 std::span<const uint32_t> source) {
        result.resize(source.size());
        for (size_t i = 0; i < source.size(); i++) {
            uint32_t data = source[i];
            uint32_t r = (data >> 16) & 0xff;
            uint32_t g = (data >> 8) & 0xff;
            uint32_t b = data & 0xff;
            result[i] = (convert(r) << 20) | (convert(g) << 10) | convert(b);
        }
    }

    void convert_rgb565_to_rgb10(std::vector<uint32_t> &result,
                                 std::span<const uint16_t> source) {
        result.resize(source.size());
        for (size_t i = 0; i < source.size(); i++) {
            uint32_t data = source[i];
            unsigned r5 = (data >> 11) & 0x1f;
            unsigned r = (r5 << 3) | (r5 >> 2);
            unsigned g6 = (data >> 5) & 0x3f;
            unsigned g = (g6 << 2) | (g6 >> 4);
            unsigned b5 = (data)&0x1f;
            unsigned b = (b5 << 3) | (b5 >> 2);

            result[i] = (convert(r) << 20) | (convert(g) << 10) | convert(b);
        }
    }

    uint16_t lut[256];
};

struct colorspace_rgb565 {
    using data_type = uint16_t;
    static constexpr size_t data_size_in_bytes(size_t n_pixels) {
        return sizeof(data_type) * n_pixels;
    }

    colorspace_rgb565(float gamma = 2.2) : lut{gamma} {}
    gamma_lut lut;
    const std::span<const uint32_t>
    convert(std::span<const data_type> data_in) {
        lut.convert_rgb565_to_rgb10(rgb10, data_in);
        return rgb10;
    }
    std::vector<uint32_t> rgb10;
};

struct colorspace_rgb888 {
    using data_type = uint32_t;
    static constexpr size_t data_size_in_bytes(size_t n_pixels) {
        return sizeof(data_type) * n_pixels;
    }

    colorspace_rgb888(float gamma = 2.2) : lut{gamma} {}
    gamma_lut lut;
    const std::span<const uint32_t>
    convert(std::span<const data_type> data_in) {
        lut.convert_rgb888_to_rgb10(rgb10, data_in);
        return rgb10;
    }
    std::vector<uint32_t> rgb10;
};

struct colorspace_rgb888_packed {
    using data_type = uint8_t;
    static constexpr size_t data_size_in_bytes(size_t n_pixels) {
        return sizeof(data_type) * n_pixels * 3;
    }

    colorspace_rgb888_packed(float gamma = 2.2) : lut{gamma} {}
    gamma_lut lut;
    const std::span<const uint32_t>
    convert(std::span<const data_type> data_in) {
        lut.convert_rgb888_packed_to_rgb10(rgb10, data_in);
        return rgb10;
    }
    std::vector<uint32_t> rgb10;
};

struct colorspace_rgb10 {
    using data_type = uint32_t;

    const std::span<const uint32_t>
    convert(std::span<const data_type> data_in) {
        return data_in;
    }
};

inline uint32_t encode_delay_count(int32_t delay) {
    delay = std::max((delay / CLOCKS_PER_DELAY) - DELAY_OVERHEAD, 1);
    assert(delay < 1000000);
    return uint32_t(delay - 1);
}

inline bool row_words_are_uniform(std::span<const uint32_t> row_words) {
    if (row_words.empty()) {
        return false;
    }
    return std::all_of(
        row_words.begin(), row_words.end(), [&](uint32_t word) { return word == row_words.front(); }
    );
}

template <typename pinout>
void protomatter_render_rgb10(std::vector<uint32_t> &result,
                              const matrix_geometry &matrixmap,
                              const schedule &sched, uint32_t old_active_time,
                              const uint32_t *pixels) {
    result.clear();
    std::vector<uint32_t> frame_words;

    auto calc_addr_bits = [](int addr) {
        uint32_t data = 0;
        if (addr & 1)
            data |= (1 << pinout::PIN_ADDR[0]);
        if (addr & 2)
            data |= (1 << pinout::PIN_ADDR[1]);
        if (addr & 4)
            data |= (1 << pinout::PIN_ADDR[2]);
        if constexpr (std::size(pinout::PIN_ADDR) >= 4) {
            if (addr & 8)
                data |= (1 << pinout::PIN_ADDR[3]);
        }
        if constexpr (std::size(pinout::PIN_ADDR) >= 5) {
            if (addr & 16)
                data |= (1 << pinout::PIN_ADDR[4]);
        }
        return data;
    };

    const size_t n_addr = 1u << matrixmap.n_addr_lines;
    const size_t pixels_across = matrixmap.pixels_across;
    uint32_t addr_bits = calc_addr_bits(n_addr - 1);
    std::vector<uint32_t> row_words;
    row_words.reserve(pixels_across);

    int32_t active_time = old_active_time;

    for (size_t addr = 0; addr < n_addr; addr++) {
        for (auto &schedule_ent : sched) {
            uint32_t r_mask = 1 << (20 + schedule_ent.shift);
            uint32_t g_mask = 1 << (10 + schedule_ent.shift);
            uint32_t b_mask = 1 << (0 + schedule_ent.shift);

            row_words.clear();
            auto mapiter = matrixmap.map.begin() +
                           matrixmap.n_lanes * addr * pixels_across;
            for (size_t x = 0; x < pixels_across; x++) {
                uint32_t data = addr_bits;
                for (size_t px = 0; px < matrixmap.n_lanes; px++) {
                    assert(mapiter != matrixmap.map.end());
                    auto pixel0 = pixels[*mapiter++];
                    auto r_bit = pixel0 & r_mask;
                    auto g_bit = pixel0 & g_mask;
                    auto b_bit = pixel0 & b_mask;

                    if (r_bit)
                        data |= (1 << pinout::PIN_RGB[px * 3 + 0]);
                    if (g_bit)
                        data |= (1 << pinout::PIN_RGB[px * 3 + 1]);
                    if (b_bit)
                        data |= (1 << pinout::PIN_RGB[px * 3 + 2]);
                }

                bool active = active_time > 0;
                active_time--;
                data |= active ? pinout::oe_active : pinout::oe_inactive;
                row_words.push_back(data);
            }

            const uint32_t active_hold_word = addr_bits | pinout::oe_active;
            const uint32_t inactive_hold_word = addr_bits | pinout::oe_inactive;

            if (row_words_are_uniform(row_words)) {
                frame_words.push_back(command_row_repeat | uint32_t(pixels_across - 1));
                frame_words.push_back(row_words.front());
            } else {
                frame_words.push_back(command_row_literal | uint32_t(pixels_across - 1));
                frame_words.insert(frame_words.end(), row_words.begin(), row_words.end());
            }
            frame_words.push_back(encode_delay_count(
                active_time * CLOCKS_PER_DATA / CLOCKS_PER_DELAY - DELAY_OVERHEAD));
            frame_words.push_back(active_hold_word);
            frame_words.push_back(encode_delay_count(pinout::post_oe_delay));
            frame_words.push_back(inactive_hold_word);
            frame_words.push_back(encode_delay_count(pinout::post_latch_delay));

            active_time = schedule_ent.active_time;

            addr_bits = calc_addr_bits(addr);
            frame_words.push_back(encode_delay_count(pinout::post_addr_delay));
            frame_words.push_back(addr_bits | pinout::oe_inactive);
        }
    }

    result.reserve(frame_words.size() * slab_copy_count);
    for (size_t copy_index = 0; copy_index < slab_copy_count; copy_index++) {
        result.insert(result.end(), frame_words.begin(), frame_words.end());
    }
}

} // namespace piomatter
