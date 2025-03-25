def main():
    base_path1='E:\\dachng\\github_clone' #存放所有仓库的地方，一般是硬盘的目录
    output_file = "E:\\dachaung\\output.csv"#输出文件
    input_csv = "E:\\dachaung\\veracode_fliter.csv"#输入文件k
    # 表头
    header = ['index', 'cwe key word', 'matched key word', 'file', 'func', 'hunk', 'function_name', 'note', 'repo', 'branch', 'url','testcase']
    urls = []
    # 获取csv文件里的urls
    max_workers=5
    with open(input_csv) as csvfile:
        reader = csv.reader(csvfile)
        urls = [row[3] for row in reader]
    # 克隆仓库
    os.chdir(base_path1)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for url in urls:
            executor.submit(clone_repository,url,base_path1)
        


    print(f"Data has been written to {output_file}")