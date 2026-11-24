"""FntvDoubanSync 发布门禁

校验内容：
1. package.v2.json 与代码元数据一致性（版本、名称、目录、图标、history）
2. 插件目录 Python 语法（py_compile）
3. 插件目录隔离：不得包含 test_*.py / __pycache__ / frontend / node_modules
4. （存在 dist/assets 时）Vue 模块联邦产物门禁（Phase 2）

用法：python scripts/check_plugin.py
"""

import json
import py_compile
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins.v2" / "fntvdoubansync"
PACKAGE_FILE = ROOT / "package.v2.json"
PLUGIN_ID = "FntvDoubanSync"

FORBIDDEN_IN_PLUGIN = ("test_", "__pycache__", "node_modules", "frontend")


def fail(msg: str) -> int:
    print(f"  [FAIL] {msg}")
    return 1


def ok(msg: str) -> int:
    print(f"  [ OK ] {msg}")
    return 0


def check_metadata() -> int:
    print("== 元数据一致性 ==")
    errors = 0

    if not PACKAGE_FILE.exists():
        return fail(f"缺少 {PACKAGE_FILE.relative_to(ROOT)}")
    package = json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))
    meta = package.get(PLUGIN_ID)
    if meta is None:
        return fail(f"{PACKAGE_FILE.name} 缺少顶层 Key {PLUGIN_ID}")

    init_file = PLUGIN_DIR / "__init__.py"
    if not init_file.exists():
        return fail(f"缺少 {init_file.relative_to(ROOT)}")
    source = init_file.read_text(encoding="utf-8")

    m = re.search(r'^\s*plugin_version\s*=\s*"([^"]+)"', source, re.MULTILINE)
    if not m:
        return fail("__init__.py 中未找到 plugin_version")
    code_version = m.group(1)

    if meta.get("version") != code_version:
        errors += fail(f"package.v2.json version={meta.get('version')!r} "
                       f"!= plugin_version={code_version!r}")
    else:
        ok(f"版本一致：{code_version}")

    history = meta.get("history") or {}
    if f"v{code_version}" not in history:
        errors += fail(f"history 缺少 v{code_version} 条目")
    else:
        ok("history 已含当前版本记录")

    if meta.get("v2") is not True:
        errors += fail("package.v2.json 未声明 \"v2\": true")
    else:
        ok("已声明 v2 兼容")

    if PLUGIN_DIR.name != PLUGIN_ID.lower():
        errors += fail(f"插件目录名 {PLUGIN_DIR.name} 应为类名全小写 {PLUGIN_ID.lower()}")
    else:
        ok("插件目录命名规范")

    icon = meta.get("icon") or ""
    if not icon:
        errors += fail("package.v2.json 缺少 icon")
    elif icon.startswith("http"):
        # 完整 URL：第三方仓库惯例，须指向本仓库 main 分支的 icons/ 目录
        expected_prefix = (f"https://raw.githubusercontent.com/"
                           f"{meta.get('author') or 'wastedwood'}/MoviePilot-Plugins/main/icons/")
        if not icon.startswith(expected_prefix) or not icon.endswith(".png"):
            errors += fail(f"icon 完整 URL 不符合本仓库约定：应以 {expected_prefix} 开头")
        else:
            icon_name = icon.rsplit("/", 1)[-1]
            if not (ROOT / "icons" / icon_name).exists():
                errors += fail(f"icons/{icon_name} 不存在")
            else:
                ok(f"图标存在（完整 URL）：icons/{icon_name}")
    elif not (ROOT / "icons" / icon).exists():
        errors += fail(f"icons/{icon} 不存在")
    else:
        ok(f"图标存在：icons/{icon}")

    if not re.search(rf"^class\s+{PLUGIN_ID}\(_PluginBase\)", source, re.MULTILINE):
        errors += fail(f"__init__.py 未定义 class {PLUGIN_ID}(_PluginBase)")
    else:
        ok(f"插件类 {PLUGIN_ID}(_PluginBase)")

    # 分身友好：禁止在插件内硬编码插件 ID 字符串读写配置/路径
    if re.search(rf"[\"']{PLUGIN_ID}[\"']", source):
        errors += fail(f"__init__.py 硬编码了 {PLUGIN_ID} 字符串（应使用 self.__class__.__name__）")
    else:
        ok("无硬编码插件 ID 字符串")

    return errors


def check_syntax() -> int:
    print("== Python 语法 ==")
    errors = 0
    # 编译到临时目录，避免在插件目录留下 __pycache__
    with tempfile.TemporaryDirectory(prefix="check-plugin-") as tmpdir:
        for py in sorted(PLUGIN_DIR.rglob("*.py")):
            cfile = str(Path(tmpdir) / f"{py.stem}.pyc")
            try:
                py_compile.compile(str(py), doraise=True, cfile=cfile)
                ok(f"{py.relative_to(ROOT)}")
            except py_compile.PyCompileError as e:
                errors += fail(f"{py.relative_to(ROOT)}: {e}")
    return errors


def check_isolation() -> int:
    print("== 插件目录隔离 ==")
    errors = 0
    for path in PLUGIN_DIR.rglob("*"):
        rel = path.relative_to(PLUGIN_DIR).as_posix()
        for keyword in FORBIDDEN_IN_PLUGIN:
            if keyword in rel:
                errors += fail(f"{rel}：插件目录不允许出现 {keyword}"
                               "（MoviePilot 安装时会整目录复制插件目录）")
    if not errors:
        ok("插件目录干净（无测试 / 构建源码 / 缓存）")
    return errors


def check_federation_dist() -> int:
    """Phase 2：dist/assets 联邦产物门禁（目录不存在时跳过）"""
    assets = PLUGIN_DIR / "dist" / "assets"
    print("== Vue 模块联邦产物 ==")
    if not assets.exists():
        print("  [SKIP] 未发现 dist/assets（Phase 2 尚未构建）")
        return 0

    errors = 0
    files = [f for f in assets.rglob("*") if f.is_file()]
    if not any(f.name == "remoteEntry.js" for f in files):
        errors += fail("dist/assets 缺少 remoteEntry.js")

    for f in files:
        if f.name.startswith(("index-", "date-", "runtime-")):
            errors += fail(f"dist/assets 含禁拷贝文件：{f.relative_to(assets)}")

    for f in files:
        if any(part.startswith("__federation_shared") for part in f.parts):
            errors += fail(f"dist/assets 含共享依赖产物：{f.relative_to(assets)}")

    for f in files:
        if f.suffix == ".css":
            css = f.read_text(encoding="utf-8", errors="replace")
            # 全局 .v- / .mdi- 类规则会污染宿主样式
            stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
            if re.search(r"(?m)^[^@\n{}]*\.(?:v-|mdi-)[\w-]", stripped):
                errors += fail(f"{f.relative_to(assets)} 含未限定作用域的 .v-/.mdi- 全局样式")
    if not errors:
        ok(f"dist/assets 联邦产物合规（{len(files)} 个文件）")
    return errors


def main() -> int:
    print(f"FntvDoubanSync 发布门禁：{ROOT}\n")
    total = 0
    total += check_metadata()
    print()
    total += check_syntax()
    print()
    total += check_isolation()
    print()
    total += check_federation_dist()
    print()
    if total:
        print(f"门禁未通过：{total} 处问题")
        return 1
    print("门禁全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
