import AppKit
import Charts
import SwiftUI

struct Point: Decodable, Identifiable {
    let date: String
    let equity_wan: Double
    let drawdown_pct: Double
    var id: String { date }
    var day: Date { Self.parser.date(from: date)! }
    static let parser: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(secondsFromGMT: 0)
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}

struct Curve: Decodable { let points: [Point] }

struct EquityFigure: View {
    let points: [Point]
    let blue = Color(red: 0.13, green: 0.36, blue: 0.67)
    let red = Color(red: 0.77, green: 0.25, blue: 0.26)
    var ticks: [Date] {
        [points.first!.day] + (2016...2026).map { Point.parser.date(from: "\($0)-01-01")! }
    }

    func metric(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            Text(label).font(.system(size: 17)).foregroundStyle(.secondary)
            Text(value).font(.system(size: 31, weight: .semibold, design: .rounded))
        }.frame(maxWidth: .infinity, alignment: .leading)
            .padding(21).background(.white, in: RoundedRectangle(cornerRadius: 15))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            VStack(alignment: .leading, spacing: 10) {
                Text("21 品种 · 20 万元 · 回测资金曲线")
                    .font(.system(size: 38, weight: .bold))
                Text("2015-01-05 至 2026-11-04  ·  周 K 信号  ·  固定一手  ·  全品种触价止损")
                    .font(.system(size: 20)).foregroundStyle(.secondary)
            }
            HStack(spacing: 16) {
                metric("期末账户权益", "124.95 万元")
                metric("累计收益", "+524.77%")
                metric("最大回撤", "−39.73%")
                metric("Sharpe", "0.802")
            }
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    Text("账户权益（万元）").font(.system(size: 21, weight: .semibold))
                    Spacer()
                    Text("虚线为初始资金 20 万元").font(.system(size: 15)).foregroundStyle(.secondary)
                }
                Chart {
                    RuleMark(y: .value("初始资金", 20.0))
                        .foregroundStyle(Color.gray.opacity(0.65))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 4]))
                    ForEach(points) { p in
                        LineMark(x: .value("日期", p.day), y: .value("权益", p.equity_wan))
                            .foregroundStyle(blue)
                            .lineStyle(StrokeStyle(lineWidth: 2.2))
                    }
                }
                .chartXScale(domain: points.first!.day...points.last!.day)
                .chartYScale(domain: 0.0...140.0)
                .chartXAxis {
                    AxisMarks(values: ticks) { value in
                        AxisGridLine().foregroundStyle(Color.gray.opacity(0.14))
                        AxisValueLabel(format: .dateTime.year()).font(.system(size: 14))
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .leading, values: [0, 20, 40, 60, 80, 100, 120, 140]) { value in
                        AxisGridLine().foregroundStyle(Color.gray.opacity(0.17))
                        AxisValueLabel {
                            if let v = value.as(Int.self) {
                                Text("\(v)").font(.system(size: 14)).frame(width: 56, alignment: .trailing)
                            }
                        }
                    }
                }
                .frame(height: 405)
                .padding(.top, 4)
            }.padding(24).background(.white, in: RoundedRectangle(cornerRadius: 18))
            VStack(alignment: .leading, spacing: 13) {
                HStack {
                    Text("历史高点回撤").font(.system(size: 21, weight: .semibold))
                    Spacer()
                    Text("最大回撤发生于 2018-01-26").font(.system(size: 15)).foregroundStyle(.secondary)
                }
                Chart {
                    ForEach(points) { p in
                        AreaMark(x: .value("日期", p.day), yStart: .value("基准", 0.0),
                                 yEnd: .value("回撤", p.drawdown_pct))
                            .foregroundStyle(red.opacity(0.14))
                        LineMark(x: .value("日期", p.day), y: .value("回撤", p.drawdown_pct))
                            .foregroundStyle(red)
                            .lineStyle(StrokeStyle(lineWidth: 1.6))
                    }
                }
                .chartXScale(domain: points.first!.day...points.last!.day)
                .chartYScale(domain: -45.0...0.0)
                .chartXAxis {
                    AxisMarks(values: ticks) { value in
                        AxisGridLine().foregroundStyle(Color.gray.opacity(0.14))
                        AxisValueLabel(format: .dateTime.year()).font(.system(size: 14))
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .leading, values: [-40, -30, -20, -10, 0]) { value in
                        AxisGridLine().foregroundStyle(Color.gray.opacity(0.17))
                        AxisValueLabel {
                            if let v = value.as(Int.self) {
                                Text("\(v)%").font(.system(size: 14)).frame(width: 56, alignment: .trailing)
                            }
                        }
                    }
                }.frame(height: 155)
            }.padding(24).background(.white, in: RoundedRectangle(cornerRadius: 18))
            VStack(alignment: .leading, spacing: 5) {
                Text("净利润 104.95 万元  ·  1,999 笔完整交易  ·  已计滑点 11.12 万元，手续费为零")
                Text("使用全部 2,875 个交易日数据；日线 OHLC 模拟触价止损，期末持仓按市价估值。来源：Stage060 冻结账本。")
            }.font(.system(size: 15)).foregroundStyle(.secondary)
        }.padding(34).frame(width: 1500, alignment: .leading)
            .background(Color(red: 0.953, green: 0.965, blue: 0.982))
            .environment(\.colorScheme, .light)
            .environment(\.timeZone, TimeZone(secondsFromGMT: 0)!)
    }
}

@main struct Render {
    @MainActor static func main() throws {
        let data = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
        let curve = try JSONDecoder().decode(Curve.self, from: data)
        guard curve.points.count == 2875, curve.points.first!.equity_wan == 20,
              curve.points.last!.equity_wan == 124.9535 else {
            throw CocoaError(.fileReadCorruptFile)
        }
        let renderer = ImageRenderer(content: EquityFigure(points: curve.points))
        renderer.scale = 1.5
        guard let image = renderer.cgImage,
              let png = NSBitmapImageRep(cgImage: image).representation(using: .png, properties: [:])
        else { throw CocoaError(.fileWriteUnknown) }
        try png.write(to: URL(fileURLWithPath: CommandLine.arguments[2]))
        print("Rendered \(curve.points.count) daily points, \(image.width)×\(image.height)")
    }
}
