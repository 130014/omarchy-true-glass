#include "../engine/src/ExclusiveBarGeometry.hpp"
#include <cassert>
#include <cmath>

using ExclusiveBarGeometry::Rect;

static bool same(Rect a, Rect b) {
    return std::abs(a.x - b.x) < 1e-9 && std::abs(a.y - b.y) < 1e-9 &&
           std::abs(a.w - b.w) < 1e-9 && std::abs(a.h - b.h) < 1e-9;
}

int main() {
    constexpr unsigned top = 1, bottom = 2, left = 4, right = 8;
    const auto fullTop = ExclusiveBarGeometry::reservedRect({0, 0, 1536, 864}, 28, top | left | right, top,
                                                             top, right, bottom, left);
    const auto oldTop = ExclusiveBarGeometry::reservedRect({0, 0, 1536, 28}, 28, top | left | right, top,
                                                            top, right, bottom, left);
    assert(fullTop && oldTop && same(*fullTop, *oldTop));
    const auto topWithoutEdge = ExclusiveBarGeometry::reservedRect({0, 0, 1536, 864}, 28, top | left | right, 0,
                                                                    top, right, bottom, left);
    assert(topWithoutEdge && same(*topWithoutEdge, *oldTop));

    const auto fullBottom = ExclusiveBarGeometry::reservedRect({0, 0, 1536, 864}, 32, bottom | left | right, bottom,
                                                                top, right, bottom, left);
    const auto oldBottom = ExclusiveBarGeometry::reservedRect({0, 832, 1536, 32}, 32, bottom | left | right, bottom,
                                                               top, right, bottom, left);
    assert(fullBottom && oldBottom && same(*fullBottom, *oldBottom));

    const auto fullLeft = ExclusiveBarGeometry::reservedRect({0, 0, 1536, 864}, 30, top | bottom | left, left,
                                                              top, right, bottom, left);
    const auto oldLeft = ExclusiveBarGeometry::reservedRect({0, 0, 30, 864}, 30, top | bottom | left, left,
                                                             top, right, bottom, left);
    assert(fullLeft && oldLeft && same(*fullLeft, *oldLeft));

    const auto fullRight = ExclusiveBarGeometry::reservedRect({0, 0, 1536, 864}, 30, top | bottom | right, right,
                                                               top, right, bottom, left);
    const auto oldRight = ExclusiveBarGeometry::reservedRect({1506, 0, 30, 864}, 30, top | bottom | right, right,
                                                              top, right, bottom, left);
    assert(fullRight && oldRight && same(*fullRight, *oldRight));

    // A larger output and fractional scale keep the operation in logical units;
    // scaling either result afterward is identical.
    const auto large = ExclusiveBarGeometry::reservedRect({0, 0, 5120, 2880}, 40, top | left | right, top,
                                                           top, right, bottom, left);
    assert(large && same(*large, {0, 0, 5120, 40}));
    const Rect fullScaled{fullTop->x * 1.5, fullTop->y * 1.5, fullTop->w * 1.5, fullTop->h * 1.5};
    const Rect oldScaled{oldTop->x * 1.5, oldTop->y * 1.5, oldTop->w * 1.5, oldTop->h * 1.5};
    assert(same(fullScaled, oldScaled));
    assert(!ExclusiveBarGeometry::reservedRect({0, 0, 1536, 864}, 0, top | left | right, top,
                                                top, right, bottom, left));
    assert(!ExclusiveBarGeometry::reservedRect({0, 0, 1536, 864}, 28, top | left | right, bottom,
                                                top, right, bottom, left));

    const float topInsets[4] = {-80, -80, 0, -80};
    float rightInsets[4];
    ExclusiveBarGeometry::orientInsets(rightInsets, topInsets, right, top, right, bottom, left);
    assert(rightInsets[0] == -80 && rightInsets[1] == -80 && rightInsets[2] == -80 && rightInsets[3] == 0);
}
