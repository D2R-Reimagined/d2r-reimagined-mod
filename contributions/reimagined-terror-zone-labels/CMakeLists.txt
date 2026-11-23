cmake_minimum_required(VERSION 3.29)
project(reimagined_terror_zone_labels LANGUAGES CXX RC)

set(PLUGIN_SDK_DIR "${CMAKE_CURRENT_SOURCE_DIR}/deps/PluginSDK" CACHE PATH "Pinned D2RLoader PluginSDK 0.3.0 checkout")
add_subdirectory("${PLUGIN_SDK_DIR}" sdk EXCLUDE_FROM_ALL)
add_library(d2rl-reimagined-terror-zone-labels SHARED src/plugin.cpp src/plugin.rc)
target_link_libraries(d2rl-reimagined-terror-zone-labels PRIVATE D2RLPlugin::D2RLPlugin)
target_compile_features(d2rl-reimagined-terror-zone-labels PRIVATE cxx_std_20)
target_compile_options(d2rl-reimagined-terror-zone-labels PRIVATE
    $<$<COMPILE_LANGUAGE:CXX>:/W4 /permissive- /utf-8 /EHsc>)
set_target_properties(d2rl-reimagined-terror-zone-labels PROPERTIES MSVC_RUNTIME_LIBRARY MultiThreaded)
