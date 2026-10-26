// Plaid's bridge to RT64 (ADR-0163). SPDX-License-Identifier: MIT OR Apache-2.0
//
// One renderer thread owns the RT64 application and its SDL window: it creates
// both, runs every call into RT64 and pumps window events. The runtime hands it
// graphics tasks and VI state through the C ABI below and waits for each.
//
// Plaid keeps guest RAM in big-endian byte order; RT64 reads RDRAM as 32-bit
// host words (the Mupen64Plus layout). Before a task, words the guest changed
// since the last task are copied in swapped. Completed framebuffer readbacks
// return through the runtime's memory protection and cache-coherence boundary.

#include "hle/rt64_application.h"
#define PLAID_GFX_API __declspec(dllexport)
#include "readback.h"

#include <SDL.h>

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <cstring>
#include <functional>
#include <mutex>
#include <thread>
#include <vector>

namespace {

constexpr uint32_t RamSize = 0x800000;

std::vector<uint8_t> rdram(RamSize), seen(RamSize), dmem(0x1000), imem(0x1000), header(0x40);
uint32_t mi_intr, dpc[9], vi[14];
std::unique_ptr<RT64::Application> app;
Readback readback;

std::mutex lock;
std::condition_variable wake;
std::function<void()> job;
bool idle = true, ready = false, opened = false, closed = false;
std::atomic<uint32_t> input{0};  // buttons << 16 | stick x << 8 | stick y
thread_local bool on_renderer = false;
SDL_AudioDeviceID audio = 0;
uint32_t audio_rate = 0;
std::vector<int16_t> pcm;

// Runs f on the renderer thread and waits for it.
void run(std::function<void()> f) {
    if (on_renderer) { f(); return; }
    std::unique_lock<std::mutex> l(lock);
    wake.wait(l, [] { return idle; });
    job = std::move(f);
    idle = false;
    wake.notify_all();
    wake.wait(l, [] { return idle; });
}

void sync_ram(const uint8_t *ram, const uint8_t *dirty_pages = nullptr) {
    for (uint32_t page = 0; page < RamSize; page += 4096) {
        if (dirty_pages && !dirty_pages[page / 4096]) continue;
        for (uint32_t p = page; p < page + 4096; p += 4) {
            if (std::memcmp(&seen[p], &ram[p], 4)) {
                std::memcpy(&seen[p], &ram[p], 4);
                uint32_t w = uint32_t(ram[p]) << 24 | uint32_t(ram[p + 1]) << 16 | uint32_t(ram[p + 2]) << 8 | ram[p + 3];
                std::memcpy(&rdram[p], &w, 4);
            }
        }
    }
}

void renderer() {
    on_renderer = true;
    RT64::Application::Core core{};
    core.window = {};  // RT64 opens its own window on this thread
    core.HEADER = header.data();
    core.RDRAM = rdram.data();
    core.DMEM = dmem.data();
    core.IMEM = imem.data();
    core.MI_INTR_REG = &mi_intr;
    uint32_t **dp[] = {&core.DPC_START_REG, &core.DPC_END_REG, &core.DPC_CURRENT_REG, &core.DPC_STATUS_REG,
        &core.DPC_CLOCK_REG, &core.DPC_BUFBUSY_REG, &core.DPC_PIPEBUSY_REG, &core.DPC_TMEM_REG};
    for (int i = 0; i < 8; i++) *dp[i] = &dpc[i];
    // the order of plaid_gfx_screen's registers
    uint32_t **v[] = {&core.VI_STATUS_REG, &core.VI_ORIGIN_REG, &core.VI_WIDTH_REG, &core.VI_INTR_REG,
        &core.VI_V_CURRENT_LINE_REG, &core.VI_TIMING_REG, &core.VI_V_SYNC_REG, &core.VI_H_SYNC_REG, &core.VI_LEAP_REG,
        &core.VI_H_START_REG, &core.VI_V_START_REG, &core.VI_V_BURST_REG, &core.VI_X_SCALE_REG, &core.VI_Y_SCALE_REG};
    for (int i = 0; i < 14; i++) *v[i] = &vi[i];
    core.checkInterrupts = [] {};  // the runtime posts SP and DP completion itself

    RT64::ApplicationConfiguration config;
    config.appId = "plaid";
    config.useConfigurationFile = false;
    app = std::make_unique<RT64::Application>(core, config);
    // Framebuffer storage can have non-square pixels; present on the 4:3 TV
    // surface instead of fitting its storage dimensions to the window.
    app->enhancementConfig.presentation.removeBlackBorders = false;
    bool ok = app->setup(0) == RT64::Application::SetupResult::Success;
    {
        std::lock_guard<std::mutex> l(lock);
        opened = ok;
        ready = true;
    }
    wake.notify_all();
    if (!ok) return;

    for (;;) {
        std::function<void()> f;
        {
            std::unique_lock<std::mutex> l(lock);
            wake.wait_for(l, std::chrono::milliseconds(4), [] { return !idle; });
            if (!idle) f = std::move(job);
        }
        if (f) {
            f();
            std::lock_guard<std::mutex> l(lock);
            idle = true;
            wake.notify_all();
        }
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) {
                std::lock_guard<std::mutex> l(lock);
                closed = true;
            }
        }
        // Keyboard as controller 1: X/C/Z = A/B/Z, Enter = START, Q/E = L/R,
        // I/K/J/L = C buttons, W/S/A/D = D-pad, arrows = stick.
        static const struct { SDL_Scancode key; uint32_t bit; } map[] = {
            {SDL_SCANCODE_X, 0x8000}, {SDL_SCANCODE_C, 0x4000}, {SDL_SCANCODE_Z, 0x2000},
            {SDL_SCANCODE_RETURN, 0x1000}, {SDL_SCANCODE_W, 0x0800}, {SDL_SCANCODE_S, 0x0400},
            {SDL_SCANCODE_A, 0x0200}, {SDL_SCANCODE_D, 0x0100}, {SDL_SCANCODE_Q, 0x0020},
            {SDL_SCANCODE_E, 0x0010}, {SDL_SCANCODE_I, 0x0008}, {SDL_SCANCODE_K, 0x0004},
            {SDL_SCANCODE_J, 0x0002}, {SDL_SCANCODE_L, 0x0001}};
        const Uint8 *k = SDL_GetKeyboardState(nullptr);
        uint32_t b = 0;
        for (const auto &m : map) b |= k[m.key] ? m.bit : 0;
        int x = (k[SDL_SCANCODE_RIGHT] - k[SDL_SCANCODE_LEFT]) * 80, y = (k[SDL_SCANCODE_UP] - k[SDL_SCANCODE_DOWN]) * 80;
        input = b << 16 | uint32_t(uint8_t(x)) << 8 | uint8_t(y);
    }
}

}  // namespace

// Called only after the pinned renderer completes a RAM readback.
void plaidReadback(uint32_t physical, uint32_t size) { readback.record(physical, size); }

extern "C" {

// Opens the window and renderer; 0 on success. rom_header: the first 0x40
// ROM bytes, which RT64 uses to identify the game.
__declspec(dllexport) int plaid_gfx_open(const uint8_t *rom_header) {
    std::memcpy(header.data(), rom_header, header.size());
    std::thread(renderer).detach();
    std::unique_lock<std::mutex> l(lock);
    wake.wait(l, [] { return ready; });
    return opened ? 0 : 1;
}

__declspec(dllexport) int plaid_gfx_native_rsp(int (*work)(void *), void *context) {
    if (!work) return 1;
    int result = 0;
    run([&] { result = work(context); });
    return result;
}

// Renders one graphics task. ram: guest RAM in big-endian order; the
// addresses are the OSTask's ucode, ucode_data and data_ptr.
__declspec(dllexport) int plaid_gfx_task(const uint8_t *ram, uint32_t ucode, uint32_t ucode_data, uint32_t data_ptr,
                                      plaid_gfx_writeback writeback, void *context) {
    readback.clear();
    const uint32_t textAddress = ucode & 0x3FFFFF8;
    const uint32_t dataAddress = ucode_data & 0x3FFFFF8;
    if (textAddress > RamSize - 0x1000 || dataAddress > RamSize - 0x1000)
        return PLAID_GFX_UNKNOWN_UCODE;
    int result = 0;
    run([=, &result] {
        sync_ram(ram);
        // Query current bytes even when a task reuses the same RAM addresses.
        const auto *gbi = app->interpreter->gbiManager.getGBIForUCode(
            rdram.data(), textAddress, dataAddress);
        if (!gbi || gbi->ucode == RT64::GBIUCode::Unknown) {
            result = PLAID_GFX_UNKNOWN_UCODE;
            return;
        }
        if (gbi != app->interpreter->hleGBI)
            app->interpreter->UCode.textAddress = ~0u;
        app->interpreter->loadUCodeGBI(textAddress, dataAddress, true);
        app->processDisplayLists(rdram.data(), data_ptr & 0x3FFFFFF, 0, true);
    });
    return result ? result : readback.finish(rdram, seen, writeback, context);
}

// Raw RDP commands produced by lowered RSP microcode, including partial lists.
__declspec(dllexport) int plaid_gfx_rdp(const uint8_t *ram, const uint8_t *commands, uint32_t size, const uint8_t *dirty_pages,
                                     plaid_gfx_writeback writeback, void *context) {
    readback.clear();
    run([=] {
        sync_ram(ram, dirty_pages);
        std::vector<uint32_t> words(size / 4);
        for (uint32_t p = 0; p < size; p += 4)
            words[p / 4] = uint32_t(commands[p]) << 24 | uint32_t(commands[p + 1]) << 16 |
                uint32_t(commands[p + 2]) << 8 | commands[p + 3];
        app->processDisplayLists(reinterpret_cast<uint8_t *>(words.data()), 0, size, false);
    });
    return readback.finish(rdram, seen, writeback, context);
}

// Presents the screen for one VI retrace. regs: STATUS, ORIGIN, WIDTH, INTR,
// V_CURRENT, BURST, V_SYNC, H_SYNC, LEAP, H_START, V_START, V_BURST, X_SCALE,
// Y_SCALE.
__declspec(dllexport) void plaid_gfx_screen(const uint32_t *regs) {
    run([=] {
        std::memcpy(vi, regs, sizeof vi);
        app->updateScreen();
    });
}

// Controller 1 from the window's keyboard: buttons << 16 | stick x << 8 | stick y.
__declspec(dllexport) uint32_t plaid_gfx_input(void) { return input; }

// Plays one AI buffer (ADR-0170): big-endian 16-bit stereo samples at rate Hz.
// Without an audio device the game runs silent.
__declspec(dllexport) void plaid_audio_play(const uint8_t *samples, uint32_t bytes, uint32_t rate) {
    if (rate != audio_rate) {
        audio_rate = rate;
        run([=] {  // SDL is initialized on the renderer thread
            if (audio) SDL_CloseAudioDevice(audio);
            SDL_AudioSpec want{}, have{};
            want.freq = int(rate);
            want.format = AUDIO_S16SYS;
            want.channels = 2;
            want.samples = 512;
            audio = SDL_InitSubSystem(SDL_INIT_AUDIO) == 0 ? SDL_OpenAudioDevice(nullptr, 0, &want, &have, 0) : 0;
            if (audio) SDL_PauseAudioDevice(audio, 0);
        });
    }
    if (!audio) return;
    pcm.resize(bytes / 2);
    for (uint32_t i = 0; i < bytes / 2; i++) pcm[i] = int16_t(samples[2 * i] << 8 | samples[2 * i + 1]);
    // shortcut: the AI model and the device run on different clocks; past
    // 200 ms of queued audio drop it rather than resample.
    if (SDL_GetQueuedAudioSize(audio) > rate * 4 / 5) SDL_ClearQueuedAudio(audio);
    SDL_QueueAudio(audio, pcm.data(), bytes);
}

// 1 once the user has closed the window.
__declspec(dllexport) int plaid_gfx_closed(void) {
    std::lock_guard<std::mutex> l(lock);
    return closed;
}

}
