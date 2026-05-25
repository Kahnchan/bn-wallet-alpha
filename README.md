# Binance Wallet Alpha 空投日历

自动追踪 Binance Wallet Alpha 空投相关信号，并生成 Apple Calendar 可订阅的 `.ics` 日历。

云端订阅地址：

```text
https://kahnchan.github.io/bn-wallet-alpha/binance-alpha-airdrops.ics
```

项目页面：

```text
https://kahnchan.github.io/bn-wallet-alpha/
```

项目页面会直接展示一个月历视图，读取 `history.json` 中已经抓到的事件，并把 Alpha 空投挂到对应日期上；`.ics` 订阅地址仍然给 Apple Calendar 使用。

## 它做什么

- 每 30 分钟运行一次 GitHub Actions。
- 抓取 Binance Alpha 结构化币种接口，识别 `onlineAirdrop=true` 的项目。
- 扫描 Binance 官方公告/CMS，补充领取门槛、领取数量、开放时间等规则。
- 扫描官方 X 账号 `@binancezh` 和 `@BinanceWallet`，捕捉更早的 Alpha 空投预告；同时重扫历史官推的 thread，后续补充精确时间或规则时会回填旧事件。
- 生成 `public/binance-alpha-airdrops.ics`，由 GitHub Pages 托管给 Apple Calendar 订阅。
- 生成并发布 `public/history.json`，把已经发现的事件持续保留下来；后续扫描不到旧推文时也不会删除历史日历项。
- 页面端读取 `history.json` 渲染网页月历，方便不用打开 Calendar.app 也能查看。

## 日历规则

- 标题格式：`币种 - BN Alpha 空投/预告`，例如 `NEX - BN Alpha 预告`。
- 已确认具体时间的项目会生成定时事件。
- 只确认到日期的社媒预告会生成全天事件，避免误导成某个固定小时。
- 同一币种同一天如果先出现全天预告、后续官推补充了 `UTC` 时间或领取规则，脚本会把全天事件升级为定时事件，并把新规则放到简介前面。
- 默认不生成每天重复检查提醒。
- 没有明确规则的项目会在简介里提示去 `Binance Wallet > Alpha > Events` 核验。
- 已发现的事件会长期保留，不按 7 天或 30 天自动清理。

## Apple Calendar 订阅

1. 打开 Calendar.app。
2. 选择 `File > New Calendar Subscription...`。
3. 粘贴云端订阅地址：

```text
https://kahnchan.github.io/bn-wallet-alpha/binance-alpha-airdrops.ics
```

建议把自动刷新设置为每 30 分钟或每小时。

## 手动运行

```bash
/usr/bin/python3 scripts/update_binance_alpha_calendar.py
```

扩大回看窗口：

```bash
/usr/bin/python3 scripts/update_binance_alpha_calendar.py --lookback-days 7
```

关闭社媒扫描：

```bash
/usr/bin/python3 scripts/update_binance_alpha_calendar.py --no-social
```

增加官方 X 账号：

```bash
/usr/bin/python3 scripts/update_binance_alpha_calendar.py --social-accounts binancezh,BinanceWallet,BinanceChinese
```

调整历史 thread 回扫数量：

```bash
/usr/bin/python3 scripts/update_binance_alpha_calendar.py --social-threads 30
```

额外生成每天 20:30 的人工检查提醒：

```bash
/usr/bin/python3 scripts/update_binance_alpha_calendar.py --include-daily-check
```

## 本机模式

本机模式已经不是默认推荐方式。需要时可以重新启用：

```bash
bash scripts/install_launchd.sh
```

这会安装两个 macOS LaunchAgent：

- 每 30 分钟刷新一次 `.ics`
- 在本机 `http://127.0.0.1:8765/` 提供订阅地址

停止本机任务：

```bash
bash scripts/uninstall_launchd.sh
```

## 云端维护

查看最近运行：

```bash
gh run list --repo Kahnchan/bn-wallet-alpha --workflow update-calendar.yml
```

查看某次日志：

```bash
gh run view <run-id> --repo Kahnchan/bn-wallet-alpha --log
```

手动触发：

```bash
gh workflow run update-calendar.yml --repo Kahnchan/bn-wallet-alpha
```

## 注意

GitHub Actions 的定时任务可能延迟，不保证精确卡点执行。社媒预告只代表官方账号公开提到的日期或方向，最终领取时间、资格、Alpha Points 门槛和领取数量仍以 Binance Wallet App 内 Alpha 活动页为准。
