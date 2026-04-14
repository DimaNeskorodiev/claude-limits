#!/usr/bin/env python3
"""
Generate Claude Limits .icns icon for the macOS .app bundle.

Draws a ring-style icon matching the menu-bar widget aesthetic,
then uses iconutil to produce a proper multi-resolution .icns file.

Usage:
    python3 generate_icon.py <output.icns>
"""
import sys
import os
import shutil
import tempfile
import subprocess
from pathlib import Path

from AppKit import (
    NSImage, NSBitmapImageRep, NSGraphicsContext,
    NSBezierPath, NSColor, NSFont,
    NSFontAttributeName, NSForegroundColorAttributeName,
    NSAttributedString,
)
from Foundation import NSMakeRect, NSMakePoint, NSMakeSize


def _draw_icon(size: float) -> NSImage:
    """
    Draw the Claude Limits app icon at the given pixel size.

    Design:
      • Dark charcoal rounded-rect background
      • Subtle grey ring track (full circle)
      • Claude orange arc at ~72% fill
      • Bold white "CL" label centred inside
    """
    img = NSImage.alloc().initWithSize_(NSMakeSize(size, size))
    img.lockFocus()

    # ── Background: dark rounded rectangle ────────────────────────────────────
    BG_COLOR     = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.11, 0.11, 0.13, 1.0)
    TRACK_COLOR  = NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 1.0, 1.0, 0.15)
    ARC_COLOR    = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.91, 0.49, 0.17, 1.0)
    TEXT_COLOR   = NSColor.whiteColor()

    corner = size * 0.22
    bg = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(0, 0, size, size), corner, corner
    )
    BG_COLOR.setFill()
    bg.fill()

    # ── Ring ──────────────────────────────────────────────────────────────────
    cx = cy  = size / 2.0
    padding   = size * 0.13
    ring_r    = (size / 2.0) - padding
    lw_track  = size * 0.055
    lw_arc    = size * 0.075
    fill_pct  = 0.72               # static 72 % — looks intentional, not loading

    # Track (full circle)
    TRACK_COLOR.setStroke()
    track = NSBezierPath.bezierPathWithOvalInRect_(
        NSMakeRect(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
    )
    track.setLineWidth_(lw_track)
    track.stroke()

    # Arc (clockwise from 12-o'clock)
    end_deg = 90.0 - fill_pct * 360.0
    arc = NSBezierPath.bezierPath()
    arc.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(
        NSMakePoint(cx, cy), ring_r, 90.0, end_deg, True
    )
    arc.setLineWidth_(lw_arc)
    try:
        arc.setLineCapStyle_(1)    # NSLineCapStyleRound
    except Exception:
        pass
    ARC_COLOR.setStroke()
    arc.stroke()

    # ── "CL" label ────────────────────────────────────────────────────────────
    font_size = size * 0.21
    font = NSFont.boldSystemFontOfSize_(font_size)
    attrs = {
        NSFontAttributeName:            font,
        NSForegroundColorAttributeName: TEXT_COLOR,
    }
    label = NSAttributedString.alloc().initWithString_attributes_("CL", attrs)
    lsz = label.size()
    label.drawAtPoint_(NSMakePoint(
        (size - lsz.width)  / 2.0,
        (size - lsz.height) / 2.0,
    ))

    img.unlockFocus()
    return img


def _save_png(img: NSImage, path: Path):
    tiff = img.TIFFRepresentation()
    rep  = NSBitmapImageRep.imageRepWithData_(tiff)
    # NSPNGFileType = 4
    png  = rep.representationUsingType_properties_(4, {})
    png.writeToFile_atomically_(str(path), True)


def generate_icns(output_path: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        iconset = Path(tmpdir) / "AppIcon.iconset"
        iconset.mkdir()

        # Sizes required by Apple for a full-resolution .icns
        # Each logical size has a 1x and 2x (@2x) variant.
        logical_sizes = [16, 32, 128, 256, 512]

        rendered: dict[int, NSImage] = {}
        for sz in logical_sizes:
            rendered[sz]    = _draw_icon(float(sz))
            rendered[sz * 2] = _draw_icon(float(sz * 2))

        for sz in logical_sizes:
            _save_png(rendered[sz],      iconset / f"icon_{sz}x{sz}.png")
            _save_png(rendered[sz * 2],  iconset / f"icon_{sz}x{sz}@2x.png")

        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", output_path],
            check=True,
        )


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "AppIcon.icns"
    generate_icns(out)
    print(f"Icon written to {out}")
