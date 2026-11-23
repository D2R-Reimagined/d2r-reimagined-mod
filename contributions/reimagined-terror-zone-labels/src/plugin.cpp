#include <D2RLPlugin/api.h>
#include <D2RLPlugin/lifecycle_events.h>
#include <D2RLPlugin/localization.h>
#include <windows.h>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string_view>

#include "rotations.h"

namespace {
constexpr D2RL::PluginInfo info{
    .infoSize = D2RL::PluginInfoSize,
    .abiVersion = D2RL_PLUGIN_ABI_VERSION,
    .id = "reimagined-terror-zone-labels",
    .name = "Reimagined Terror Zone Labels",
    .version = "0.1.1",
    .author = "RuffnecKk",
    .description = "Shows act names for whole-act Terror Zones on the automap.",
    .flags = D2RL::PluginFlags::Client | D2RL::PluginFlags::NativeHooks,
};

namespace d2r {
uintptr_t imageBase{};

template<class T>
const T& At(const void* object, int offset) noexcept {
    return *reinterpret_cast<const T*>(static_cast<const std::byte*>(object) + offset);
}

template<class T>
T Engine(uintptr_t rva) noexcept {
    return reinterpret_cast<T>(imageBase + rva);
}
}

constexpr uintptr_t AppendSite = 0x1475406;
constexpr uintptr_t AppendFormat = 0x783d0;
constexpr uintptr_t OutsideSite = 0x14755a0;
constexpr uintptr_t RenderZoneNames = 0x137c2b0;
constexpr uintptr_t ActiveZoneState = 0x2a236e0;
constexpr int ActiveEntries = 0x80;
constexpr int ActiveCount = 0x88;
constexpr std::size_t MaxActiveAreas = 256;
constexpr std::array ActKeys{"d2r:act1", "d2r:act2", "d2r:act3", "d2r:act4", "d2r:act5"};

struct ActiveArea {
    uint32_t levelId;
    std::byte otherFields[16];
};
static_assert(sizeof(ActiveArea) == 0x14);

using AppendFn = void (*)(void*, const char*, ...) noexcept;
using ZoneNamesFn = void (*)(std::size_t, const uint32_t*, const char*, std::size_t, char*, uint32_t) noexcept;

constexpr uint8_t ExpectedCall[]{0xe8, 0xc5, 0x2f, 0xc0, 0xfe};
constexpr uint8_t ExpectedOutsideCall[]{0xe8, 0x0b, 0x6d, 0xf0, 0xff};
const D2RL::PluginContext* plugin{};
const D2RL::LocalizationService* localization{};
int32_t currentLevel{-1};

template<std::size_t N>
bool Matches(uintptr_t rva, const uint8_t (&expected)[N]) noexcept {
    uint8_t actual[N]{};
    SIZE_T copied{};
    return ReadProcessMemory(GetCurrentProcess(), d2r::Engine<const void*>(rva), actual, N, &copied) &&
           copied == N && std::memcmp(actual, expected, N) == 0;
}

bool MatchesAutomap() noexcept {
    constexpr uint8_t inside[]{0x44,0x8b,0xc3,0x48,0x8b,0xd0,0x49,0x8b,0xcc,0xe8,0xc5,0x2f,0xc0,0xfe,
                               0xb2,0x0a,0x49,0x8b,0xcc,0xe8,0x3b,0xfc,0xff,0xff};
    constexpr uint8_t append[]{0x48,0x8b,0xc4,0x48,0x89,0x50,0x10,0x4c,0x89,0x40,0x18,0x4c,0x89,0x48,0x20,
                               0x53,0x55,0x56,0x57,0x41,0x56,0x41,0x57,0x48,0x83,0xec,0x48,0x48,0x8d,0x68,0x18,0x48};
    constexpr uint8_t list[]{0x48,0x8b,0x05,0xdf,0xe1,0x5a,0x01,0x48,0x8b,0x88,0x88,0x00,0x00,0x00,
                             0x48,0x8d,0x14,0x89,0x48,0x8b,0x88,0x80,0x00,0x00,0x00,0x4c,0x8d,0x2c,0x91};
    constexpr uint8_t outside[]{0x48,0x8b,0x0d,0x6b,0xe1,0x5a,0x01,0x48,0x8d,0x85,0xa0,0x00,0x00,0x00,
                                0xc7,0x44,0x24,0x28,0x0f,0x00,0x00,0x00,0x4c,0x8d,0x05,0x59,0x17,0x88,0x00,
                                0x41,0xb9,0x00,0x06,0x00,0x00,0x48,0x89,0x44,0x24,0x20,0x48,0x8b,0xd3,0x48,
                                0x8b,0x89,0x88,0x00,0x00,0x00,0xe8,0x0b,0x6d,0xf0,0xff};
    constexpr uint8_t names[]{0x48,0x89,0x5c,0x24,0x08,0x48,0x89,0x6c,0x24,0x10,0x48,0x89,0x74,0x24,0x18,
                              0x57,0x48,0x83,0xec,0x40,0x49,0x8b,0xd9,0x49,0x8b,0xf8,0x48,0x8b,0xf2,0x48,0x8b,0xe9};
    constexpr uint8_t grouping[]{0x40,0x55,0x53,0x56,0x57,0x41,0x55,0x48,0x8d,0xac,0x24,0xa0,0xfc,0xff,0xff,
                                 0x48,0x81,0xec,0x60,0x04,0x00,0x00,0x48,0x8b,0x05,0xeb,0xb3,0x61,0x01,0x48,0x33,0xc4};
    return d2r::imageBase && Matches(0x14753fd, inside) && Matches(AppendFormat, append) &&
           Matches(0x14754fa, list) && Matches(0x147556e, outside) &&
           Matches(RenderZoneNames, names) && Matches(0x13afec0, grouping);
}

const D2RL::LifecycleService* lifecycle{};
D2RL::Lifecycle::ListenerHandle levelListener = D2RL::Lifecycle::InvalidHandle;

void __cdecl UpdateLevel(const D2RL::PluginContext*, const D2RL::Lifecycle::GameplayEvent* event,
                         void*) noexcept {
    currentLevel = event->currentValue;
}

uint32_t FindWholeAct(uint32_t current, std::span<const ActiveArea> active) noexcept {
    if (std::ranges::find(active, current, &ActiveArea::levelId) == active.end()) {
        return 0;
    }
    for (const auto& rotation : rotations::WholeActs) {
        if (std::ranges::find(rotation.levels, current) != rotation.levels.end() &&
            std::ranges::all_of(rotation.levels, [&](uint32_t level) {
                return std::ranges::find(active, level, &ActiveArea::levelId) != active.end();
            })) {
            return rotation.act;
        }
    }
    return 0;
}

std::string_view LocalizeAct(uint32_t act, std::span<char> buffer) noexcept {
    uint32_t required{};
    const auto result = localization->getStringByKey(plugin, ActKeys[act - 1], buffer.data(),
                                                      static_cast<uint32_t>(buffer.size()), &required);
    if (result != D2RL::Localization::Result::Success || required < 2 ||
        required > buffer.size() || buffer[required - 1] != '\0') {
        return {};
    }
    return {buffer.data(), required - 1};
}

bool TryAppendAct(void* output) noexcept {
    if (currentLevel <= 0) {
        return false;
    }
    const auto* state = *d2r::Engine<const void* const*>(ActiveZoneState);
    if (state == nullptr) {
        return false;
    }
    const auto count = d2r::At<std::size_t>(state, ActiveCount);
    const auto* areas = d2r::At<const ActiveArea*>(state, ActiveEntries);
    if (areas == nullptr || count < 2 || count > MaxActiveAreas) {
        return false;
    }
    const auto act = FindWholeAct(static_cast<uint32_t>(currentLevel), {areas, count});
    if (act == 0) {
        return false;
    }

    char localized[128]{};
    if (LocalizeAct(act, localized).empty()) {
        return false;
    }
    d2r::Engine<AppendFn>(AppendFormat)(output, "%s", localized);
    return true;
}

void AppendInsideZone(void* output, const char* originalFormat, uint32_t level) noexcept {
    if (!TryAppendAct(output)) {
        d2r::Engine<AppendFn>(AppendFormat)(output, originalFormat, level);
    }
}

bool TryRenderActiveActs(std::span<const uint32_t> levels, char* output, std::size_t capacity,
                         uint32_t nameLimit) noexcept {
    std::array<bool, ActKeys.size()> complete{};
    for (const auto& rotation : rotations::WholeActs) {
        if (std::ranges::all_of(rotation.levels, [&](uint32_t id) {
                return std::ranges::find(levels, id) != levels.end();
            })) {
            complete[rotation.act - 1] = true;
        }
    }
    if (std::ranges::none_of(complete, [](bool value) { return value; })) {
        return false;
    }

    // A whole act can be active alongside a partial Terror Zone.
    std::array<uint32_t, MaxActiveAreas> remaining{};
    std::array<char, 0x600> text{};
    std::size_t used{};
    uint32_t labels{};
    for (std::size_t i = 0; i < complete.size(); ++i) {
        if (!complete[i]) {
            continue;
        }
        char localized[128]{};
        const auto name = LocalizeAct(static_cast<uint32_t>(i + 1), localized);
        if (name.empty()) {
            return false;
        }
        std::memcpy(text.data() + used, name.data(), name.size());
        used += name.size();
        text[used++] = '\n';
        ++labels;
    }
    const auto end = std::ranges::copy_if(levels, remaining.begin(), [&](uint32_t id) {
        return std::ranges::none_of(rotations::WholeActs, [&](const auto& rotation) {
            return complete[rotation.act - 1] &&
                   std::ranges::find(rotation.levels, id) != rotation.levels.end();
        });
    }).out;
    const auto count = static_cast<std::size_t>(end - remaining.begin());
    if (used >= capacity || labels >= nameLimit) {
        return false;
    }
    if (count != 0) {
        d2r::Engine<ZoneNamesFn>(RenderZoneNames)(count, remaining.data(), "%s\n",
            (std::min)(capacity, text.size()) - used, text.data() + used, nameLimit - labels);
    }
    const auto length = std::char_traits<char>::length(text.data());
    if (length >= capacity) {
        return false;
    }
    std::memcpy(output, text.data(), length + 1);
    return true;
}

void RenderOutsideZone(std::size_t count, const uint32_t* levels, const char* format,
                        std::size_t capacity, char* output, uint32_t nameLimit) noexcept {
    if (count > 1 && count <= MaxActiveAreas && levels != nullptr && output != nullptr &&
        format != nullptr && std::strcmp(format, "%s\n") == 0 &&
        TryRenderActiveActs({levels, count}, output, capacity, nameLimit)) {
        return;
    }
    d2r::Engine<ZoneNamesFn>(RenderZoneNames)(count, levels, format, capacity, output, nameLimit);
}

bool InstallCall(const D2RL::PluginContext* context, uintptr_t site,
                 const uint8_t (&expected)[5], uintptr_t handler) noexcept {
    const uintptr_t next = d2r::imageBase + site + sizeof(expected);
    SYSTEM_INFO system{};
    GetSystemInfo(&system);
    const uintptr_t step = system.dwAllocationGranularity;
    const uintptr_t start = next - next % step;
    constexpr uintptr_t Rel32Limit = 0x7fff0000;
    for (uintptr_t distance = step; distance <= Rel32Limit; distance += step) {
        auto* relay = static_cast<uint8_t*>(VirtualAlloc(reinterpret_cast<void*>(start + distance), 14,
                                                      MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
        if (relay == nullptr) {
            continue;
        }
        const uint8_t jump[]{0xff, 0x25, 0, 0, 0, 0};
        std::memcpy(relay, jump, sizeof(jump));
        std::memcpy(relay + sizeof(jump), &handler, sizeof(handler));
        DWORD oldProtection{};
        uint8_t call[sizeof(expected)]{0xe8};
        const auto displacement = static_cast<int32_t>(reinterpret_cast<uintptr_t>(relay) - next);
        std::memcpy(call + 1, &displacement, sizeof(displacement));
        if (VirtualProtect(relay, 14, PAGE_EXECUTE_READ, &oldProtection) &&
            FlushInstructionCache(GetCurrentProcess(), relay, 14) &&
            context->PatchBytes(site, expected, sizeof(expected), call, sizeof(call))) {
            // The Loader owns restoration of the patched call. Keep the relay
            // allocated until process exit, as a caller may still be returning.
            return true;
        }
        VirtualFree(relay, 0, MEM_RELEASE);
        return false;
    }
    return false;
}
}  // namespace

D2RL_PLUGIN_EXPORT const D2RL::PluginInfo* D2RLoaderGetPluginInfo() noexcept {
    return &info;
}

D2RL_PLUGIN_EXPORT bool D2RLoaderLoadPlugin(const D2RL::PluginContext* context) noexcept {
    if (context == nullptr || context->activeMod == nullptr ||
        (_stricmp(context->activeMod, "Reimagined") != 0 &&
         _stricmp(context->activeMod, "ReimaginedOfficial") != 0)) {
        return false;
    }
    d2r::imageBase = context->exeBase;
    if (!MatchesAutomap()) {
        context->LogWarn("Terror Zone Labels: unsupported automap formatter.");
        return false;
    }
    if (context->QueryService(&localization) != D2RL::ServiceQueryResult::Success ||
        !D2RL::HasLocalizationServiceField(localization, D2RL::LocalizationServiceRequiredSize) ||
        localization->getStringByKey == nullptr) {
        context->LogWarn("Terror Zone Labels: Localization v2 unavailable.");
        return false;
    }
    constexpr auto lifecycleBytes = static_cast<uint32_t>(offsetof(D2RL::LifecycleService,
        unregisterGameplayEventListener) + sizeof(D2RL::Lifecycle::UnregisterGameplayEventListenerFn));
    if (context->QueryService(&lifecycle) != D2RL::ServiceQueryResult::Success ||
        !D2RL::HasLifecycleServiceField(lifecycle, lifecycleBytes) ||
        lifecycle->registerGameplayEventListener == nullptr ||
        lifecycle->unregisterGameplayEventListener == nullptr) {
        context->LogWarn("Terror Zone Labels: gameplay event service unavailable.");
        return false;
    }

    using namespace D2RL::Lifecycle;
    const GameplayEventListener listener{.structSize = GameplayEventListenerSize,
                                         .kind = GameplayEventKind::LevelChanged,
                                         .callback = UpdateLevel};
    plugin = context;
    if (lifecycle->registerGameplayEventListener(context, &listener, &levelListener) != Result::Success) {
        plugin = nullptr;
        return false;
    }
    if (!InstallCall(context, AppendSite, ExpectedCall, reinterpret_cast<uintptr_t>(&AppendInsideZone))) {
        lifecycle->unregisterGameplayEventListener(context, levelListener);
        levelListener = InvalidHandle;
        plugin = nullptr;
        context->LogWarn("Terror Zone Labels: automap formatter call unavailable.");
        return false;
    }
    if (InstallCall(context, OutsideSite, ExpectedOutsideCall, reinterpret_cast<uintptr_t>(&RenderOutsideZone))) {
        context->LogInfo("Terror Zone Labels: inside- and outside-zone act labels enabled.");
    } else {
        context->LogWarn("Terror Zone Labels: outside-zone formatter unavailable; inside-zone labels enabled.");
    }
    return true;
}

D2RL_PLUGIN_EXPORT void D2RLoaderUnloadPlugin() noexcept {
    if (levelListener != D2RL::Lifecycle::InvalidHandle) {
        lifecycle->unregisterGameplayEventListener(plugin, levelListener);
        levelListener = D2RL::Lifecycle::InvalidHandle;
    }
    currentLevel = -1;
}
