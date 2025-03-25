import os
import re
import csv
import json
import argparse
import subprocess
import difflib
import shutil
import multiprocessing
import tqdm
import copy
import glob
import fnmatch
from TestParser import TestParser



def analyze_project(repo_path, repo_name, grammar_file, output):
    """
    Analyze a single project using an already cloned repository.
    """
    print("Analyzing " + repo_name + "...")
    repo = {}
    repo["url"] = repo_path
    repo["repo_name"] = repo_name

    # Create output folder
    repo_out = os.path.join(output, str(repo_name))
    os.makedirs(repo_out, exist_ok=True)

    # Run analysis
    language = 'java'
    print("Extracting and mapping tests...")
    tot_mtc = find_map_test_cases(repo_path, grammar_file, language, repo_out, repo)
    (tot_tclass, tot_tc, tot_tclass_fclass, tot_mtc) = tot_mtc

    # Print Stats
    print("---- Results ----")
    print("Test Classes: " + str(tot_tclass))
    print("Mapped Test Classes: " + str(tot_tclass_fclass))
    print("Test Cases: " + str(tot_tc))
    print("Mapped Test Cases: " + str(tot_mtc))

def find_test_classes(root):
    """
    查找包含 @Test 注释的 Java 测试类文件。
    """
    tests = []
    
    # 遍历目录
    for dirpath, _, filenames in os.walk(root):
        for filename in fnmatch.filter(filenames, '*.java'):
            file_path = os.path.join(dirpath, filename)
            with open(file_path, 'r', encoding='utf-8') as file:
                try:
                    # 检查文件中是否包含 @Test
                    if any('@Test' in line for line in file):
                        tests.append(file_path)
                except Exception as e:
                    print("Error reading {file_path}: {e}\n")

    return tests

def find_map_test_cases(root, grammar_file, language, output, repo):
    """
    Finds test cases using @Test annotation
    Maps Test Classes -> Focal Class
    Maps Test Case -> Focal Method
    """
    # Logging
    log_path = os.path.join(output, "log.txt")
    log = open(log_path, "w")

    # Move to folder
    if os.path.exists(root):
        os.chdir(root)
    else:
        return 0, 0, 0, 0

    #获得Test Classes
    try:
        # print("执行grep -l -r @Test --include \*.java命令")
        result = subprocess.check_output(r'grep -l -r @Test --include \*.java', shell=True)
        tests = result.decode('ascii').splitlines()
    except:
        print("命令执行失败")
        log.write("Error during grep" + '\n')
        return 0, 0, 0, 0

    # Java Files
    try:
        # result = subprocess.check_output(['find', '-name', '*.java'])
        
        java = glob.glob(os.path.join(root, '**', '*.java'), recursive=True)
        java = [os.path.relpath(file, root).replace('\\', '/') for file in java]
        java = [j.replace("./", "") for j in java]
    except Exception as e:
        log.write(f"Error during finding Java files: {str(e)}\n")
        return 0, 0, 0, 0


    # Potential Focal Classes
    focals = list(set(java) - set(tests))
    focals = [f for f in focals if not "src/test" in f]
    focals_norm = [f.lower() for f in focals]
    
    log.write("Java Files: " + str(len(java)) + '\n')
    log.write("Test Classes: " + str(len(tests)) + '\n')
    log.write("Potential Focal Classes: " + str(len(focals)) + '\n')
    log.flush()

    # Mapped tests
    mapped_tests = {}

    # Map Test Class -> Focal Class
    log.write("Perfect name matching analysis" + '\n')
    for test in tests:
        tests_norm = test.lower().replace("/src/test/", "/src/main/")
        tests_norm = tests_norm.replace("test", "")
        
        if tests_norm in focals_norm:
            index = focals_norm.index(tests_norm)
            focal = focals[index]
            mapped_tests[test] = focal

    log.write("Perfect Matches Found: " + str(len(mapped_tests)) + '\n')

    # Stats
    tot_tclass = len(tests)
    tot_tclass_fclass = len(mapped_tests)
    tot_tc = 0
    tot_mtc = 0

    # Map Test Case -> Focal Method
    log.write("Mapping test cases" + '\n')
    mtc_list = list()
    parser = TestParser(grammar_file, language)
    for test, focal in mapped_tests.items():
        log.write("----------" + '\n')
        log.write("Test: " + test + '\n')
        log.write("Focal: " + focal + '\n')

        test_cases = parse_test_cases(parser, test)
        focal_methods = parse_potential_focal_methods(parser, focal)
        tot_tc += len(test_cases)

        mtc = match_test_cases(test, focal, test_cases, focal_methods, log)
        
        mtc_size = len(mtc)
        tot_mtc += mtc_size
        if mtc_size > 0:
            mtc_list.append(mtc)

    # Export Mapped Test Cases
    if len(mtc_list) > 0:
        export_mtc(repo, mtc_list, output)

    # Print Stats
    log.write("==============" + '\n')
    log.write("Test Classes: " + str(tot_tclass) + '\n')
    log.write("Mapped Test Classes: " + str(tot_tclass_fclass) + '\n')
    log.write("Test Cases: " + str(tot_tc) + '\n')
    log.write("Mapped Test Cases: " + str(tot_mtc) + '\n')

    log.close()
    return tot_tclass, tot_tc, tot_tclass_fclass, tot_mtc



def parse_test_cases(parser, test_file):
    """
    Parse source file and extracts test cases
    """
    parsed_classes = parser.parse_file(test_file)

    test_cases = list()

    for parsed_class in parsed_classes:
        for method in parsed_class['methods']:
            if method['testcase']:

                #Test Class Info
                test_case_class = dict(parsed_class)
                test_case_class.pop('methods')
                test_case_class.pop('argument_list')
                test_case_class['file'] = test_file
                method['class'] = test_case_class

                test_cases.append(method)
    
    return test_cases


def parse_potential_focal_methods(parser, focal_file):
    """
    Parse source file and extracts potential focal methods (non test cases)
    """
    parsed_classes = parser.parse_file(focal_file)

    potential_focal_methods = list()

    for parsed_class in parsed_classes:
        for parsed_method in parsed_class['methods']:
            method = dict(parsed_method)
            if not method['testcase']: #and not method['constructor']:

                #Class Info
                focal_class = dict(parsed_class)
                focal_class.pop('argument_list')

                focal_class['file'] = focal_file
                method['class'] = focal_class

                potential_focal_methods.append(method)
    
    return potential_focal_methods



def match_test_cases(test_class, focal_class, test_cases, focal_methods, log):
    """
    Map Test Case -> Focal Method
    It relies on two heuristics:
    - Name: Focal Method name is equal to Test Case name, except for "test"
    - Unique Method Call: Test Case invokes a single method call within the Focal Class
    """
    #Mapped Test Cases
    mapped_test_cases = list()

    focals_norm = [f['identifier'].lower() for f in focal_methods]
    for test_case in test_cases:
        test_case_norm = test_case['identifier'].lower().replace("test", "")
        log.write("Test-Case: " + test_case['identifier'] + '\n')

        #Matching Strategies
        if test_case_norm in focals_norm:
            #Name Matching
            index = focals_norm.index(test_case_norm)
            focal = focal_methods[index]
            
            mapped_test_case = {}
            mapped_test_case['test_class'] = test_class
            mapped_test_case['test_case'] = test_case
            mapped_test_case['focal_class'] = focal_class
            mapped_test_case['focal_method'] = focal

            mapped_test_cases.append(mapped_test_case)
            log.write("> Found Focal-Method:" + focal['identifier'] + '\n')
        
        else:
            #Single method invoked that is in the focal class
            invoc_norm = [i.lower() for i in test_case['invocations']]
            overlap_invoc = list(set(invoc_norm).intersection(set(focals_norm)))
            if len(overlap_invoc) == 1:

                index = focals_norm.index(overlap_invoc[0])
                focal = focal_methods[index]

                mapped_test_case = {}
                mapped_test_case['test_class'] = test_class
                mapped_test_case['test_case'] = test_case
                mapped_test_case['focal_class'] = focal_class
                mapped_test_case['focal_method'] = focal

                mapped_test_cases.append(mapped_test_case)
                log.write("> [Single-Invocation] Found Focal-Method:" + focal['identifier'] + '\n')
    
    log.write("+++++++++" + '\n')
    log.write("Test-Cases: " + str(len(test_cases)) + '\n')
    log.write("Focal Methods: " + str(len(focals_norm)) + '\n')
    log.write("Mapped Test Cases: " + str(len(mapped_test_cases)) + '\n')
    return mapped_test_cases


def read_repositories(json_file_path):
    """
    Read the repository java file
    """
    if os.path.isfile(json_file_path):
        data = json.loads(open(json_file_path).read())
    return data


def export_mtc(repo, mtc_list, output):
    """
    Export a JSON file representing the Mapped Test Case (mtc)
    It contains info on the Test and Focal Class, and Test and Focal method
    """
    mtc_id = 0
    all_mtcs = []  # 创建一个列表来存储所有的mtc对象

    for mtc_file in mtc_list:
        for mtc_p in mtc_file:
            mtc = copy.deepcopy(mtc_p)
            mtc['test_class'] = mtc['test_case'].pop('class')
            mtc['focal_class'] = mtc['focal_method'].pop('class')
            mtc['repository'] = repo

            # Clean Focal Class data
            for fmethod in mtc['focal_class']['methods']:
                fmethod.pop('body')
                fmethod.pop('class')
                fmethod.pop('invocations')
            
            method = mtc['focal_method']['signature']
            # 去掉\n和空格
            method = re.sub(r',\n\s*', ', ', method)
            method = re.sub(r'\n\s*', '', method)
            all_mtcs.append(method)  # 将mtc对象添加到列表中
            mtc_id += 1

    mtc_file = str(repo["repo_name"]) + "_signature.json"  # 使用repo名称作为文件名
    json_path = os.path.join(output, mtc_file)  # 构建完整的文件路径

    with open(json_path, 'w') as f:  # 打开文件准备写入
        json.dump(all_mtcs, f, indent=4)  # 将所有mtc对象写入同一个JSON文件

def export(data, out):
    """
    Exports data as json file
    """
    with open(out, "w") as text_file:
        data_json = json.dumps(data)
        text_file.write(data_json)    



def parse_args():
    """
    Parse the args passed from the command line
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo_path", 
        type=str, 
        default="repo_path",
        help="GitHub URL of the repo to analyze",
    )
    parser.add_argument(
        "--repo_name",
        type=str,
        default="unknown-repo-name",
        help="repo-name used to refer to the repo",
    )
    parser.add_argument(
        "--grammar",
        type=str,
        default="build/my-languages.so'", # 默认.so文件路径
        help="Filepath of the tree-sitter grammar",
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="E:/dachaung/tmp/output/", # 默认输出路径
        help="Path to the output folder",
    )

    return vars(parser.parse_args())


def main():
    args = parse_args()
    repo_git = args['repo_path']
    repo_name = args['repo_name']
    grammar_file = args['grammar']
    output = args['output']
    local_repo_path = os.path.join(repo_git)  # 确保传入的是本地路径
    analyze_project(local_repo_path, repo_name, grammar_file, output)

if __name__ == '__main__':
    main()