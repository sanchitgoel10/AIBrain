#!/usr/bin/env swift

import AppKit
import Foundation
import Vision

func cgImage(from path: String) -> CGImage? {
    guard let image = NSImage(contentsOfFile: path) else {
        return nil
    }
    var rect = NSRect(origin: .zero, size: image.size)
    return image.cgImage(forProposedRect: &rect, context: nil, hints: nil)
}

func recognize(path: String) throws -> [String] {
    guard let image = cgImage(from: path) else {
        throw NSError(domain: "AIBrainOCR", code: 1, userInfo: [NSLocalizedDescriptionKey: "Could not load image: \(path)"])
    }

    var output: [String] = []
    let request = VNRecognizeTextRequest { request, error in
        if let error = error {
            output.append("OCR error: \(error.localizedDescription)")
            return
        }
        let observations = request.results as? [VNRecognizedTextObservation] ?? []
        output.append(contentsOf: observations.compactMap { observation in
            observation.topCandidates(1).first?.string
        })
    }
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true

    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])
    return output
}

let paths = Array(CommandLine.arguments.dropFirst())
if paths.isEmpty {
    fputs("usage: ocr_images.swift image.png [image2.png ...]\n", stderr)
    exit(2)
}

var allLines: [String] = []
for path in paths {
    do {
        let lines = try recognize(path: path)
        allLines.append(contentsOf: lines)
        allLines.append("")
    } catch {
        fputs("ERROR: \(error.localizedDescription)\n", stderr)
        exit(1)
    }
}

print(allLines.joined(separator: "\n"))
