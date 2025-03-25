import subprocess
import json
from pathlib import Path
import tree_sitter
from tree_sitter import Language, Parser
import warnings
import os
import csv
import re
from concurrent.futures import ThreadPoolExecutor
import requests
import time
from tempfile import TemporaryDirectory
access_token = "your_token" 
import shutil
# 忽略 FutureWarning
warnings.simplefilter('ignore', FutureWarning)



def get_modified_java_files(diff_file_path):
    """从指定的diff文件中获取所有Java文件（被修改的）的文件名列表，不包含文件夹路径。"""
    modified_java_files = []

    # 检查文件是否存在
    if os.path.exists(diff_file_path):
        # 打开并读取文件内容
        with open(diff_file_path, 'r') as file:
            for line in file:
                if line.startswith('diff --git'):
                    # 获取文件的完整路径
                    full_path = line.strip()
                    # 检查是否以.java结尾且不为空
                    if full_path.endswith('.java') and full_path:
                        # 使用os.path.basename获取文件名
                        filename = os.path.basename(full_path)
                        modified_java_files.append(filename)

    return modified_java_files



def get_modified_java_path(repo_path):
    """
    从指定的仓库路径中获取所有修改过的Java文件的文件路径列表。
    参数:
        repo_path (str): 仓库路径。
    返回:
        list: 包含所有修改过的Java文件的文件路径列表。
    """
    path = repo_path + '/diff.txt'
    with open(path, 'r', encoding='utf-8') as file:
        diff_output = file.read()
        get_modifed_java_path = extract_java_file_paths(diff_output)
        return get_modifed_java_path



def run_find_map_test_cases(repo_path, repo_name, grammar_path, output_dir):
    """
    使用 Git Bash 运行 find_map_test_cases.py 脚本。

    参数:
        repo_path (str): 仓库路径。
        repo_name (str): 仓库名称。
        grammar_path (str): tree-sitter Java 语法文件的路径。
        output_dir (str): 输出文件夹的路径。

    返回:
        dict: 包含所有方法签名的列表。
    """
    repo_full_path = os.path.join(output_dir, repo_name)
    json_name = repo_name + '_signature.json'
    json_file_path = os.path.join(repo_full_path,json_name)
    #  如果在tmp/output目录下已经存在repo则不再执行
    # if(os.path.exists(repo_full_path)):

    #     if(os.path.exists(json_file_path)):
    #         with open(json_file_path, 'r') as file:
    #             mapping = json.load(file)
    #             return mapping
    #     else:
    #         return []

    # Git Bash 的路径
    git_bash_path = r"E:/Git/git-bash.exe"
    
    # 要运行的脚本命令
    command = [
        git_bash_path,
        '-c',  # 使用 -c 参数来执行命令
        f"python e:/dachuang/find_map_test_cases.py "  # 使用正斜杠
        f"--repo_path {repo_path} "
        f"--repo_name {repo_name} "
        f"--grammar {grammar_path} "
        f"--output {output_dir}"
    ]
    
    # print(f"Running command: {command}")
    # 执行命令并捕获输出

    subprocess.run(command, capture_output=True, text=True)
    
    if(os.path.exists(json_file_path)):
        with open(json_file_path, 'r') as file:
            mapping = json.load(file)
            return mapping
    else:
        return []



def extract_java_file_paths(diff_output):
    """
    从diff输出中提取所有修改过的Java文件的文件路径。

    参数:
        diff_output (str): 包含diff输出的字符串。

    返回:
        list: 包含所有修改过的Java文件的文件路径列表。    
    """
    pattern = r'(?:a/|b/)([^ \t\n\r\f\v]+)'
    matches = re.findall(pattern, diff_output)

    java_file_paths = [path for path in matches if path.endswith('.java')]

    unique_java_file_paths = list(set(java_file_paths))

    return unique_java_file_paths



def  extract_method_signatures(file_path):
    """
    解析 Java 文件并提取所有方法签名

    :param file_path: Java 文件路径
    :return: 包含所有方法签名的列表
    """
    # 加载 Java 语法库
    JAVA_LANGUAGE = Language('build/my-languages.so', 'java')
    parser = Parser()
    parser.set_language(JAVA_LANGUAGE)
    # 读取要解析的 Java 文件
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            java_code = file.read()
    except FileNotFoundError:
        print(f"文件 {file_path} 不存在")
        return []

    # 使用 Tree-sitter 解析代码
    tree = parser.parse(bytes(java_code, "utf-8"))

    # 输出语法树结构以便调试
    # print("语法树结构：")
    # print(tree.root_node.sexp())

    # Tree-sitter 查询语法，用于提取所有方法声明
    method_query = """
    (method_declaration 
      (modifiers)?
      type: (_) @return_type
      name: (identifier) @method_name
      parameters: (formal_parameters) @param_list
    )
    """
    # 创建 Query 对象并执行查询
    query = JAVA_LANGUAGE.query(method_query)
    captures = query.captures(tree.root_node)

    # 用于存储方法签名的列表
    method_signatures = []
    current_method = {"params": [], "method_name": None, "return_type": None}

    for capture in captures:
        node, capture_name = capture
        if capture_name == 'return_type':
            if current_method['method_name'] is not None:
                # 生成方法签名并添加到列表
                params_str = ", ".join(current_method['params'])
                signature = f"{current_method['return_type']} {current_method['method_name']}({params_str})"
                method_signatures.append(signature)
                current_method = {"params": [], "method_name": None, "return_type": None}
            current_method['return_type'] = node.text.decode('utf-8')

        elif capture_name == 'method_name':
            current_method['method_name'] = node.text.decode('utf-8')

        elif capture_name == 'param_list':
            # 遍历参数列表节点，提取每一个参数
            param_list_node = node
            for i in range(param_list_node.named_child_count):
                param_node = param_list_node.named_child(i)
                param_type_node = param_node.child_by_field_name('type')
                param_name_node = param_node.child_by_field_name('name')
                if param_type_node is None or param_name_node is None:
                    continue

                param_type = param_type_node.text.decode('utf-8')
                param_name = param_name_node.text.decode('utf-8')
                current_method['params'].append(f"{param_type} {param_name}")

    # 捕获最后一个方法的签名
    if current_method['method_name'] is not None:
        params_str = ", ".join(current_method['params'])
        signature = f"{current_method['return_type']} {current_method['method_name']}({params_str})"
        method_signatures.append(signature)

    return method_signatures



def method_exists(mapping, method_signature):
    """
    检查给定的方法签名是否存在于映射列表中。

    参数：
        mapping: 包含方法签名的列表
        method_signature: 方法签名

    返回值: 如果方法存在则返回 True，否则返回 False
    """ 
    if(mapping == []) :
        return False
    # 直接检查给定的方法签名是否在列表中
    return method_signature in mapping



def extract_filename(test_filename):
    # 获得测试文件中的被测试文件名(如果不是test会返回none)
    test_filename = os.path.splitext(test_filename)[0]
    
    # 匹配"test"和"filename"
    match = re.match(r"(test[_-]?)(.+)|(.+?)([_-]?test)", test_filename, re.IGNORECASE)
    if match:
        return match.group(2) if match.group(2) else match.group(3)
    return None



def main():
    base_path = 'E:/dachuang/github_clone'  # 存放所有仓库的目录
    output_file = "E:/dachuang/output.csv"  # 输出文件
    input_csv = "E:/dachuang/output.csv"  # 输入文件
    output_dir = 'E:/dachuang/tmp/output/'  # 输出文件夹的路径
    grammar_path = 'E:/dachuang/build/my-languages.so'  # tree-sitter Java 语法文件的路径

    urls = []
    # 获取 CSV 文件里的 URLs
    max_workers = 5
    with open(input_csv) as csvfile:
        reader = csv.reader(csvfile)
        urls = [row[10] for row in reader]


    # 加载 Java 语法库
    JAVA_LANGUAGE = Language('build/my-languages.so', 'java')
    parser = Parser()
    parser.set_language(JAVA_LANGUAGE)
    
    # os.chdir(base_path)
    header = ['index', 'cwe key word', 'matched key word', 'file', 'func', 'hunk', 'function_name', 'note', 'repo', 'branch', 'url', 'testcase']
    
    # 读取现有的 CSV 文件
    existing_data = []
    with open(output_file, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        existing_data = list(reader)

    # 创建字典，以 URL 为键，testcase 结果为值
    testcase_results = {}

    for url in urls:
        # commit_hash = extract_commit_hash(url)
        
        match = re.search(r'/([^/]+/[^/]+)/commit/', url)
        if not match:
            continue
        repository_name = match.group(1)  # 获取 user/repo
        repo = re.search(r'[^/]+$', repository_name).group()  # 获取 repo
        print("处理仓库:", repo)

        # 修改文件列表modified_java_files（仅java文件）
        repo_path = base_path + '/' + repo
        modified_java_files = get_modified_java_files(repo_path + '/diff.txt')
        
        # 修改文件路径列表modified_java_path（仅java文件）
        modified_java_path = get_modified_java_path(base_path + '/' + repo)#已测试有效
        
        # 获得 mapping 列表
        mapping = run_find_map_test_cases(repo_path, repo, grammar_path, output_dir)
        
        # 初始化结果字典。1：test文件存在，且在列表中；2：test文件存在，但不在列表中 0：test文件不存在
        test_case_results = {file_name: 0 for file_name in modified_java_files}

        # 先把所有 test 找出来并标记对应文件的 testcase
        for java_file in modified_java_files:
            filename = extract_filename(java_file)
            if filename:
                test_case_results[filename] = 1

        # 再遍历 java 修改文件列表
        for java_file in modified_java_files:
            flag = 0
            # 排除已经找到 test 的文件和 test 文件
            if test_case_results[java_file] == 1 or extract_filename(java_file):
                continue
            else:
                # 获得修改文件路径
                java_file_path_list  = [path for path in modified_java_path if path.endswith(java_file)]
                
                if not java_file_path_list:
                    continue
                else:
                    java_file_path = java_file_path_list[0]#理论上只有一个文件路径
                    java_file_path = base_path + '/' + repo + '/' + java_file_path
                   
                method_signatures = extract_method_signatures(java_file_path)  # 获得方法列表
                
                for method_signature in method_signatures:
                    if method_exists(mapping, method_signature) == True:
                        flag = 2  # 至少有一个焦点方法存在对应的测试用例
                        break
                # flag = 0 # 没有找到对应的测试用例
                test_case_results[java_file] = flag

        # 将当前 URL 的 testcase 结果保存到字典中
        testcase_results[url] = test_case_results
        print(f"仓库{repo}的测试结果:{test_case_results}")

    # 更新 CSV 文件中的 testcase 列
    for row in existing_data:
        url = row['url']
        if url in testcase_results:
            row['testcase'] = testcase_results[url]  # 更新 testcase 列

    # 将更新后的数据写回 CSV 文件
    with open(output_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(existing_data)

    print(f"Testcase column has been updated in {output_file}")


if __name__ == '__main__':
    main()
