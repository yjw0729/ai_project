
# PYTEST简单教程

## pytest自动检索
** pytest框架会自动检索项目下的目录（venv  / .开头的目录除外）
自动识别到test_  开头或者   _test结尾的py文件
测试类需要以 Test开头，并且类中没有__init__方法
测试案例可以编写为方法或者函数，要以test_开头

## pytest中常用的夹具和标记

### 夹具

- 编写到conftest.py 文件中，在运行时会自动识别，并不会当作测试文件执行，主要存储子目录下共享的fixture
- 夹具的功能
  #### 1、创建数据
  #### 2、环境搭建
  #### 3、资源共享（数据库连接、浏览器等）
  #### 4、清理回收（删除临时文件、数据库事务回滚）
  #### 1、在用例执行时，进行前置与后置操作，
  #### 2、在用例执行时，进行接口之间的信息传递
  #### 3、夹具之间可配置执行顺序
  #### 4、控制夹具的作用域，夹具的自动使用

### 标记

** 使用@pytest.mark.xxx 装饰器进行标记 **
- #### 自定义标记
  ##### 1、需要先在配置文件中进行注册
  ##### 2、在执行时主要是用来筛选，pytest -m 
- 框架内标记
  #### 1、无需注册，可以直接引用
  ##### 2、根据引用的不同有不同的功能
  ```
    **skip** - 跳过执行该测试用例
        '@pytest.mark.skip(reason="跳过原因")
         def test_this_will_be_skipped():
            assert 1 == 2
  ```
  ```
    **skipif** - 如果条件为真，则跳过测试
        '@pytest.mark.skipif(sys.version_info < (3, 6), reason="需要Python3.6或更高版本")
         def test_this_will_be_skipped_if_python_version_less_than_3_6():
                assert 1 == 1'
  ```
  ```
    **xfail** - 预期该测试会失败，如果测试失败，结果标记为XFAIL（预期失败）；如果测试通过，则标记为XPASS（意外通过）
        '@pytest.mark.xfail
         def test_this_will_xfail():
            assert False'
  ```
  ```
    **parametrize** - 参数化测试，为测试函数提供多组参数，每组参数运行一次测试
        '@pytest.mark.parametrize("input, expected", [(1, 2), (2, 4), (3, 6)])
         def test_multiply_by_two(input, expected):
            assert input * 2 == expected'
  ```
  ```
    **usefixtures** - 在测试类或模块级别使用指定的fixture。注意，这个标记不能用于测试函数，而是用于类或模块
        '@pytest.mark.usefixtures("cleandir")
         class TestDirectoryFixture:
            def test_something(self):
            # 这个测试会在cleandir fixture提供的干净目录中运行
            pass'
  ```
  ```
    **filterwarnings** - 过滤警告，可以标记测试以忽略特定警告或对警告进行处理
        '@pytest.mark.filterwarnings("ignore:deprecated")
         def test_that_emits_deprecation_warning():
            # 这里可能会产生过时警告，但会被忽略
                pass'
  ```
## 测试案例编写规则

### yaml文件

- 测试案例使用yaml文件进行编写，一个接口信息编写为一个yaml文件,一个yaml文件是一个测试套件test_suit，里面可以包含多个测试场景的test_case

** 如果指定了test_suit，那么自动执行测试套件中的所有test_case
