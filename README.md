# Binance Wallet Alpha 日历订阅

这个目录用于生成一个自动刷新的 Apple Calendar 订阅日历，提醒 Binance Wallet Alpha 空投领取事件。

## 工作方式

- `scripts/update_binance_alpha_calendar.py` 抓取官方 Binance Alpha 币种数据和近期官方公告候选。
- 默认还会通过公开镜像扫描官方 X 账号 `@binancezh` 和 `@BinanceWallet`，用来捕捉更早的 Alpha 空投预告。
- `public/binance-alpha-airdrops.ics` 是 Apple Calendar 订阅的日历文件。
- `data/alpha_airdrops.md` 和 `data/alpha_airdrops.json` 是生成后的快照。
- `scripts/install_launchd.sh` 会安装两个 macOS LaunchAgent：
  - 每 30 分钟刷新一次日历文件
  - 在本机 `http://127.0.0.1:8765/` 提供订阅地址
- LaunchAgent 会从 `~/Library/Application Support/BnWalletAlphaCalendar` 运行，避免 macOS 后台权限限制阻止访问 `Documents` 下的文件。

默认只生成具体识别到的币种空投事件，不生成每天重复的检查提醒。需要每日检查提醒时，可以手动给刷新脚本加 `--include-daily-check`。

## 安装

```bash
bash scripts/install_launchd.sh
```

然后打开 Calendar.app：

```text
File > New Calendar Subscription...
```

填入这个订阅地址：

```text
http://127.0.0.1:8765/binance-alpha-airdrops.ics
```

建议把 Apple Calendar 的自动刷新也设为每 30 分钟或每小时。

## 手动刷新

```bash
/usr/bin/python3 scripts/update_binance_alpha_calendar.py
```

默认窗口包含最近 3 天内官方字段 `onlineAirdrop=true` 的 Alpha 币种，以及接口中能看到的未来项目。想看更宽的窗口，可以这样跑：

```bash
/usr/bin/python3 scripts/update_binance_alpha_calendar.py --lookback-days 7
```

想临时关闭社媒扫描：

```bash
/usr/bin/python3 scripts/update_binance_alpha_calendar.py --no-social
```

想增加官方 X 账号：

```bash
/usr/bin/python3 scripts/update_binance_alpha_calendar.py --social-accounts binancezh,BinanceWallet,BinanceChinese
```

如果想额外生成每天 20:30 的人工检查提醒：

```bash
/usr/bin/python3 scripts/update_binance_alpha_calendar.py --include-daily-check
```

## 卸载

```bash
bash scripts/uninstall_launchd.sh
```

这会删除后台任务，但不会从 Apple Calendar 里移除你已经添加的订阅。

## 云端托管

推荐用 GitHub Pages + GitHub Actions：

1. 把这个目录推到一个 GitHub 仓库。
2. 在仓库设置里启用 Pages，Source 选择 `GitHub Actions`。
3. `.github/workflows/update-calendar.yml` 会每 30 分钟运行一次，生成并发布 `binance-alpha-airdrops.ics`。

发布后 Apple Calendar 订阅地址大概是：

```text
https://<你的 GitHub 用户名>.github.io/<仓库名>/binance-alpha-airdrops.ics
```

注意：GitHub Actions 的定时任务可能有延迟，不保证精确卡点执行。
