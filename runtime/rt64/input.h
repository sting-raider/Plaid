// SPDX-License-Identifier: MIT OR Apache-2.0
#pragma once
#include <SDL.h>
#include "settings.h"
#include <algorithm>
#include <array>
#include <cstdlib>

namespace plaid_input {
inline SDL_Scancode key(const std::string &name) {
    if (name == u8"↑") return SDL_SCANCODE_UP;
    if (name == u8"↓") return SDL_SCANCODE_DOWN;
    if (name == u8"←") return SDL_SCANCODE_LEFT;
    if (name == u8"→") return SDL_SCANCODE_RIGHT;
    if (name == "Enter") return SDL_SCANCODE_RETURN;
    if (name == " ") return SDL_SCANCODE_SPACE;
    return SDL_GetScancodeFromName(name.c_str());
}
// Browser standard mapping is not the same numeric order as SDL's enum.
inline float level(const std::string &value, bool keyboard, const Uint8 *keys, SDL_GameController *pad,
                   double deadzone, double range) {
    if (keyboard) { auto k = key(value); return k != SDL_SCANCODE_UNKNOWN && keys[k] ? 1.f : 0.f; }
    if (!pad) return 0;
    int n = -1; char suffix = 0, extra = 0;
    if (sscanf(value.c_str(), "Button %d%c", &n, &extra) == 1) {
        static const SDL_GameControllerButton buttons[] = {SDL_CONTROLLER_BUTTON_A, SDL_CONTROLLER_BUTTON_B,
            SDL_CONTROLLER_BUTTON_X, SDL_CONTROLLER_BUTTON_Y, SDL_CONTROLLER_BUTTON_LEFTSHOULDER,
            SDL_CONTROLLER_BUTTON_RIGHTSHOULDER, SDL_CONTROLLER_BUTTON_INVALID, SDL_CONTROLLER_BUTTON_INVALID,
            SDL_CONTROLLER_BUTTON_BACK, SDL_CONTROLLER_BUTTON_START, SDL_CONTROLLER_BUTTON_LEFTSTICK,
            SDL_CONTROLLER_BUTTON_RIGHTSTICK, SDL_CONTROLLER_BUTTON_DPAD_UP, SDL_CONTROLLER_BUTTON_DPAD_DOWN,
            SDL_CONTROLLER_BUTTON_DPAD_LEFT, SDL_CONTROLLER_BUTTON_DPAD_RIGHT, SDL_CONTROLLER_BUTTON_GUIDE};
        if (n == 6 || n == 7) return SDL_GameControllerGetAxis(pad, n == 6 ? SDL_CONTROLLER_AXIS_TRIGGERLEFT : SDL_CONTROLLER_AXIS_TRIGGERRIGHT) / 32767.f;
        if (n < 0 || n >= int(sizeof buttons / sizeof *buttons)) return 0;
        return SDL_GameControllerGetButton(pad, buttons[n]) ? 1.f : 0.f;
    }
    if (sscanf(value.c_str(), "Axis %d%c%c", &n, &suffix, &extra) != 2 || n < 0 || n > 3 || (suffix != '+' && suffix != '-')) return 0;
    float v = SDL_GameControllerGetAxis(pad, static_cast<SDL_GameControllerAxis>(n)) / 32767.f;
    v = std::max(0.f, std::min(1.f, v * (suffix == '+' ? 1.f : -1.f)));
    return v > deadzone / 100 ? std::min(1.f, float(v * range / 100)) : 0.f;
}
inline uint32_t sample(const plaid_settings::Player &p, const Uint8 *keys, SDL_GameController *pad) {
    if (!p.connected) return 0;
    auto get = [&](const char *name) {
        auto it = p.bindings.find(name);
        return it == p.bindings.end() ? 0.f : level(it->second, p.type == "keyboard", keys, pad, p.deadzone, p.range);
    };
    static const std::array<std::pair<const char *, uint32_t>, 14> bits = {{{"a",0x8000},{"b",0x4000},{"z",0x2000},
        {"start",0x1000},{"dUp",0x0800},{"dDown",0x0400},{"dLeft",0x0200},{"dRight",0x0100},
        {"l",0x0020},{"r",0x0010},{"cUp",0x0008},{"cDown",0x0004},{"cLeft",0x0002},{"cRight",0x0001}}};
    uint32_t buttons = 0;
    for (const auto &bit : bits) if (get(bit.first) > .5f) buttons |= bit.second;
    int x = int((get("stickRight") - get("stickLeft")) * 80);
    int y = int((get("stickUp") - get("stickDown")) * 80);
    return buttons << 16 | uint32_t(uint8_t(x)) << 8 | uint8_t(y);
}
// A pad with the standard layout and the given player's stick tuning.
inline plaid_settings::Player default_pad(const plaid_settings::Player &like) {
    plaid_settings::Player p;
    p.connected = true;
    p.deadzone = like.deadzone;
    p.range = like.range;
    return p;
}
// Two input words for one player: buttons combine, each stick axis takes the larger push.
inline uint32_t merge(uint32_t a, uint32_t b) {
    auto axis = [](uint32_t w, int shift) { return int8_t(uint8_t(w >> shift)); };
    auto pick = [](int8_t u, int8_t v) { return uint8_t(std::abs(int(u)) >= std::abs(int(v)) ? u : v); };
    return ((a | b) & 0xffff0000u) | uint32_t(pick(axis(a, 8), axis(b, 8))) << 8 | pick(axis(a, 0), axis(b, 0));
}
}
