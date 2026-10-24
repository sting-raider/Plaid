# Local corrections to the pinned MIT RT64 reference. Generate build copies;
# keep .refs untouched and reject a changed patch context at configure time.
# RT64 source: Copyright (c) 2024 RT64 Contributors; see .refs/rt64/LICENSE.
function(plaid_rt64_patch unit before after)
    get_filename_component(original "${RT64_DIR}/src/${unit}.cpp" ABSOLUTE)
    file(READ "${original}" source)
    string(REPLACE "${before}" "" removed "${source}")
    string(LENGTH "${source}" old_size)
    string(LENGTH "${removed}" removed_size)
    string(LENGTH "${before}" match_size)
    math(EXPR expected_size "${old_size} - ${match_size}")
    if(NOT removed_size EQUAL expected_size)
        message(FATAL_ERROR "RT64 patch context must occur exactly once: ${unit}")
    endif()
    string(REPLACE "${before}" "${after}" patched "${source}")
    get_filename_component(name "${unit}" NAME)
    set(copy "${CMAKE_CURRENT_BINARY_DIR}/patched/${name}.cpp")
    file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/patched")
    file(WRITE "${copy}.tmp" "${patched}")
    configure_file("${copy}.tmp" "${copy}" COPYONLY)
    get_filename_component(original_dir "${original}" DIRECTORY)
    set_source_files_properties("${copy}" TARGET_DIRECTORY rt64
        PROPERTIES INCLUDE_DIRECTORIES "${original_dir}")
    get_target_property(sources rt64 SOURCES)
    list(FIND sources "${original}" index)
    if(index LESS 0)
        message(FATAL_ERROR "RT64 compilation unit missing: ${original}")
    endif()
    list(REMOVE_ITEM sources "${original}")
    list(APPEND sources "${copy}")
    set_property(TARGET rt64 PROPERTY SOURCES "${sources}")
endfunction()

# A reversed integer T range does not upload TMEM (pinned ares parallel-rdp,
# Renderer::load_tile). Otherwise the unsigned row count wraps to billions.
plaid_rt64_patch(hle/rt64_rdp
    "if (t.uls > t.lrs) {"
    "if (t.uls > t.lrs || (t.ult >> 2) > (t.lrt >> 2)) {")

# Report every completed native-target readback, including equal-valued bytes.
# Plaid mirrors these spans into guest RAM and applies its normal cache guards.
plaid_rt64_patch(hle/rt64_state
    "                pairCursor = framebufferPairCursor;\n                while (pairCursor < maxFramebufferPair) {\n                    if (getFramebufferPairs(pairCursor)) {\n                        colorFb->copyNativeToRAM(&RDRAM[colorFb->addressStart], colorWriteWidth, colorRowStart, std::min(colorRowEnd, colorFb->height));\n\n                        if (depthWriteWidth > 0) {\n                            depthFb->copyNativeToRAM(&RDRAM[depthFb->addressStart], depthWriteWidth, depthRowStart, std::min(depthRowEnd, depthFb->height));\n                        }\n                    }\n\n                    pairCursor++;\n                }"
    "                extern void plaidReadback(uint32_t address, uint32_t size);\n                pairCursor = framebufferPairCursor;\n                while (pairCursor < maxFramebufferPair) {\n                    if (getFramebufferPairs(pairCursor)) {\n                        colorFb->copyNativeToRAM(&RDRAM[colorFb->addressStart], colorWriteWidth, colorRowStart, std::min(colorRowEnd, colorFb->height));\n                        const uint32_t colorReadbackRowBytes = colorFb->imageRowBytes(colorWriteWidth);\n                        const uint32_t colorReadbackRowEnd = std::min(colorRowEnd, colorFb->height);\n                        plaidReadback(colorFb->addressStart + colorRowStart * colorReadbackRowBytes,\n                            (colorReadbackRowEnd - colorRowStart) * colorReadbackRowBytes);\n\n                        if (depthWriteWidth > 0) {\n                            depthFb->copyNativeToRAM(&RDRAM[depthFb->addressStart], depthWriteWidth, depthRowStart, std::min(depthRowEnd, depthFb->height));\n                            const uint32_t depthReadbackRowBytes = depthFb->imageRowBytes(depthWriteWidth);\n                            const uint32_t depthReadbackRowEnd = std::min(depthRowEnd, depthFb->height);\n                            plaidReadback(depthFb->addressStart + depthRowStart * depthReadbackRowBytes,\n                                (depthReadbackRowEnd - depthRowStart) * depthReadbackRowBytes);\n                        }\n                    }\n\n                    pairCursor++;\n                }")

# Fill mode uses GPU clears, which ignore the rasterizer's scissor state.
# Clip in render-target coordinates, using each rectangle's own alignment.
plaid_rt64_patch(render/rt64_framebuffer_renderer
    [=[                    clearRect.rect = convertFixedRect(call.callDesc.rect, p.resolutionScale, p.fbWidth, invRatioScale, extOriginPercentage, horizontalMisalignment, call.callDesc.rectLeftOrigin, call.callDesc.rectRightOrigin);]=]
    [=[                    clearRect.rect = convertFixedRect(call.callDesc.rect, p.resolutionScale, p.fbWidth, invRatioScale, extOriginPercentage, horizontalMisalignment, call.callDesc.rectLeftOrigin, call.callDesc.rectRightOrigin);
                    const RenderRect fillScissor = convertFixedRect(call.callDesc.scissorRect, p.resolutionScale, p.fbWidth, invRatioScale, extOriginPercentage, horizontalMisalignment, call.callDesc.scissorLeftOrigin, call.callDesc.scissorRightOrigin);
                    clearRect.rect = RenderRect{
                        std::max(clearRect.rect.left, fillScissor.left),
                        std::max(clearRect.rect.top, fillScissor.top),
                        std::min(clearRect.rect.right, fillScissor.right),
                        std::min(clearRect.rect.bottom, fillScissor.bottom)
                    };
                    if (clearRect.rect.isEmpty()) {
                        instanceDrawCall.type = InstanceDrawCall::Type::Unknown;
                    }]=])
