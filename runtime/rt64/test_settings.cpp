// SPDX-License-Identifier: MIT OR Apache-2.0
#include "settings.h"
#undef NDEBUG
#include <cassert>
#include <cstdio>
#include <fstream>
int main() {
    using namespace plaid_settings;
    Settings s = parse(json::parse(R"({"unknown":42,"fullscreen":true,"n64Mode":true,"aspect":"21:9","players":[{"connected":true,"type":"keyboard","bindings":{"a":"P","b":""}},{"type":"xbox","connected":true}]})"));
    assert(s.fullscreen && s.n64Mode && s.aspect == "21:9");
    assert(s.players[0].bindings.at("a") == "P" && s.players[0].bindings.at("b").empty());
    assert(s.players[1].bindings.at("z") == "Button 6" && s.players[1].connected);
    const char *path = "plaid-settings-test.json";
    { std::ofstream f(path); f << "{ broken"; }
    assert(!load(path, s) && s.players[0].bindings.at("a") == "P");
    Settings default_settings;
    assert(!load(path, default_settings) && default_settings.players[0].bindings.at("a") == "X" && !default_settings.fullscreen);
    std::remove(path);
    assert(!load(path, s));
    bool rejected = false;
    try { parse(json::parse(R"({"resolutionScale":-1})")); } catch (const std::exception &) { rejected = true; }
    assert(rejected);
}
