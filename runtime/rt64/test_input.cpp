// SPDX-License-Identifier: MIT OR Apache-2.0
#define SDL_MAIN_HANDLED
#include "input.h"
#undef NDEBUG
#include <cassert>
#include <cstdio>
#include <fstream>
int main() {
    plaid_settings::Player p;
    p.connected = true; p.type = "keyboard"; p.bindings = plaid_settings::defaults(true);
    Uint8 keys[SDL_NUM_SCANCODES]{};
    keys[SDL_SCANCODE_X] = keys[SDL_SCANCODE_UP] = 1;
    assert(plaid_input::sample(p, keys, nullptr) == 0x80000050u);
    const char *path = "plaid-input-test.json";
    { std::ofstream f(path); f << R"({"players":[{"connected":true,"type":"keyboard","bindings":{"a":"P","stickUp":"Space"}}]})"; }
    plaid_settings::Settings settings;
    assert(plaid_settings::load(path, settings));
    std::remove(path);
    p = settings.players[0];
    keys[SDL_SCANCODE_P] = keys[SDL_SCANCODE_SPACE] = 1;
    assert(plaid_input::sample(p, keys, nullptr) == 0x80000050u);
    keys[SDL_SCANCODE_P] = 0;
    assert(plaid_input::sample(p, keys, nullptr) == 0x50u);
    p.connected = false;
    assert(plaid_input::sample(p, keys, nullptr) == 0);
    // keyboard + pad on Player 1: buttons combine, each axis keeps the larger push
    assert(plaid_input::merge(0x80000050u, 0x4000b000u) == 0xc000b050u);
    assert(plaid_input::default_pad(p).bindings.at("a") == "Button 0");
}
