import requests
import time
import csv
import re
import os 
import subprocess #用来执行powershell命令并把输出重定向
from concurrent.futures import ThreadPoolExecutor #多线程池
access_token = "" 

def clone_repository(url, output_dir):
    try:
        # 从URL中提取仓库名
        repository_name = re.search(r'/([^/]+/[^/]+)/commit/', url).group(1)
        repo = re.search(r'[^/]+$', repository_name).group()
        # 构造仓库地址
        repository_url = f"https://{access_token}@github.com/{repository_name}"
        api_url = f"https://api.github.com/repos/{repository_name}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.get(api_url, headers=headers)

        if response.status_code == 200:
            # url有效
            # 检查目录下是否已经存在该仓库
            if os.path.exists(os.path.join(output_dir, repo)):
                #print(f"Repository {repo} already exists, skipping...")
                return
            # 在指定目录下执行git clone命令
            subprocess.run(["git", "clone", repository_url])
            print(f"Successfully cloned {url}")
            print(repository_name)
            # 延迟一段时间，避免频繁请求
            time.sleep(2)  # 可根据需要调整延迟时间
            return True
        else:
        #response.status_code == 404:
            return False

    except Exception as e:
        print(f"Error cloning {url}: {e}")

def main():
    base_path1='../repo' #存放所有仓库的地方，一般是硬盘的目录
    output_file = "dataset/output.csv"#输出文件
    input_csv = "dataset/veracode_fliter.csv"#输入文件k
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

if __name__ == "__main__":
    main()