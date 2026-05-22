#!/usr/bin/env swift

import AppKit
import Foundation

final class CaptureDelegate: NSObject, NSApplicationDelegate {
    var window: NSPanel!
    let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        let size: CGFloat = 58
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

        let button = NSButton(frame: NSRect(x: 0, y: 0, width: size, height: size))
        button.title = "●"
        button.font = NSFont.systemFont(ofSize: 34, weight: .semibold)
        button.bezelStyle = .circular
        button.isBordered = true
        button.target = self
        button.action = #selector(capture)
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
