// SPDX-License-Identifier: MIT OR Apache-2.0
// Launcher settings, parsed before the renderer thread starts.
#pragma once
#include <json/json.hpp>
#include <array>
#include <cmath>
#include <fstream>
#include <map>
#include <string>

namespace plaid_settings {
using json = nlohmann::json;
using Bindings = std::map<std::string, std::string>;
inline Bindings defaults(bool keyboard) {
    if (keyboard) return {{"a","X"},{"b","C"},{"z","Z"},{"start","Enter"},{"l","Q"},{"r","E"},
        {"cUp","I"},{"cDown","K"},{"cLeft","J"},{"cRight","L"},
        {"dUp","W"},{"dDown","S"},{"dLeft","A"},{"dRight","D"},
        {"stickUp","↑"},{"stickDown","↓"},{"stickLeft","←"},{"stickRight","→"}};
    return {{"a","Button 0"},{"b","Button 2"},{"z","Button 6"},{"start","Button 9"},
        {"l","Button 4"},{"r","Button 5"},{"cUp","Axis 3-"},{"cDown","Axis 3+"},
        {"cLeft","Axis 2-"},{"cRight","Axis 2+"},{"dUp","Button 12"},{"dDown","Button 13"},
        {"dLeft","Button 14"},{"dRight","Button 15"},{"stickUp","Axis 1-"},
        {"stickDown","Axis 1+"},{"stickLeft","Axis 0-"},{"stickRight","Axis 0+"}};
}
struct Player {
    bool connected = false;
    std::string type = "xbox";
    Bindings bindings = defaults(false);
    double deadzone = 12, range = 100;
};
struct Settings {
    std::array<Player, 4> players;
    std::string aspect = "4:3";
    double resolutionScale = 2;
    bool vsync = true, fullscreen = false, n64Mode = false;
    Settings() { players[0].connected = true; players[0].type = "keyboard"; players[0].bindings = defaults(true); }
};
inline Settings parse(const json &j) {
    if (!j.is_object()) throw std::runtime_error("settings must be an object");
    Settings s;
    if (j.contains("aspect")) {
        s.aspect = j.at("aspect").get<std::string>();
        if (s.aspect != "4:3" && s.aspect != "16:9" && s.aspect != "21:9" && s.aspect != "stretch")
            throw std::runtime_error("invalid aspect");
    }
    if (j.contains("resolutionScale")) s.resolutionScale = j.at("resolutionScale").get<double>();
    if (!std::isfinite(s.resolutionScale) || s.resolutionScale <= 0 || s.resolutionScale > 16)
        throw std::runtime_error("invalid scale");
    if (j.contains("vsync")) s.vsync = j.at("vsync").get<bool>();
    if (j.contains("fullscreen")) s.fullscreen = j.at("fullscreen").get<bool>();
    if (j.contains("n64Mode")) s.n64Mode = j.at("n64Mode").get<bool>();
    if (j.contains("players")) {
        const auto &players = j.at("players");
        if (!players.is_array() || players.size() > 4) throw std::runtime_error("invalid players");
        for (size_t i = 0; i < players.size(); ++i) {
            const auto &p = players.at(i);
            if (!p.is_object()) throw std::runtime_error("invalid player");
            auto &out = s.players[i];
            if (p.contains("connected")) out.connected = p.at("connected").get<bool>();
            if (p.contains("type")) out.type = p.at("type").get<std::string>();
            if (out.type != "keyboard" && out.type != "xbox" && out.type != "ds4" && out.type != "dualsense" &&
                out.type != "switchpro" && out.type != "n64usb" && out.type != "generic")
                throw std::runtime_error("invalid device");
            out.bindings = defaults(out.type == "keyboard");
            if (p.contains("bindings")) {
                const auto &b = p.at("bindings");
                if (!b.is_object()) throw std::runtime_error("invalid bindings");
                if (!b.empty()) out.bindings = b.get<Bindings>();
            }
            if (p.contains("deadzone")) out.deadzone = p.at("deadzone").get<double>();
            if (p.contains("range")) out.range = p.at("range").get<double>();
            if (!std::isfinite(out.deadzone) || out.deadzone < 0 || out.deadzone >= 100 ||
                !std::isfinite(out.range) || out.range < 0 || out.range > 150) throw std::runtime_error("invalid stick settings");
        }
    }
    return s;
}
inline bool load(const char *path, Settings &out) {
    try {
        std::ifstream file(path);
        if (!file) return false;
        json j = json::parse(file);
        out = parse(j);
        return true;
    } catch (const std::exception &) { return false; }
}
}
