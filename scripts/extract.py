import re
import subprocess
import os
from typing import List, Tuple

def is_comment(stripped_line):
    # 检查是否为单行注释
    if re.match(r'//', stripped_line):
        return 1

    # 检查是否是*开头的单行注释
    if re.match(r'^\s*\*\s', stripped_line):
        return 2
    
    # 多行注释的起始
    if re.match(r'/\*', stripped_line):
        return 3
    
    # 多行注释结束
    if re.match(r'\*/', stripped_line):
        return 4
    
    return 0

def normalize_method_signature(method_signature: str) -> str:
    """
    规范化 Java 方法签名：
    1. 去掉方法参数列表前后的空格
    2. 确保括号紧贴参数
    
    :param method_signature: 原始方法签名，例如 "startDataNode(Configuration conf, AbstractList<File> dataDirs, SecureResources resources )"
    :return: 规范化后的方法签名，例如 "startDataNode(Configuration conf, AbstractList<File> dataDirs, SecureResources resources)"
    """
    # 移除参数列表中的多余空格（确保括号和参数之间没有空格）
    method_signature = re.sub(r'\s*,\s*', ', ', method_signature)  # 确保逗号后有一个空格
    method_signature = re.sub(r'\s*\(\s*', '(', method_signature)  # 确保 `(` 直接紧贴方法名
    method_signature = re.sub(r'\s*\)\s*', ')', method_signature)  # 确保 `)` 直接紧贴最后一个参数
    
    return method_signature

def get_hunk_lines(commit_hash: str, file_path: str, repo_path: str) -> Tuple[List[int], List[int]]:
    """获取文件在指定 commit **修改前后的 hunk 行号**
    
    Returns:
        - old_lines: 旧版本被删除的具体行号（每个 `-` 行）
        - new_lines: 新版本新增的具体行号（每个 `+` 行）
    """
    # repo_path = "E:/dachuang2024/tmp/tmp/hadoop"
    os.chdir(repo_path)
    cmd = ["git", "diff", commit_hash + "^!", "--", file_path]
    diff_output = subprocess.run(cmd, capture_output=True, text=True).stdout
    lines = diff_output.split("\n")
    
    old_lines = []
    new_lines = []
    current_old_line = None
    current_new_line = None

    for line in lines:
        # 解析 hunk 头，例如：@@ -12,5 +15,6 @@
        hunk_match = re.match(r'@@ -(\d+),?\d* \+(\d+),?', line)
        if hunk_match:
            current_old_line = int(hunk_match.group(1))  # 旧版本起始行号
            current_new_line = int(hunk_match.group(2))  # 新版本起始行号
            continue  # 进入下一个循环
        
        # 处理删除的行（旧版本）
        if line.startswith("-") and not line.startswith("---"):
            old_lines.append(current_old_line)  # 记录具体删除的行号
            # print(current_old_line)
            current_old_line += 1  # 递增旧版本行号
        
        # 处理新增的行（新版本）
        elif line.startswith("+") and not line.startswith("+++"):
            new_lines.append(current_new_line)  # 记录具体新增的行号
            # print(current_new_line)
            current_new_line += 1  # 递增新版本行号
        
        # 普通未修改的代码，保持行号同步
        elif not line.startswith("-") and not line.startswith("+"):
            if current_old_line is not None:
                current_old_line += 1
            if current_new_line is not None:
                current_new_line += 1

    return old_lines, new_lines

import re
from typing import List, Tuple
import re
from typing import List, Tuple

def extract_method_ranges(file_content: str) -> List[Tuple[str, int, int]]:
    """从 Java 代码中提取方法的名称、起始行号和结束行号"""
    lines = file_content.split("\n")
    
    # Java 方法定义匹配（支持泛型方法、静态方法等）
    method_pattern = re.compile(
        r'\b(public\s+|private\s+|protected\s+|static\s+|final\s+|synchronized\s+|abstract\s+|native\s+)*' 
        r'(\w+(\[\])?)\s+'  # 匹配如 'void', 'int' 等返回类型, 并允许有多个空格 捕获组2
        r'(\w+)\s*'  # 匹配方法名，捕获组4
        r'(\([^$]*\))\s*' # 匹配参数列表,一个捕获组
        # r'(\(.*?$)' 
        r'(?:\s*throws\s+([\w\s,]+))?\s*' 
        r'\{?'  # 可选的起始大括号
    )
    semicolon_at_end = re.compile(r'.*;\s*$')
    control_keywords = {'if', 'else', 'for', 'while', 'switch', 'catch', 'finally', 'try','IOException'}
    annotation_pattern = re.compile(r'^\s*@')  # 识别 `@Override` 等注解

    method_ranges = []
    current_method = None
    start_line = None
    buffer = ""  # 用于拼接多行方法声明
    count = 0
    buffer_num = 0
    flag = 0 # 记录是否在方法中
    in_multiline_comment = 0  # 计数器，跟踪未闭合的多行注释
    
    stack = []

    for i, line in enumerate(lines, start=1):
        stripped_line = line.strip()

        # 检查是否进入或退出多行注释(只针对不在方法里时)
        if not in_multiline_comment and is_comment(stripped_line) == 3 and flag == 0:
            in_multiline_comment += 1
        if in_multiline_comment and is_comment(stripped_line) == 4 and flag == 0:
            in_multiline_comment -= 1
        
        # 如果在多行注释中，跳过处理
        if in_multiline_comment > 0:
            continue

        # 忽略单行注释
        if is_comment(stripped_line) in [1, 2]:
            continue

        # 1. 过滤接口方法和 `;` 结尾的行
        if semicolon_at_end.search(stripped_line) and flag == 0:
            buffer = ""  # 可能是接口方法，重置缓冲
            continue

        # 2. 处理方法前的 `@Annotation`
        if annotation_pattern.match(stripped_line):
            continue  # 忽略注解，不存入 `buffer`

        # 3. 处理多行方法声明
        if stripped_line != "}" and stripped_line != "*/" and flag == 0:
            buffer += " " + stripped_line  # 累积方法头

        # 4. 只有当 `{` 出现时，才尝试匹配方法
        
        if "{" in stripped_line and flag == 0:
            match = method_pattern.search(buffer)
            if match:
               
                # current_method = f"{match.group(2)}({match.group(3).strip()})"
                # print("buffer:",buffer)
                buffer_num+=1
                method_name = match.group(4) # 方法名
                parameters_str = match.group(5)  # 参数列表
                if method_name in control_keywords:
                    continue

                current_method = f"{method_name}{parameters_str if parameters_str else ''}"
                count+=1
                flag = 1
               
                start_line = i
                # stack.append("{")  # 方法开始，压入 `{`
                # print("方法开始")
                stack = [] # 方法开始，栈置空
                buffer = ""  # 清空缓冲
                

        # 5. 逐字符处理 `{}`，确保方法完整匹配
        if "{" in stripped_line or "}" in stripped_line:
            # print(stripped_line)
            for char in stripped_line:
                if char == "{":
                    stack.append("{")
                elif char == "}":
                    if stack:
                        stack.pop()
                        

        # 6. 方法结束
        if current_method and not stack:
            current_method = normalize_method_signature(current_method)
            method_ranges.append((current_method, start_line, i))
            # print(f"Method: {current_method}, Start: {start_line}, End: {i}")
            current_method = None
            start_line = None
            stack = []
            flag = 0

    # print(count)
    # print(buffer_num)
    return method_ranges

def get_file_content(commit_hash: str, file_path: str, repo_path: str) -> str:
    """获取指定 commit 版本的 Java 文件内容"""
    # repo_path = "E:/dachuang2024/tmp/tmp/hadoop"
    os.chdir(repo_path)
    cmd = ["git", "show", f"{commit_hash}:{file_path}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""

def get_modified_methods(commit_hash: str, file_path: str, repo_path: str):
    """获取受影响的方法，并记录每个方法内的修改行号（基于新旧版本对比）

    Returns:
        method_changes: { 方法签名: [修改行号列表] }
    """
    old_lines, new_lines = get_hunk_lines(commit_hash, file_path,repo_path)

    # 获取旧版本和新版本的代码
    old_code = get_file_content(f"{commit_hash}^", file_path,repo_path)  # 旧版本
    new_code = get_file_content(commit_hash, file_path,repo_path)  # 新版本

    # 提取方法范围
    old_methods = extract_method_ranges(old_code)
    new_methods = extract_method_ranges(new_code)

    method_changes = {}

    # 在旧版本中查找 `-` 删除行所属的方法
    for hunk in old_lines:
        for method_name, start, end in old_methods:
            if start <= hunk <= end:
                if method_name not in method_changes:
                    method_changes[method_name] = []
                method_changes[method_name].append(hunk - start + 1)  # 计算相对行号

    # 在新版本中查找 `+` 新增行所属的方法
    for hunk in new_lines:
        for method_name, start, end in new_methods:
            if start <= hunk <= end:
                if method_name not in method_changes:
                    method_changes[method_name] = []
                method_changes[method_name].append(hunk - start + 1)  # 计算相对行号

    return method_changes

# 示例调用
# print(get_modified_methods("abc123", "src/Main.java"))
# commit_hash = "957c56dbe5b1490490c09ddfbca9a4204c7c9d00"
# file_path = "hadoop-hdfs-project/hadoop-hdfs/src/main/java/org/apache/hadoop/hdfs/server/datanode/DataNode.java"
# print(get_modified_methods(commit_hash, file_path))