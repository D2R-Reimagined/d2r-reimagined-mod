#pragma once

#include <array>
#include <cstdint>
#include <span>

namespace rotations {
// Reimagined desecratedzones.json at 259768f269baefd01758a8961d785ae10d98879d.

inline constexpr uint32_t Act1Manual[]{
    2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38
};
inline constexpr uint32_t Act1Auto[]{
    2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38
};
inline constexpr uint32_t Act2Auto[]{
    41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74
};
inline constexpr uint32_t Act3Auto[]{
    76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102
};
inline constexpr uint32_t Act4Auto[]{
    39, 104, 105, 106, 107, 108
};
inline constexpr uint32_t Act5Auto[]{
    110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132
};

struct Rotation {
    uint32_t act;
    std::span<const uint32_t> levels;
};

inline constexpr std::array WholeActs{
    Rotation{1, Act1Manual},
    Rotation{1, Act1Auto},
    Rotation{2, Act2Auto},
    Rotation{3, Act3Auto},
    Rotation{4, Act4Auto},
    Rotation{5, Act5Auto},
};

}  // namespace rotations
