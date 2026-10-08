# 日志分析任务

你需要编写一个 shell 脚本来分析 Web 服务器的访问日志。

## 输入

日志文件位于 `/data/access.log`，每行格式如下：

```
192.168.1.100 - - [01/Jan/2024:10:00:00 +0000] "GET /api/users HTTP/1.1" 200 1234
192.168.1.101 - - [01/Jan/2024:10:00:01 +0000] "POST /api/login HTTP/1.1" 401 56
192.168.1.100 - - [01/Jan/2024:10:00:02 +0000] "GET /api/products HTTP/1.1" 200 5678
```

- 第 1 个字段是客户端 IP 地址。
- 双引号内的请求行格式为 `METHOD PATH HTTP/1.1`。
- 请求行之后依次是 HTTP 状态码和响应字节数。

## 要求

编写脚本完成以下任务：

1. 统计每个 IP 地址的请求次数。
2. 找出请求次数最多的 IP 地址。
3. 统计 HTTP 状态码分布（200、401、404、500 等）。
4. 将结果输出到 `/output/report.txt`。

## 输出格式

`/output/report.txt` 应该包含以下三个区块，区块标题必须原样保留，区块之间用一个空行分隔：

```
=== Top IP ===
192.168.1.100: 15 requests

=== Status Code Distribution ===
200: 120
401: 5
404: 10
500: 2

=== Requests per IP ===
192.168.1.100: 15
192.168.1.101: 7
```

说明：

- `Top IP` 区块：请求次数最多的 IP，格式为 `<ip>: <count> requests`。
- `Status Code Distribution` 区块：每行一个状态码，格式为 `<code>: <count>`。
- `Requests per IP` 区块：每行一个 IP，格式为 `<ip>: <count>`。
- 计数必须与 `/data/access.log` 的实际内容一致。

## 提交

将你的解决方案写入 `solution/solve.sh`。脚本会在容器内以 `bash` 执行，并且必须自行创建 `/output` 目录（如果不存在）。
