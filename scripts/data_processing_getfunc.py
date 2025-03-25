import subprocess
from tree_sitter import Language, Parser
import re
import os
import warnings
import json
import csv
import data_processing as dp
import extract as ex
warnings.simplefilter('ignore', FutureWarning)

JAVA_LANGUAGE = Language('build/my-languages.so', 'java')
parser = Parser()
parser.set_language(JAVA_LANGUAGE)

# 已测试有效 
def run_command(command):
    """运行shell命令并返回输出"""
    
    # 使用列表形式传递命令，避免shell解释问题
    args = command.split()
    result = subprocess.run(args, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error occurred: {result.stderr}")
    
    return result.stdout


def get_file_paths(repo_path, commit_hash):
    """
    获取指定提交中所有修改的文件路径。

    :param commit_hash: 提交哈希值
    ：param repo_path: 本地仓库路径
    :return: 修改的文件路径列表
    """
    
    command = f'git diff --name-only {commit_hash}^..{commit_hash}'
    # repo_path = "E:/dachuang2024/tmp/tmp/spring-framework"
    os.chdir(repo_path)
    file_paths = run_command(command)

    return file_paths.splitlines()

# 已测试有效
def get_modified_functions(commit_hash,file_path,repo_path):
    """
        提取diff_out中某个修改文件的所有修改函数名称。

        参数:
            commit_hash: 提交哈希值。
            file_path: 修改文件的路径。

        返回:
            list: 该diff的修改函数名称列表(函数名+参数)。
        """
    return ex.get_modified_methods(commit_hash,file_path,repo_path)

# 已测试有效
def extract_functions(content):
    """
    解析 Java 文件内容并提取所有方法的完整定义（键：方法签名（名+参数）；值：包括访问修饰符、返回类型、方法名、参数列表、异常声明和方法体）。
    使用tree-sitter解析
    :param content: Java 文件内容字符串
    :return: 包含方法名称到完整方法定义的字典
    """
    
    functions = {}
    tree = parser.parse(bytes(content, 'utf8'))  # 解析文件内容为语法树
    
    method_query = """
    (method_declaration
      type: (_) @return_type
      name: (identifier) @method_name
      parameters: (formal_parameters) @param_list
      body: (block) @method_body
    )
    """
    query = JAVA_LANGUAGE.query(method_query)
    captures = query.captures(tree.root_node)

    current_method = {"name": None, "body": None, "params": [], "return_type": None, "exceptions": []}
    for capture in captures:
        node, capture_name = capture
        
        if capture_name == 'method_name':
            current_method['name'] = content[node.start_byte:node.end_byte]
            
        elif capture_name == 'method_body':
            current_method['body'] = content[node.start_byte:node.end_byte]
            
        elif capture_name == 'return_type':
            current_method['return_type'] = content[node.start_byte:node.end_byte]
            
        elif capture_name == 'param_list':
            current_method['params'] = []
            param_list_node = node
            for i in range(param_list_node.named_child_count):
                param_node = param_list_node.named_child(i)
                param_type_node = param_node.child_by_field_name('type')
                param_name_node = param_node.child_by_field_name('name')
                
                if param_type_node is not None and param_name_node is not None:
                    param_type = content[param_type_node.start_byte:param_type_node.end_byte]
                    param_name = content[param_name_node.start_byte:param_name_node.end_byte]
                    current_method['params'].append(f"{param_type} {param_name}")
        
        # 当我们得到了一个方法的所有必要信息后，生成其完整定义并存储
        if all([current_method['name'], current_method['body'], current_method['return_type']]):
            # 查找异常声明
            method_def_start = content.find(current_method['return_type'])
            method_def_end = node.end_point[0] + 1  # 假设方法定义结束在方法体开始之前的一行
            method_def_str = content[method_def_start:method_def_end]
            exceptions = re.findall(r'throws\s+([\w\s,]+)', method_def_str)
            if exceptions:
                current_method['exceptions'] = [ex.strip() for ex in exceptions[0].split(',')]

            params_str = ", ".join(current_method['params']) if current_method['params'] else ""
            exceptions_str = " throws " + ", ".join(current_method['exceptions']) if current_method['exceptions'] else ""
            signature = f"{current_method['name']}({params_str})"
            full_function = f"{current_method['return_type']} {current_method['name']}({params_str}){exceptions_str}{current_method['body']}"
            functions[signature] = full_function
            # signature = f"{current_method['return_type']} {current_method['name']}({params_str}){exceptions_str}"
            # full_function = f"{signature}{current_method['body']}"
            # functions[current_method['name']] = full_function
            
            # 重置 current_method 以便处理下一个方法
            current_method = {"name": None, "body": None, "params": [], "return_type": None, "exceptions": []}
    
    return functions

def main_process(commit_hash,repo_path,index,output_file_path):
    """
    主函数：从每个commit里提取出修改函数和未修改函数。
    
    :param commit_hash: 提交哈希值
    :param repo_path: 在本地的代码库路径
    :param index: 编号，用于记录函数的编号
    """
    file_paths = get_file_paths(repo_path,commit_hash)  # 获取所有修改文件路径(相对于其所在仓库)
    
    

    # 逐个处理文件
    for file_path in file_paths:
        print(f"Processing file: {file_path}")
        content = ex.get_file_content(commit_hash, file_path,repo_path)  # 获取文件内容
        parent_content = ex.get_file_content(f'{commit_hash}^', file_path,repo_path)  # 获取父提交版本的文件内容
        modified_function_names = get_modified_functions(commit_hash, file_path, repo_path)  # 获取被修改的函数名称(字典，键为函数名，值为修改的行号列表)
        parent_functions = extract_functions(parent_content)  # 提取父提交中的所有函数定义

        # 将修改的函数和未修改的函数写入文件

        #切换到脚本所在目录
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        os.chdir(script_dir)

        # 打开文件以写入模式
        with open(output_file_path, 'w', encoding='utf-8') as file:
            for func_name, func_body in parent_functions.items():
                index+=1
                #print("文件里获得的函数名", func_name)
                # 判断函数是否被修改
                if func_name in modified_function_names:
                    is_modified = 1 
                else:
                    is_modified = 0

                # 创建包含函数定义和修改标志的字典
                function_info = {
                    'idx': index,
                    'func': func_body,
                    'target': is_modified,
                    'flaw_line_index': modified_function_names[func_name] if is_modified else None
                }
                # print(is_modified)
                # 将字典转换为JSON字符串并写入文件
                file.write(json.dumps(function_info) + '\n')
        



def main(input_file_path, output_file_path, base_path):

    with open(input_file_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        urls = [row[3] for row in reader]

    index = 0
    # 处理每个url
    for i,url in enumerate(urls, start=1):
        match = re.search(r'/([^/]+/[^/]+)/commit/', url)
        if not match:
            print(f"URL {url} does not match the expected pattern.")
            continue

        repository_name = match.group(1) #user/repo,如：hadoop/hadoop-common
        repo = re.search(r'[^/]+$', repository_name).group() #repo,如：hadoop-common
        commit_hash = url.split('/')[-1]
        
        repo_path = os.path.join(base_path, repo) #得到仓库的本地克隆目录
        main_process(commit_hash,repo_path,index,output_file_path)

if __name__ == '__main__':
    # 思路：对每个url，读取其commit_hash，以及仓库名repo
    ## 调用main函数可以得到修改的函数和未修改的函数（针对diff_out里出现的文件（即修改过的文件）,可以得到一个修改文件列表modified_file_path；结果写进jsonl文件里）
    ### 疑问：一个diff中多个文件的函数是否可能重名，如果重名需要以每个文件为单位读取diffout，而不是整个diff
    # 对于仓库中的其他未修改文件(不在modified_file_path里的），遍历仓库获得这些文件的file_path，直接调用extract_functions函数，将结果写进jsonl文件里
    
    # ！！！！！！换一个思路：找到所有修改块（根据@@里的行号信息），然后到原文件中寻找修改块所在函数。  已解决
    input_csv = r'dataset\input.csv' #输入文件                                         
    output_file_path = r'dataset\output_getfunc_test.jsonl' #输出文件
    base_path='E:\\dachuang2024\\tmp\\tmp' #存放所有仓库的地方
    main(input_csv, output_file_path,base_path)
    print("结果已写入文件{output_file_path}.")                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  

    
    # commit_hash = '957c56dbe5b1490490c09ddfbca9a4204c7c9d00'  # 替换为你的提交哈希值
    # file_path = 'hadoop-hdfs-project/hadoop-hdfs/src/main_process/java/org/apache/hadoop/hdfs/server/datanode/DataNode.java'   # 替换为目标Java文件路径
    # main_process(commit_hash, file_path)