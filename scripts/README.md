# 处理git diff命令获得的diff_out内容并统计相关数据
## 概述

- 统计diffout中涉及的修改块数hunk， 所有修改块所在函数func的集合，涉及的java文件数 file。脚本`data_processing.py`
- 判断commit中的Java文件是否存在对应的测试文件。脚本`data_processing_testcase.py`
	- 输出格式`{file1:1,file2:2,file3:0}`  
		- 1：修改文件列表中有该文件对应的test文件
		- 2：修改文件列表中没有该文件对应的test文件，但是仓库中有
		- 0：不存在该文件对应的修改文件
	- 代码思路：
		- 对于每个仓库， 从diffout中获取修改文件列表
		1. 读取修改文件列表，如果是test文件，说明其对应的修改文件找到test，testcase=1
		2. 对于列表中没有对应test的java文件：
			- 获得仓库中所有测试用例和焦点方法的mapping，提取出焦点方法得到一个列表methodlist。（调用脚本find_map_test_case）
			- 获取该文件中所有焦点方法（tree-sitter），在methodlist中寻找是否存在该方法。存在，testcase=2.
		3. 以上两种方法都没找到，testcase=0
- 提取每个commit涉及的修改方法主体，以及涉及的修改文件中未改动的方法主体，并统计修改行号。脚本'data_processing_get_func.py'

## 文件解释

- `data_processing_testcase.py` 扫描本地仓库，从已有的diff.txt文件中获取diffout内容，并判断每个修改文件是否有对应的测试文件。输出到dataset/output.csv的testcase列。
- `find_map_test_case.py` 用于在某仓库中获得所有方法和对应测试用例的映射，提取map中的焦点方法形成一个列表，并输出到该仓库下的一个json文件里。由data_processing_testcase.py调用。
- `TestParser.py` 由find_map_test_case.py调用。
- `data_processing.py` 统计file/hunk/func等数据，输出到dataset/output.csv
- `data_processing_get_func.py` 提取修改和未修改方法主体，以及涉及的修改行号。输出到dataset/output_getfunc_test.jsonl
- `extract.py` 实现提取方法主体的功能，由data_processing_get_func.py调用。
- `clone_repo.py` 克隆仓库。
- build文件夹：放置tree-sitter Java 语法文件

## 运行准备

- 安装0.21.3版本的tree-sitter，克隆java语言的仓库tree-sitter-java
```
	pip install tree_sitter==0.21.3
	git clone https://github.com/tree-sitter/tree-sitter-java
```
- 生成.so文件，运行下面的代码
```python
import tree_sitter
from tree_sitter import Language

Language.build_library(
  # so文件保存位置
  'build/my-languages.so',

  # git clone的tree-sitter-java仓库路径
  [
    'tree-sitter-java'
  ]
)
```

-  需要已经克隆到本地的仓库，每个仓库下有一个diff.txt文件。运行clone_repo.py会进行克隆。
```bash
python clone_repo.py

python data_processing.py #统计file/hunk/func等数据
python data_processing_testcase.py #判断每个修改文件是否有对应的测试文件

python data_processing_get_func.py #提取修改和未修改方法主体，以及涉及的修改行号
```

