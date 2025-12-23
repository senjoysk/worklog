#!/usr/bin/env swift

import Foundation
import Vision
import AppKit

/// 画像ファイルからOCRでテキストを抽出するCLIツール
/// 使用法: ocr_tool <image_path>

func performOCR(imagePath: String) -> String? {
    guard let image = NSImage(contentsOfFile: imagePath) else {
        fputs("Error: Cannot load image: \(imagePath)\n", stderr)
        return nil
    }

    guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        fputs("Error: Cannot convert to CGImage\n", stderr)
        return nil
    }

    var recognizedText = ""
    let semaphore = DispatchSemaphore(value: 0)

    let request = VNRecognizeTextRequest { request, error in
        defer { semaphore.signal() }

        if let error = error {
            fputs("Error: OCR failed: \(error.localizedDescription)\n", stderr)
            return
        }

        guard let observations = request.results as? [VNRecognizedTextObservation] else {
            return
        }

        let texts = observations.compactMap { observation -> String? in
            observation.topCandidates(1).first?.string
        }

        recognizedText = texts.joined(separator: "\n")
    }

    // 日本語と英語の両方を認識
    request.recognitionLanguages = ["ja-JP", "en-US"]
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])

    do {
        try handler.perform([request])
        semaphore.wait()
    } catch {
        fputs("Error: Failed to perform OCR: \(error.localizedDescription)\n", stderr)
        return nil
    }

    return recognizedText
}

// メイン処理
func main() {
    let arguments = CommandLine.arguments

    guard arguments.count >= 2 else {
        fputs("Usage: ocr_tool <image_path>\n", stderr)
        exit(1)
    }

    let imagePath = arguments[1]

    guard FileManager.default.fileExists(atPath: imagePath) else {
        fputs("Error: File not found: \(imagePath)\n", stderr)
        exit(1)
    }

    if let text = performOCR(imagePath: imagePath) {
        print(text)
    } else {
        exit(1)
    }
}

main()
