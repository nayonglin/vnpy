import AppKit
import WebKit

final class Check: NSObject, WKNavigationDelegate {
    let view: WKWebView
    let url: URL

    init(_ url: URL) {
        self.url = url
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()

        config.userContentController.addUserScript(WKUserScript(
            source: "window.recapErrors=[];window.addEventListener('error',e=>window.recapErrors.push(String(e.message)));",
            injectionTime: .atDocumentStart, forMainFrameOnly: true
        ))
        view = WKWebView(frame: NSRect(x: 0, y: 0, width: 1500, height: 1000), configuration: config)
        super.init()
        view.navigationDelegate = self
    }

    func start() {
        view.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
        DispatchQueue.main.asyncAfter(deadline: .now() + 55) { self.fail("WebKit verification timed out") }
    }

    func fail(_ message: String) {
        FileHandle.standardError.write(Data((message + "\n").utf8))
        exit(1)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        fail(String(describing: error))
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        fail(String(describing: error))
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        let script = try! String(contentsOfFile: CommandLine.arguments[3], encoding: .utf8)
        webView.callAsyncJavaScript(script, arguments: [:], in: nil, in: .page) { result in
            switch result {
            case .success(let value):
                print(value ?? "OK")
                let snapshot = WKSnapshotConfiguration()
                snapshot.rect = self.view.bounds
                snapshot.afterScreenUpdates = true
                self.view.takeSnapshot(with: snapshot) { image, error in
                    if let error = error { self.fail(String(describing: error)) }
                    guard let image = image, let tiff = image.tiffRepresentation,
                          let bitmap = NSBitmapImageRep(data: tiff), let png = bitmap.representation(using: .png, properties: [:]) else {
                        self.fail("snapshot data unavailable"); return
                    }
                    do { try png.write(to: URL(fileURLWithPath: CommandLine.arguments[2])); print("Snapshot saved"); exit(0) }
                    catch { self.fail(String(describing: error)) }
                }
            case .failure(let error): self.fail(String(describing: error))
            }
        }
    }
}

_ = NSApplication.shared
let check = Check(URL(fileURLWithPath: CommandLine.arguments[1]))
let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1500, height: 1000), styleMask: [.titled, .closable, .resizable], backing: .buffered, defer: false)
window.contentView = check.view
window.makeKeyAndOrderFront(nil)
NSApplication.shared.activate(ignoringOtherApps: true)
check.start()
RunLoop.main.run()
