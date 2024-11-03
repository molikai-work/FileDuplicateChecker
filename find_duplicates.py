import os
import hashlib
import random
import string
import sys
import ctypes
from collections import defaultdict
from datetime import datetime
from typing import List, Tuple, Dict, Optional
import tkinter as tk
from tkinter import messagebox


def request_admin_permission() -> bool:
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True

    root = tk.Tk()
    root.withdraw()
    response = messagebox.askyesno("权限请求", "该程序需要管理员权限来访问受限区域。您是否允许？")
    if response:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()
    return False


def calculate_file_hash(file_path: str) -> Optional[str]:
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
    except Exception as e:
        print(f"\n无法读取文件 {file_path}: {e}")
        return None
    return hash_md5.hexdigest()


def log_scanned_items(log_file: Optional[str], scanned_items: List[str], failed_items: List[str]) -> None:
    if log_file:
        with open(log_file, 'a', encoding="utf-8") as f:
            f.write("\n扫描的文件和文件夹:\n" + "\n".join(scanned_items) + "\n")
            if failed_items:
                f.write("\n扫描失败的文件和文件夹:\n" + "\n".join(failed_items) + "\n")


def generate_unique_log_filename(base_name: str) -> str:
    while True:
        log_filename = f"{base_name}_{''.join(random.choices(string.ascii_letters + string.digits, k=4))}_findDuplicatesLog.txt"
        if not os.path.exists(log_filename):
            return log_filename


def update_progress(message: str) -> None:
    sys.stdout.write(f"\r{message}")
    sys.stdout.flush()


def find_duplicates(start_dir: str, check_files: bool, check_dirs: bool,
                    check_content: bool, exclude_extensions: Optional[List[str]],
                    max_depth: Optional[int], log_file: Optional[str]) -> Dict[str, List[Tuple[str, str]]]:
    items = defaultdict(list)
    scanned_items = []
    failed_items = []

    try:
        for dirpath, dirnames, filenames in os.walk(start_dir):
            depth = dirpath[len(start_dir):].count(os.sep)
            if max_depth is not None and depth > max_depth:
                dirnames.clear()
                continue
            
            if check_dirs:
                for dirname in dirnames:
                    dir_path = os.path.join(dirpath, dirname)
                    scanned_items.append(f"文件夹: {dir_path}")
                    update_progress(f"正在扫描: {dir_path}")
                    items[dirname].append((dir_path, 'folder'))

            if check_files:
                for filename in filenames:
                    if exclude_extensions and any(filename.lower().endswith(ext) for ext in exclude_extensions):
                        continue

                    file_path = os.path.join(dirpath, filename)
                    scanned_items.append(f"文件: {file_path}")
                    update_progress(f"正在扫描: {file_path}")

                    if check_content:
                        file_hash = calculate_file_hash(file_path)
                        if file_hash:
                            items[file_hash].append((file_path, 'file'))
                        else:
                            failed_items.append(f"文件读取失败: {file_path}")
                    else:
                        items[filename].append((file_path, 'file'))

    except Exception as e:
        print(f"\n在遍历目录时发生错误: {e}")
        return {}

    log_scanned_items(log_file, scanned_items, failed_items)
    return {name: details for name, details in items.items() if len(details) > 1}


def format_output(duplicates: Dict[str, List[Tuple[str, str]]], check_content: bool, log_file: Optional[str]) -> None:
    if not duplicates:
        print("\n没有找到重复的条目。\n")
        if log_file:
            with open(log_file, 'a', encoding="utf-8") as f:
                f.write("\n没有找到重复的条目。\n")
        return

    output = ["\n重复条目信息:", "=" * 50]
    for index, (name, details) in enumerate(duplicates.items()):
        item_type = details[0][1]
        paths = [entry[0] for entry in details]
        
        if item_type == 'file':
            output.append(f"类型: 文件\nMD5: {name if check_content else '不适用'}")
            for i, (path, _) in enumerate(details, start=1):
                md5_hash = calculate_file_hash(path) if not check_content else "已提供"
                output.append(f"MD5 {i}: {md5_hash}\n路径 {i}: {path}")

        else:
            output.append(f"类型: 文件夹\n名称: {name}")
            output.extend(f"路径 {i}: {path}" for i, path in enumerate(paths, start=1))

        if index < len(duplicates) - 1:
            output.append("-" * 50)

    output.append("=" * 50)
    print("\n".join(output))

    if log_file:
        with open(log_file, 'a', encoding="utf-8") as f:
            f.write("\n".join(output) + "\n")


def get_user_choice() -> str:
    while True:
        print("\n请选择检查类型:")
        print("1. 仅检查文件名")
        print("2. 仅检查文件夹名")
        print("3. 检查所有")
        
        choice = input("请输入选项 (1/2/3): ")
        if choice in ['1', '2', '3']:
            return choice
        print("无效的选项，请重新输入。")


def standardize_extensions(extensions_input: str) -> List[str]:
    extensions = [ext.lower().strip() for ext in extensions_input.split(",")]
    return [ext if ext.startswith(".") else f".{ext}" for ext in extensions]


def main() -> None:
    if request_admin_permission():
        print("管理员权限已获得。")

    choice = get_user_choice()
    check_files = choice in ['1', '3']
    check_dirs = choice in ['2', '3']
    check_content = choice != '2' and input("是否检查文件内容? (y/n)，留空表示不检查: ").strip().lower() == 'y'

    exclude_extensions_input = input("请输入要排除的文件扩展名（例如 txt,jpg,png），留空表示不排除: ").strip().lower()
    exclude_extensions = standardize_extensions(exclude_extensions_input) if exclude_extensions_input else None

    max_depth = input("请输入递归深度限制（整数），留空表示不限制: ").strip()
    max_depth = int(max_depth) if max_depth.isdigit() else None

    log_file = None
    if input("是否记录日志? (y/n)，留空表示不记录: ").strip().lower() == 'y':
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
        log_file = generate_unique_log_filename(timestamp)
        with open(log_file, 'w', encoding="utf-8") as f:
            f.write(f"扫描开始时间: {datetime.now()}\n扫描设置:\n  检查文件: {check_files}\n  检查文件夹: {check_dirs}\n  检查内容: {check_content}\n  排除扩展名: {exclude_extensions}\n  最大递归深度: {max_depth}\n\n")

    print("\n正在检查当前目录及其子目录...")
    current_directory = os.getcwd()
    print(f"当前目录: {current_directory}\n")

    duplicates = find_duplicates(current_directory, check_files, check_dirs, check_content, exclude_extensions, max_depth, log_file=log_file)
    format_output(duplicates, check_content, log_file=log_file)

    if log_file:
        end_time = datetime.now()
        with open(log_file, 'a', encoding="utf-8") as f:
            f.write(f"\n扫描结束时间: {end_time}\n")

    print("检查完成，请查看输出。\n")
    input("按任意键退出...")


if __name__ == "__main__":
    main()
