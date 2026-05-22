#!/usr/bin/env swift

import AppKit
import Foundation

final class CaptureButtonView: NSView {
    var onCapture: (() -> Void)?
    private var isHovering = false
    private var isPressed = false

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        addTrackingArea(NSTrackingArea(
            rect: bounds,
            options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect],
            owner: self
        ))
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override var acceptsFirstResponder: Bool { true }

    override func mouseEntered(with event: NSEvent) {
        isHovering = true
        needsDisplay = true
    }

    override func mouseExited(with event: NSEvent) {
        isHovering = false
        isPressed = false
        needsDisplay = true
    }

    override func mouseDown(with event: NSEvent) {
        isPressed = true
        needsDisplay = true
    }

    override func mouseUp(with event: NSEvent) {
        let point = convert(event.locationInWindow, from: nil)
        let shouldCapture = bounds.contains(point)
        isPressed = false
        needsDisplay = true
        if shouldCapture {
            onCapture?()
        }
    }

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)

        let rect = bounds.insetBy(dx: 3, dy: 3)
        let radius = rect.width / 2
        let path = NSBezierPath(roundedRect: rect, xRadius: radius, yRadius: radius)

        NSGraphicsContext.saveGraphicsState()
        let shadow = NSShadow()
        shadow.shadowColor = NSColor.black.withAlphaComponent(0.28)
        shadow.shadowBlurRadius = isHovering ? 14 : 10
        shadow.shadowOffset = NSSize(width: 0, height: -4)
        shadow.set()

        let top = isPressed
            ? NSColor(calibratedRed: 0.12, green: 0.39, blue: 0.95, alpha: 0.98)
            : NSColor(calibratedRed: 0.18, green: 0.56, blue: 1.00, alpha: 0.98)
        let bottom = isPressed
            ? NSColor(calibratedRed: 0.04, green: 0.18, blue: 0.54, alpha: 0.98)
            : NSColor(calibratedRed: 0.05, green: 0.24, blue: 0.78, alpha: 0.98)
        NSGradient(starting: top, ending: bottom)?.draw(in: path, angle: 90)
        NSGraphicsContext.restoreGraphicsState()

        NSColor.white.withAlphaComponent(isHovering ? 0.50 : 0.34).setStroke()
        path.lineWidth = 1.4
        path.stroke()

        drawGlyph(in: rect)
    }

    private func drawGlyph(in rect: NSRect) {
        let center = NSPoint(x: rect.midX, y: rect.midY)

        let lensRect = NSRect(x: center.x - 12, y: center.y - 8, width: 19, height: 19)
        let lens = NSBezierPath(ovalIn: lensRect)
        NSColor.white.setStroke()
        lens.lineWidth = 3.2
        lens.stroke()

        let handle = NSBezierPath()
        handle.move(to: NSPoint(x: center.x + 4, y: center.y - 5))
        handle.line(to: NSPoint(x: center.x + 14, y: center.y - 15))
        handle.lineWidth = 3.4
        handle.lineCapStyle = .round
        NSColor.white.setStroke()
        handle.stroke()

        let sparkle = NSBezierPath()
        sparkle.move(to: NSPoint(x: center.x - 13, y: center.y + 12))
        sparkle.line(to: NSPoint(x: center.x - 13, y: center.y + 4))
        sparkle.move(to: NSPoint(x: center.x - 17, y: center.y + 8))
        sparkle.line(to: NSPoint(x: center.x - 9, y: center.y + 8))
        sparkle.lineWidth = 1.8
        sparkle.lineCapStyle = .round
        NSColor.white.withAlphaComponent(0.9).setStroke()
        sparkle.stroke()
    }
}

final class CaptureDelegate: NSObject, NSApplicationDelegate {
    var window: NSPanel!
    let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        let size: CGFloat = 62
        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1200, height: 800)
        let frame = NSRect(x: screen.maxX - size - 28, y: screen.midY - size / 2, width: size, height: size)

        window = NSPanel(
            contentRect: frame,
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        window.isFloatingPanel = true
        window.level = .floating
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        window.backgroundColor = .clear
        window.isOpaque = false
        window.hasShadow = true

        let button = CaptureButtonView(frame: NSRect(x: 0, y: 0, width: size, height: size))
        button.onCapture = { [weak self] in self?.capture() }
        window.contentView = button
        window.orderFrontRegardless()
    }

    @objc func capture() {
        let task = Process()
        task.currentDirectoryURL = root
        task.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        task.arguments = ["scripts/capture_current_page.py"]

        let output = Pipe()
        let error = Pipe()
        task.standardOutput = output
        task.standardError = error

        do {
            try task.run()
            task.waitUntilExit()
        } catch {
            show("Capture failed", error.localizedDescription)
            return
        }

        let outText = String(data: output.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        let errText = String(data: error.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""

        if task.terminationStatus == 0 {
            show("Captured", outText.trimmingCharacters(in: .whitespacesAndNewlines))
        } else {
            show("Capture error", errText.trimmingCharacters(in: .whitespacesAndNewlines))
        }
    }

    func show(_ title: String, _ message: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message.isEmpty ? "No details." : message
        alert.alertStyle = title.contains("error") || title.contains("failed") ? .warning : .informational
        alert.runModal()
    }
}

let app = NSApplication.shared
let delegate = CaptureDelegate()
app.delegate = delegate
app.run()
