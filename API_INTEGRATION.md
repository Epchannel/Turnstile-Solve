# Tài liệu tích hợp API self-host cho agent

Tài liệu đối chiếu với `api.py`, `core/browser.py`, `core/templates.py`, `core/stealth.py`, `turnstile/solve.py` và `cf_clearance/solve.py` trong repository hiện tại. API dùng HTTP GET và mô hình tạo task → polling → nhận kết quả.

> Áp dụng cho phiên bản **2.1.0**: server mặc định chạy **headed**, `/turnstile` hỗ trợ `proxy` và `timeout` theo từng request, và không dùng inject fingerprint/UA/locale.

## 1. Cấu hình kết nối

| Cấu hình của project tích hợp | Giá trị đề xuất |
|---|---|
| `SOLVER_BASE_URL` | `http://127.0.0.1:5072` |
| HTTP timeout mỗi request | 15 giây |
| Khoảng polling | 2 giây |
| Deadline tổng mỗi task phía client | 180 giây, cho phép cấu hình |

`127.0.0.1` chỉ dùng khi client và server cùng máy/network namespace. Nếu client chạy trong container hoặc máy khác, cấu hình địa chỉ server có thể truy cập từ client. `0.0.0.0` là địa chỉ bind, không phải base URL cho client.

Server hiện không có API key, endpoint POST, Swagger, webhook hoặc endpoint hủy task. `GET /` trả HTML hướng dẫn, không phải JSON health check. Không cần gửi JSON body cho các endpoint bên dưới. Dùng query encoder của HTTP client để truyền URL, sitekey và proxy.

## 2. Tạo task Turnstile

```http
GET /turnstile?url=<encoded-page-url>&sitekey=<site-key>
```

Ví dụ đầy đủ cho iHerb:

```http
GET /turnstile?url=https%3A%2F%2Fcheckout9.iherb.com%2Fauth%2Fui%2Faccount%2Flogin&sitekey=0x4AAAAAADmKZAkmJVxUyvHF&action=account_check&proxy=http%3A%2F%2Fuser%3Apass%40host%3Aport&timeout=90
```

| Query | Bắt buộc | Ý nghĩa |
|---|---|---|
| `url` | Có | URL trang chứa widget |
| `sitekey` | Có | Sitekey công khai của widget |
| `action` | Không | Giá trị binding `data-action`, nếu widget có sử dụng |
| `cdata` | Không | Giá trị binding `data-cdata`, nếu widget có sử dụng |
| `proxy` | Không | Proxy riêng cho task, ví dụ `http://user:pass@host:port` |
| `timeout` | Không | Budget giải (route + real-page) sau khi browser khởi động, mặc định 90, tối thiểu 10 |

Proxy truyền trực tiếp được ưu tiên và được áp dụng cho browser context **trước khi** điều hướng, nên Turnstile thấy IP exit của proxy thay vì IP server. Nếu không có, server chọn từ `proxies.txt` khi bật `--proxy`. Mật khẩu proxy được mask trong log.

`timeout` không bao gồm thời gian xếp hàng (semaphore) và thời gian khởi động browser; client vẫn cần deadline tổng riêng. Giá trị `< 10` hoặc không phải integer được thay bằng 90.

Với sitekey gắn domain (ví dụ iHerb `checkout9.iherb.com`), solver render widget nhân tạo ngay tại origin đích thay vì tải trang thật, nên không cần vượt WAF 403 của trang. `action` phải khớp với cấu hình widget; nếu sitekey yêu cầu `action` mà client bỏ qua, token sẽ không được cấp.

Response tạo task thành công, HTTP 200:

```json
{"errorId":0,"taskId":"69b669a2-9fa5-4a81-b1ce-ed874c2482a1"}
```

Đây chỉ là xác nhận đã tạo task, chưa phải giải thành công.

## 3. Tạo task cf_clearance

```http
GET /cf_clearance?url=<encoded-page-url>&timeout=60
```

| Query | Bắt buộc | Ý nghĩa |
|---|---|---|
| `url` | Có | URL trang cần truy cập |
| `proxy` | Không | Proxy riêng cho task, ví dụ `http://user:pass@host:port` |
| `timeout` | Không | Số giây chờ cookie, kiểu integer, mặc định 60, tối thiểu 10 |

Proxy truyền trực tiếp được ưu tiên; nếu không có, server chọn từ `proxies.txt` khi bật `--proxy`. Nếu không có proxy khả dụng, dùng kết nối trực tiếp. Giá trị `timeout` không chuyển được sang integer hoặc `< 10` sẽ dùng mặc định 60; agent nên tự kiểm tra số nguyên dương trước khi gửi.

Response tạo task giống Turnstile. `timeout` không phải deadline tổng của task: thời gian xếp hàng, khởi động browser, điều hướng và thao tác trang nằm ngoài khoảng chờ cookie này.

## 4. Poll kết quả

```http
GET /result?id=<taskId>
```

Đang xử lý hoặc đang đợi slot:

```json
{"status":"processing"}
```

Response này không có `errorId`. Không được coi thiếu `errorId` là lỗi.

Turnstile thành công:

```json
{"errorId":0,"status":"ready","solution":{"token":"<token>"}}
```

`solution` của Turnstile chỉ có `token`; server không trả `method` hoặc thời gian xử lý của loại task này.

cf_clearance thành công, ví dụ minh họa cấu trúc:

```json
{
  "errorId": 0,
  "status": "ready",
  "solution": {
    "cf_clearance": {
      "name": "cf_clearance",
      "value": "<cookie-value>",
      "domain": ".example.com",
      "path": "/",
      "expires": 1800000000,
      "httpOnly": true,
      "secure": true,
      "sameSite": "None"
    },
    "cookies": [],
    "user_agent": "<browser-user-agent>",
    "headers": {"User-Agent": "<browser-user-agent>", "Accept-Language": "en-US"},
    "elapsed": 12.3,
    "elapsed_time": 14.567,
    "proxy": null,
    "warning": "cf_clearance is bound to IP + JA3/TLS + User-Agent. Replay only from the same IP, with this exact User-Agent, over a TLS stack producing the same JA3."
  }
}
```

`cookies` thực tế là danh sách cookie lấy từ browser, bao gồm cookie clearance khi thành công. Cấu trúc cookie có thể có thêm trường do browser cung cấp. `proxy` là chuỗi proxy đã chọn hoặc `null`. `elapsed` là thời gian trong solver; `elapsed_time` bao gồm khởi động browser nhưng không bao gồm thời gian đợi semaphore. Không coi việc nhận cookie là đảm bảo mọi HTTP client có thể dùng lại phiên: IP, User-Agent và TLS fingerprint có ảnh hưởng như trường `warning` mô tả.

## 5. Lỗi và cách xử lý

Các lỗi nghiệp vụ dưới đây cũng trả HTTP 200. Agent phải kiểm tra JSON, không chỉ HTTP status.

```json
{
  "errorId": 1,
  "errorCode": "ERROR_CAPTCHA_UNSOLVABLE",
  "errorDescription": "Workers could not solve the Captcha"
}
```

| `errorCode` | Điều kiện | Hành động phía client |
|---|---|---|
| `ERROR_WRONG_PAGEURL` | Thiếu `url` hoặc thiếu `sitekey` đối với Turnstile | Sửa input; không retry nguyên request |
| `ERROR_WRONG_PROXY` | Chuỗi `proxy` không parse được | Sửa định dạng proxy; không retry nguyên request |
| `ERROR_WRONG_CAPTCHA_ID` | Thiếu ID, ID không tồn tại, bị cleanup hoặc server đã restart | Dừng polling ID này; báo mất task |
| `ERROR_CAPTCHA_UNSOLVABLE` | Solver không có kết quả hoặc có exception, kể cả lỗi browser | Dừng polling; đọc log server để tìm nguyên nhân |

Response lỗi không có `status: "fail"`. `fail` chỉ là trạng thái nội bộ. Exception chi tiết không được gửi về client.

HTTP khác 2xx, JSON không hợp lệ và lỗi network phải được xử lý riêng. Có thể retry GET `/result` khi lỗi network tạm thời với giới hạn deadline. Không tự động retry vô hạn request tạo task: mỗi lần gọi tạo task mới và không có idempotency key, kể cả khi client mất response của lần trước.

## 6. Quy trình mà agent cần triển khai

1. Đọc base URL từ cấu hình môi trường; tạo adapter server-side dùng chung HTTP client của project.
2. Kiểm tra input rồi gọi endpoint tạo task đúng loại. Kiểm tra `errorId` và `taskId`.
3. Lưu `taskId`, poll `/result` mỗi 2 giây trong deadline hữu hạn.
4. Với `processing`, tiếp tục; với `errorId: 1`, trả lỗi có mã cho caller.
5. Với `ready`, kiểm tra `solution` đúng loại rồi trả kết quả cho flow của project.
6. Khi deadline phía client hết, báo timeout cùng `taskId`. Task phía server vẫn có thể chạy vì không có API cancel.

Không giả định đây là API tương thích đầy đủ với dịch vụ captcha khác. Không gọi `/createTask`, `/getTaskResult`, không gửi `clientKey` và không đổi GET thành POST.

Task lưu trong RAM; restart server sẽ mất toàn bộ task. Task cũ hơn 3.600 giây tính từ lúc tạo được dọn mỗi 600 giây. Mặc định server chạy tối đa 4 task đồng thời; task còn lại chờ và vẫn có trạng thái `processing`. Nếu triển khai nhiều worker/process, bộ nhớ task không được chia sẻ; tạo task và polling phải tới cùng process hoặc cần thay đổi storage trước.

## 7. Client tham khảo JavaScript / TypeScript

Ví dụ dùng `fetch` và `AbortSignal.timeout` trên Node.js hiện đại; không cần dependency bổ sung. Hàm trả `solution` của cả hai loại task. Mỗi request tối đa 15 giây và không vượt deadline còn lại.

```javascript
const BASE_URL = (process.env.SOLVER_BASE_URL ?? 'http://127.0.0.1:5072').replace(/\/$/, '');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

export async function solve(type, params, deadlineMs = 180_000) {
  if (!['turnstile', 'cf_clearance'].includes(type)) throw new Error('Invalid solver type');
  if (!params.url || (type === 'turnstile' && !params.sitekey)) throw new Error('Missing solver input');
  const end = Date.now() + deadlineMs;
  let taskId;

  async function get(path, query) {
    const remaining = end - Date.now();
    if (remaining <= 0) throw new Error(`Solver deadline exceeded; taskId=${taskId ?? 'unknown'}`);
    const url = new URL(BASE_URL + path);
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }
    const response = await fetch(url, {signal: AbortSignal.timeout(Math.min(15_000, remaining))});
    if (!response.ok) throw new Error(`Solver HTTP ${response.status}`);
    const body = await response.json();
    if (!body || typeof body !== 'object') throw new Error('Invalid solver JSON');
    if (body.errorId === 1) {
      throw new Error(`${body.errorCode}: ${body.errorDescription}; taskId=${taskId ?? 'unknown'}`);
    }
    return body;
  }

  const created = await get('/' + type, params);
  if (created.errorId !== 0 || typeof created.taskId !== 'string') throw new Error('Invalid create response');
  taskId = created.taskId;
  while (Date.now() < end) {
    const result = await get('/result', {id: taskId});
    if (result.status === 'ready' && result.errorId === 0) {
      const solution = result.solution;
      if (type === 'turnstile' ? !solution?.token : !solution?.cf_clearance?.value) {
        throw new Error('Invalid solver solution');
      }
      return solution;
    }
    if (result.status !== 'processing') throw new Error('Unexpected solver response');
    await sleep(Math.min(2_000, Math.max(0, end - Date.now())));
  }
  throw new Error(`Solver deadline exceeded; taskId=${taskId}`);
}
```

Ví dụ kiểm tra với test key:

```javascript
const solution = await solve('turnstile', {
  url: 'https://demo.turnstile.workers.dev/',
  sitekey: '1x00000000000000000000AA',
});
console.log(solution.token);
```

Test key trên đã trả `XXXX.DUMMY.TOKEN.XXXX` trong phiên kiểm tra local. Kết quả này xác nhận luồng tạo task, browser và polling hoạt động với test key; chưa chứng minh khả năng giải challenge thật.

Ví dụ challenge thật, có proxy và action:

```javascript
const solution = await solve('turnstile', {
  url: 'https://checkout9.iherb.com/auth/ui/account/login',
  sitekey: '0x4AAAAAADmKZAkmJVxUyvHF',
  action: 'account_check',
  proxy: 'http://user:pass@host:port',
  timeout: 90,
}, 240_000);
console.log(solution.token.length); // ~752
```

Lưu ý:

- `timeout` trong `params` là budget phía server, không thay thế `deadlineMs` phía client.
- Với `cf_clearance`, dùng `proxy` giống nhau cho request replay sau đó; cookie gắn với IP exit.
- Token thật thường dài 300–800 ký tự. Token demo `XXXX.DUMMY.TOKEN.XXXX` không dùng được trong flow nghiệp vụ.

## 8. Khởi động và chẩn đoán server

```powershell
python -m pip install -r requirements.txt
$env:PYTHONUTF8='1'
python api.py
```

Mặc định: Chrome hệ thống, **headed** (hiện cửa sổ), cổng 5072, bind `0.0.0.0`, concurrency 4. Nếu dùng Chromium đã cài qua Patchright:

```powershell
python -m patchright install chromium
python api.py --browser_type chromium --host 127.0.0.1 --port 5072 --thread 4
```

`--debug` bật log chi tiết kèm fingerprint (`webdriver`, plugins, WebGL, timezone). `--headless` chạy không cửa sổ nhưng **chỉ dùng được với test key**: Cloudflare thật từ chối headless kể cả khi đã vá stealth. `--no-headless` là mặc định. `--proxy` bật chọn proxy từ file.

Không dùng `--useragent` cho challenge thật: UA bị ép khác phiên bản Chrome thực sẽ làm `navigator.userAgentData` không khớp và bị chấm điểm bot. Không inject thêm JavaScript fingerprint: đã kiểm chứng rằng bất kỳ `add_init_script` nào (kể cả chuỗi rỗng) đều bị Turnstile phát hiện. Chỉ dựa vào Patchright + Chrome headed native.

Khi API báo unsolvable, kiểm tra log trước vì lỗi browser thiếu executable cũng có cùng mã lỗi với challenge không giải được. Server không kiểm tra browser bằng cách chạy task khi mới khởi động.

### Chẩn đoán iHerb

Target tham chiếu: `https://checkout9.iherb.com/auth/ui/account/login`, sitekey `0x4AAAAAADmKZAkmJVxUyvHF`, action `account_check`.

```powershell
$u = 'https%3A%2F%2Fcheckout9.iherb.com%2Fauth%2Fui%2Faccount%2Flogin'
Invoke-RestMethod "http://127.0.0.1:5072/turnstile?url=$u&sitekey=0x4AAAAAADmKZAkmJVxUyvHF&action=account_check"
# poll /result?id=... -> token dài ~752 ký tự
```

Nếu log ghi `Real-page returned HTTP 403 (Cloudflare WAF?)` nhưng vẫn thấy `Turnstile solved via route`, đó là hành vi đúng: WAF chỉ chặn trang thật, còn route-intercept render widget tại origin đích. Nếu lần đầu fail rồi fallback real-page, kiểm tra proxy/IP và đảm bảo browser không chạy headless.

### Định dạng proxy

`proxies.txt` nhận một proxy mỗi dòng; dòng trống và dòng bắt đầu bằng `#` bị bỏ qua. Query `proxy` chấp nhận cùng định dạng:

```text
1.2.3.4:8080
1.2.3.4:8080:user:pass
user:pass@1.2.3.4:8080
socks5://1.2.3.4:1080
http://user:pass@1.2.3.4:8080
```

### Lưu ý vận hành

- `--thread 4` mở tối đa 4 cửa sổ Chrome; giảm nếu server thiếu RAM/CPU.
- Windows cần session desktop tương tác; Linux cần `xvfb-run` hoặc display thật.
- `GET /` trả HTML, không phải JSON health check. Muốn kiểm tra sống/chết, dùng TCP connect hoặc gọi `/result` và kiểm tra HTTP 200.
- Firewall/security group phải mở đúng cổng nếu client chạy máy khác; `0.0.0.0` chỉ là địa chỉ bind.

## 9. Tiêu chí hoàn tất tích hợp

- Base URL và deadline có thể cấu hình, không hardcode theo máy phát triển.
- Luồng test key trả dummy token qua adapter của project.
- Xử lý đủ: lỗi tạo task, `ERROR_WRONG_PROXY`, processing, ready, unsolvable, ID không tồn tại, HTTP/network error và timeout.
- Proxy được truyền theo từng request khi cần đổi IP exit; server chạy headed cho challenge thật.
- Không log token, cookie hoặc mật khẩu proxy trong log thông thường.
- Không coi demo dummy token là token thật để sử dụng trong flow nghiệp vụ.
