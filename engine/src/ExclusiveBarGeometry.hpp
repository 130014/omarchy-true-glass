#pragma once

#include <algorithm>
#include <optional>

namespace ExclusiveBarGeometry {

// Plain logical-coordinate rectangle, kept independent of Hyprland types so the
// edge/zone rules can be exercised without a compositor or GL context.
struct Rect {
    double x, y, w, h;
};

enum class Edge { Top, Right, Bottom, Left };

// The exclusive edge is authoritative when valid; older compositor states may
// omit it, in which case anchors must identify exactly one edge unambiguously.
inline std::optional<unsigned> resolveEdge(unsigned anchor, unsigned exclusiveEdge,
                                           unsigned top, unsigned right, unsigned bottom, unsigned left) {
    constexpr unsigned EDGE_MASK = 15;
    unsigned edgeBit = exclusiveEdge & EDGE_MASK;
    if (!edgeBit) {
        const unsigned candidates = anchor & EDGE_MASK;
        const bool hasTop = candidates & top, hasBottom = candidates & bottom;
        const bool hasLeft = candidates & left, hasRight = candidates & right;
        const int verticalCount = static_cast<int>(hasTop) + static_cast<int>(hasBottom);
        const int horizontalCount = static_cast<int>(hasLeft) + static_cast<int>(hasRight);
        // A stock top/bottom bar has opposing left+right anchors, and a side bar
        // has opposing top+bottom anchors. The single anchor on the other axis is
        // the exclusive edge. Fully opposed or corner-only states are ambiguous.
        if (verticalCount == 1 && horizontalCount != 1) edgeBit = hasTop ? top : bottom;
        else if (horizontalCount == 1 && verticalCount != 1) edgeBit = hasLeft ? left : right;
    }
    if ((edgeBit != top && edgeBit != right && edgeBit != bottom && edgeBit != left) || !(anchor & edgeBit))
        return std::nullopt;
    return edgeBit;
}

// An exclusive zone only describes a bar when it is positive and its edge is
// unambiguous. Clamp to surface bounds: old strip-sized layers then retain their
// exact geometry, while fullscreen surfaces shrink to the reserved strip.
inline std::optional<Rect> reservedRect(Rect surface, int exclusive, unsigned anchor, unsigned exclusiveEdge,
                                        unsigned top, unsigned right, unsigned bottom, unsigned left) {
    if (exclusive <= 0 || surface.w <= 0 || surface.h <= 0)
        return std::nullopt;
    const auto resolved = resolveEdge(anchor, exclusiveEdge, top, right, bottom, left);
    if (!resolved) return std::nullopt;
    const unsigned edgeBit = *resolved;

    const double depth = std::min<double>(exclusive, edgeBit == top || edgeBit == bottom ? surface.h : surface.w);
    if (depth <= 0) return std::nullopt;
    switch (static_cast<Edge>(edgeBit == top ? 0 : edgeBit == right ? 1 : edgeBit == bottom ? 2 : 3)) {
        case Edge::Top:    surface.h = depth; break;
        case Edge::Right:  surface.x += surface.w - depth; surface.w = depth; break;
        case Edge::Bottom: surface.y += surface.h - depth; surface.h = depth; break;
        case Edge::Left:   surface.w = depth; break;
    }
    return surface;
}

// Map a framebuffer-space strip to the full layer's unpadded sample UVs.
inline std::optional<Rect> relativeUV(Rect strip, Rect frame) {
    if (frame.w <= 0 || frame.h <= 0 || strip.w <= 0 || strip.h <= 0)
        return std::nullopt;
    return Rect{(strip.x - frame.x) / frame.w, (strip.y - frame.y) / frame.h,
                strip.w / frame.w, strip.h / frame.h};
}

// Rotate the top-bar inset convention with the reserved edge. Input order and
// output order are top,right,bottom,left. The top-bar's zero inset is its
// screen-inward edge; the three expanding (-80) sides rotate with it.
inline void orientInsets(float out[4], const float in[4], unsigned edge,
                         unsigned top, unsigned right, unsigned bottom, unsigned left) {
    if (edge == top) { std::copy(in, in + 4, out); return; }
    if (edge == bottom) { out[0] = in[2]; out[1] = in[3]; out[2] = in[0]; out[3] = in[1]; return; }
    if (edge == right) { out[0] = in[3]; out[1] = in[0]; out[2] = in[1]; out[3] = in[2]; return; }
    if (edge == left) { out[0] = in[1]; out[1] = in[2]; out[2] = in[3]; out[3] = in[0]; return; }
    std::copy(in, in + 4, out);
}

} // namespace ExclusiveBarGeometry
