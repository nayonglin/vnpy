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
        DispatchQueue.main.asyncAfter(deadline: .now() + 32) { self.fail("WebKit verification timed out") }
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
        let script = """
        const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
        const check=(cond,msg)=>{if(!cond)throw Error(msg)};
        const el=id=>document.getElementById(id);
        const pick=async(id,value)=>{const node=el(id);node.value=value;node.dispatchEvent(new Event('change'));await pause(300)};
        for(let i=0;i<60&&!el('chart')._fullLayout;i++)await pause(100);
        check(el('trade').options.length===167,'completed trade count');
        check([...document.querySelectorAll('[data-period]:checked')].map(x=>x.dataset.period).join(',')==='day30,daily','default periods');
        check(el('rejected-ledger').querySelectorAll('tbody tr').length===0,'annual rejected table');
        check(el('residual-ledger').querySelectorAll('tbody tr').length===0,'annual residual table');
        const chart=el('chart');
        check(chart._fullLayout.xaxis2.matches==='x','linked x axes');
        const old=chart._fullLayout.xaxis.range;
        await Plotly.relayout(chart,{'xaxis.range':[old[0]+2,old[1]-2]});
        check(chart._fullLayout.xaxis2.range.every((v,i)=>v===chart._fullLayout.xaxis.range[i]),'zoom synchronization');
        el('next').click(); await pause(300); check(el('trade').value==='1','next');
        el('prev').click(); await pause(300); check(el('trade').value==='0','previous');
        await pick('result','profit'); check(el('trade').options.length===52,'profit filter');
        await pick('result','loss'); check(el('trade').options.length===115,'loss filter');
        await pick('result','all');
        await pick('product','cu.SHFE'); check(el('trade').options.length>0,'copper filter');
        check(el('episodeNote').textContent.includes('2022年贡献'),'per-trade annual PnL');
        check(!el('episodeNote').textContent.includes('黄金止损线'),'no gold marker for copper');
        await pick('product',[...el('product').options].find(x=>x.textContent.includes('全部品种')).value); check(el('product').selectedIndex>=0,'all-products selection');
        const cross=[...el('trade').options].find(x=>x.textContent.includes('2023-02-06'));
        check(cross,'cross-year cotton option'); await pick('trade',cross.value);
        check(el('episodeNote').textContent.includes('2022 年末仍持仓'),'cross-year status');
        check(el('episodeNote').textContent.includes('2022年贡献'),'cross-year annual contribution');
        const weekly=document.querySelector('[data-period=weekly]');
        weekly.click(); await pause(300); check(chart._fullLayout.xaxis3.matches==='x','weekly third panel');
        weekly.click(); await pause(300); await pick('trade','0');
        check(window.recapErrors.length===0,window.recapErrors.join(','));
        return 'WebKit PASS: 167 records, 52 profit/115 loss, filters, navigation, cross-year evidence, linked zoom and default periods';
        """
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
