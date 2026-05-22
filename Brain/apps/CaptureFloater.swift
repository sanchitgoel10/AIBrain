#!/usr/bin/env swift

import AppKit
import Foundation

struct CaptureCandidate: Decodable {
    let url: String
    let title: String
    let browser: String
    let source: String

    static let empty = CaptureCandidate(url: "", title: "", browser: "", source: "")
}

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
    var dialogCandidates: [CaptureCandidate] = []
    weak var dialogTitleLabel: NSTextField?
    weak var dialogSourceLabel: NSTextField?
    weak var dialogURLInput: NSTextField?

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
        guard let url = askForURL(candidates: candidatePages()) else {
            return
        }

        let task = Process()
        task.currentDirectoryURL = root
        task.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        task.arguments = ["scripts/capture_current_page.py", "--url", url]

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

    func candidatePages() -> [CaptureCandidate] {
        let task = Process()
        task.currentDirectoryURL = root
        task.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        task.arguments = ["scripts/capture_current_page.py", "--candidate-list-json"]

        let output = Pipe()
        task.standardOutput = output
        task.standardError = Pipe()

        do {
            try task.run()
            task.waitUntilExit()
        } catch {
            return []
        }

        let data = output.fileHandleForReading.readDataToEndOfFile()
        guard let candidates = try? JSONDecoder().decode([CaptureCandidate].self, from: data) else {
            return []
        }
        return candidates.filter { isCaptureURL($0.url) }
    }

    func askForURL(candidates: [CaptureCandidate]) -> String? {
        NSApp.activate(ignoringOtherApps: true)

        dialogCandidates = candidates.isEmpty ? [.empty] : candidates
        let initial = dialogCandidates[0]

        let stack = NSStackView(frame: NSRect(x: 0, y: 0, width: 560, height: 154))
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 8

        let popup = NSPopUpButton(frame: NSRect(x: 0, y: 0, width: 560, height: 28), pullsDown: false)
        for (index, candidate) in dialogCandidates.enumerated() {
            popup.addItem(withTitle: menuTitle(for: candidate, index: index))
            popup.item(at: index)?.tag = index
        }
        popup.target = self
        popup.action = #selector(candidateSelectionChanged(_:))

        let titleLabel = wrappingLabel(
            initial.title.isEmpty ? "Title: unknown" : "Title: \(initial.title)",
            width: 560,
            bold: true
        )
        let sourceText = sourceLabelText(for: initial)
        let sourceLabel = wrappingLabel(sourceText, width: 560, bold: false)

        let input = NSTextField(frame: NSRect(x: 0, y: 0, width: 560, height: 28))
        input.stringValue = initial.url
        input.placeholderString = "https://www.youtube.com/watch?v=... or https://example.com/article"
        input.lineBreakMode = .byTruncatingMiddle

        dialogTitleLabel = titleLabel
        dialogSourceLabel = sourceLabel
        dialogURLInput = input

        stack.addArrangedSubview(popup)
        stack.addArrangedSubview(titleLabel)
        stack.addArrangedSubview(sourceLabel)
        stack.addArrangedSubview(input)

        let alert = NSAlert()
        alert.messageText = "Capture this page?"
        alert.informativeText = "Confirm both the title and exact URL before saving."
        alert.accessoryView = stack
        alert.addButton(withTitle: "Capture")
        alert.addButton(withTitle: "Cancel")
        alert.window.initialFirstResponder = input

        let response = alert.runModal()
        guard response == .alertFirstButtonReturn else {
            return nil
        }

        let url = input.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        if isCaptureURL(url) {
            return url
        }

        show("Capture error", "Paste a valid http or https URL.")
        return nil
    }

    @objc func candidateSelectionChanged(_ sender: NSPopUpButton) {
        let index = sender.selectedTag()
        guard dialogCandidates.indices.contains(index) else {
            return
        }
        let candidate = dialogCandidates[index]
        dialogTitleLabel?.stringValue = candidate.title.isEmpty ? "Title: unknown" : "Title: \(candidate.title)"
        dialogSourceLabel?.stringValue = sourceLabelText(for: candidate)
        dialogURLInput?.stringValue = candidate.url
    }

    func menuTitle(for candidate: CaptureCandidate, index: Int) -> String {
        let title = candidate.title.isEmpty ? candidate.url : candidate.title
        let source = candidate.source.isEmpty ? "manual" : candidate.source
        return "\(index + 1). \(title) [\(source)]"
    }

    func sourceLabelText(for candidate: CaptureCandidate) -> String {
        if candidate.source == "session" && !candidate.browser.isEmpty {
            return "Source: \(candidate.browser) open session"
        }
        if candidate.source == "history" && !candidate.browser.isEmpty {
            return "Source: \(candidate.browser) recent history"
        }
        if candidate.source.isEmpty {
            return "Source: pasted or typed URL"
        }
        return "Source: \(candidate.source)"
    }

    func wrappingLabel(_ text: String, width: CGFloat, bold: Bool) -> NSTextField {
        let label = NSTextField(labelWithString: text)
        label.frame = NSRect(x: 0, y: 0, width: width, height: 20)
        label.maximumNumberOfLines = 2
        label.lineBreakMode = .byTruncatingTail
        label.font = bold ? NSFont.boldSystemFont(ofSize: 13) : NSFont.systemFont(ofSize: 12)
        label.textColor = bold ? .labelColor : .secondaryLabelColor
        return label
    }

    func isCaptureURL(_ value: String) -> Bool {
        guard let url = URL(string: value),
              let scheme = url.scheme?.lowercased(),
              scheme == "http" || scheme == "https",
              let host = url.host?.lowercased() else {
            return false
        }
        if host.hasPrefix("chrome.") || host.hasPrefix("newtab.") || host.hasPrefix("dia.") {
            return false
        }
        return host != "netflix.com" && !host.hasSuffix(".netflix.com")
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
