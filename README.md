# har-entry-budget

[![tests](https://github.com/maomao-1937/har-entry-budget/actions/workflows/tests.yml/badge.svg)](https://github.com/maomao-1937/har-entry-budget/actions/workflows/tests.yml)

Check each recorded request in a local HAR 1.2 numeric subset against two explicit budgets. Get stable JSON with entry numbers and measurements, without copying URLs, headers, cookies, content text, filenames, or metadata into the report.

## Run from source

Requires Python **3.11+**, standard library only. Download the source files or clone this repository, open its root directory, and run:

```console
python har_entry_budget.py examples/clean.har --max-time-ms 100 --max-body-bytes 200
python har_entry_budget.py examples/findings.har --max-time-ms 100 --max-body-bytes 200
python har_entry_budget.py --help
```

No package installation, dependency download, credentials, configuration file, environment variables, or API setup is needed. Both budget flags are required; there are no hidden defaults. `--max-time-ms` accepts a nonnegative JSON number, including fractional milliseconds and exponent notation. `--max-body-bytes` accepts a nonnegative decimal integer. Budget tokens are limited to 128 characters.

The first command exits 0 and prints:

```json
{"code":"CLEAN","entries":1,"budgets":{"max_time_ms":100,"max_body_bytes":200},"counts":{"time_over":0,"body_over":0,"time_unknown":0,"body_unknown":0},"findings":[]}
```

The second exits 1. Its findings are:

```json
[{"entry":1,"code":"TIME_OVER","measurement":100.25,"budget":100},{"entry":1,"code":"BODY_OVER","measurement":201,"budget":200},{"entry":2,"code":"TIME_UNKNOWN"},{"entry":2,"code":"BODY_UNKNOWN"}]
```

## Policy and exits

| Exit | Meaning |
| --- | --- |
| 0 | Every present entry has both measurements known and at or below its budgets; an empty entries array also passes. `--help` emits JSON and exits 0. |
| 1 | At least one measurement exceeds its budget or is unknown. |
| 2 | Invalid/unsupported input, arguments, file access, or output failure. |

`time` is an entry's elapsed milliseconds. This profile accepts a number >= 0; booleans and negative values, including -1, are invalid. Missing `time` produces `TIME_UNKNOWN`. `response.bodySize` represents the recorded received body bytes, excluding response headers. This profile requires an integer >= -1; -1 or a missing value produces `BODY_UNKNOWN`. A missing response object also means unknown body size. A present nonobject response or invalid measurement makes the entire input invalid, even if earlier entries had findings.

Equality passes. Numeric comparison and numeric JSON emission use exact decimal values, so converting to binary floats cannot hide a small violation. `content.size` describes a different size under compression; it is ignored, never used as a replacement. Other metadata is ignored semantically but still subject to strict JSON and resource checks.

Entry indices start at 1. Findings are ordered by entry, then time before body. Counts count measurements, not distinct entries. Reports contain fixed codes, counts, indices, budgets and violating numeric measurements only. Errors are neutral JSON, never the parser's message or input path; stderr is empty. A closed stdout exits 2 without a traceback or Python shutdown exit 120. `--help` uses the same output behavior.

## Supported subset and limits

One explicitly named regular file, strict UTF-8 with an optional initial BOM; JSON root object with a `log` object, `log.version` exactly the string `"1.2"`, and `log.entries` an array of objects. Creator, request, timings, and other full HAR fields are not required or validated. This is **not a full HAR schema validator**.

| Resource | Limit |
| --- | --- |
| Input bytes (including BOM) | 2,097,152 |
| Entries | 10,000 |
| JSON nesting | 64 simultaneous objects/arrays, root counts as 1 |
| Parsed nodes | 100,000; every value and every object key counts once |
| Each numeric token | 128 characters, including sign/exponent |
| Decimal magnitude | <= 1.7976931348623157e308; very small finite values retain their decimal exponent |
| Findings | At most 20,000, two per entry |

Duplicate keys, NaN/Infinity, overflow beyond the magnitude limit, unpaired Unicode surrogates, malformed JSON/UTF-8, and cap violations are rejected anywhere, including ignored metadata. JSON integer syntax is required for bodySize: `1.0` and `1e0` are rejected. No gzip/zip input or stdin. Extremely large exponents outside Python Decimal's representable exponent range are also rejected.

URI-like names, UNC names (including mixed slash spellings), device names and Windows drive-relative names are refused lexically before stat/open. Ordinary relative names, POSIX absolute paths, and Windows absolute drive paths are allowed. On all platforms, colons are reserved for an absolute Windows drive prefix. A symlink to a regular file can be accepted. Lexical checks **cannot certify local backing** of symlinks, mounts or mapped drives; concurrent filesystem replacement is outside the guarantee.

The product only reads its named input and writes its JSON result to stdout. It makes no network requests, launches no subprocesses, and writes no files. It does not measure a browser, infer page-load totals by summing concurrent entries, verify export accuracy, sanitize the original HAR, or promise that the original HAR is safe to share. Use browser tools for inspection and fresh measurements; see [RESEARCH.md](RESEARCH.md).

## Test

```console
python -m unittest discover -s tests -v
```

All fixtures are synthetic. See [TESTING.md](TESTING.md) for actual local results. MIT license, copyright 2026 maomao-1937.

## 中文说明

这个工具读取一个本地 HAR 1.2 数值子集文件，逐条检查耗时和响应体字节预算。需要 Python 3.11 或更高版本，仅使用标准库，无需安装依赖、配置文件、环境变量或密钥。请在源码根目录运行上面的命令；两个预算参数均必填。

`time` 使用毫秒，支持小数，必须 >= 0；缺失记为未知，-1 也属于无效值。`response.bodySize` 必须为整数且 >= -1；-1、字段缺失或 response 缺失均记为未知。response 存在但不是对象时无效。相等通过，超出或未知退出 1，无效输入或操作失败退出 2，通过退出 0。缺失数据不能形成“全部通过”。空 entries 数组通过。

只比较 `response.bodySize`，不会把 `content.size` 替代为传输响应体大小，也不推算整页加载时长。JSON 报告只包含固定代码、从 1 开始的条目序号、计数、预算与超标数值，不回显 URL、请求头、Cookie、正文、元数据或路径。原 HAR 不会被修改或脱敏，请自行保管。

限制为 2 MiB、10,000 条记录、64 层 JSON、100,000 个节点和每个数字 128 字符。重复键、非有限数、数值溢出、未配对代理字符和错误编码均拒绝。仅接受明确指定的普通文件；路径字符串检查不能保证符号链接、挂载或映射盘的底层位置。它不进行网络请求、不执行子进程、不写文件，也不验证完整 HAR 模式。详细规则及边界以本页英文表格和测试为准。
