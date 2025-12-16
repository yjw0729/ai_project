from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
import time
import pymysql


class WebAutomation:

    def __init__(self, url):
        self.service = Service('D:/test-project/chromedriver-win64/chromedriver.exe')   # 替换为自己的路径
        self.driver = webdriver.Chrome(service=self.service)  # 或根据需要选择不同的浏览器
        self.driver.get(url)

    def login(self, username_xpath, password_xpath, confirm_xpath, username, password):
        """
        登录
        :param username_xpath: 用户名输入框的XPATH
        :param password_xpath: 密码输入框的XPATH
        :param confirm_xpath: 登录按钮的XPATH
        """
        self.enter_text(username_xpath, username)
        self.enter_text(password_xpath, password)
        self.click_element(confirm_xpath)
        time.sleep(1)

    def switch_to_iframe(self, iframe_xpath):
        """切换到指定的 iframe"""
        WebDriverWait(self.driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.XPATH, iframe_xpath)))
        time.sleep(1)

    def scroll_to_element(self, element_xpath):
        """将指定元素滚动到可见区域"""
        element = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, element_xpath)))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        self.driver.execute_script("window.scrollBy(0, -200);")  # 微调位置
        time.sleep(1)
        return element

    def enter_text(self, input_xpath, value):
        """
        在指定的输入框中输入文本（改为先判断是否为空，不为空才赋值）
        :param element_xpath: 文本框的XPATH
        :param value: 要输入的值
        """
        input_box = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, input_xpath)))
        # input_box.clear()  # 清空输入框
        ori_value = input_box.get_attribute('value')
        if ori_value is None or len(ori_value) == 0:
            input_box.send_keys(value)
            time.sleep(1)

    def click_element(self, button_xpath):
        """点击指定的元素"""
        button = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
        button.click()
        time.sleep(1)
        return button

    def select_value(self, element_xpath, value):
        """
        选择select标签中的值（给的页面里面没有原生select控件，没有测试）
        :param element_xpath: select标签的XPATH
        :param value: 要选择的值
        """
        selector = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, element_xpath)))
        select_element = Select(selector)
        # 定位元素(这里使用文字定位)
        select_element.select_by_visible_text(value)
        time.sleep(1)

    def get_element_by_xpath(self, element_xpath):
        self.driver.find_element(By.XPATH, element_xpath)
        time.sleep(1)

    def select_value_by_visible_text_scroll(self, input_xpath, list_xpath, visible_text, is_multiple,
                                            list_css='.tas-cb-select-dropdown .rc-virtual-list .rc-virtual-list-holder',
                                            option_css='.rc-virtual-list-holder-inner .tas-cb-select-item-option'):
        """
        根据可见文本选择自定义下拉框中的值-支持滑动（先判断是否为空）--点击弹出下拉框
        :param input_xpath:需要点击的文本框的XPATH
        :param list_xpath:下拉框处有id的那个标签对应的xpath；
        :param visible_text：需要选择的文本列表；
        :param is_multiple：这个下拉框是单选传False，多选传True
        :param list_css：list_xpath对应标签的兄弟节点的子节点，可以操作滑动的那个标签对应的css；
        :param option_css:list_css下title值为列表中值的那个div对应的css；
        注：一般情况下，后两个参数可以不传，直接使用默认值
        """
        # 获取文本框
        input = self.driver.find_element(By.XPATH, input_xpath)

        # 获取父元素，用于查询是否已选择内容
        if is_multiple:
            # 多选
            parent_element = input.find_element(By.XPATH, '../../..')
            select_elements = parent_element.find_elements(By.CSS_SELECTOR, '.tas-cb-select-selection-overflow-item')
            if len(select_elements) > 1:
                # 如果已有内容直接返回
                return
            parent_element.click()
        else:
            # 单选
            parent_element = input.find_element(By.XPATH, '../..')
            try:
                options = parent_element.find_elements(By.CSS_SELECTOR, '.tas-cb-select-selection-item')
                if len(options) == 0 or options[0].text == '':
                    parent_element.click()
                else:
                    return
            except:
                # 抛异常证明不存在
                parent_element.click()
        time.sleep(1)
        # 等待下拉框加载
        org_text = self.driver.find_element(By.XPATH, list_xpath)

        # 获取父级
        org_text_parent = org_text.find_element(By.XPATH, '..')
        max_scrolls = 30  # 设置最大滚动次数，防止因代码出问题一直循环
        scroll_count = 0
        found = 0  # 标记是否找到目标值
        # 获取下拉框元素，并不是随便一个包在外层的div都可以，需要尝试哪一层是可以滚动的，定位到可以滚动的div才可以
        dropdown = org_text_parent.find_element(By.CSS_SELECTOR, list_css)
        num = len(visible_text)
        # 滚动并选择目标值
        while scroll_count < max_scrolls:
            options = dropdown.find_elements(By.CSS_SELECTOR, option_css)
            for option in options:
                # print(option.get_attribute("title"))
                for text in visible_text:
                    if option.get_attribute("title") == text:  # 替换为你的目标值
                        option.click()  # 点击目标值
                        found += 1  # 更新找到标记
                        # sleep(1)
                        if found == num:
                            break
                if found == num:
                    break
            if found == num:
                break
            # 向下滚动
            self.driver.execute_script("arguments[0].scrollTop += 160", dropdown)
            time.sleep(1)  # 等待新内容加载
            scroll_count += 1  # 增加滚动计数
        if not found:
            print("目标值未找到，请检查选项是否存在或下拉框是否加载完整。")
            print(scroll_count)
        # 如果是多个选项，则需要再次点击文本框
        if is_multiple:
            parent_element.click()

    def select_date(self, target_date, element_xpath, is_single):
        """
        :param target_date:要选择的时间
        :param element_xpath：弹出的时间控件的XPATH（找到对应的id，再copy XPATH）
        :param is_single: 是否为单个日期，是为True, 不是为False
        """
        target_date_arr = target_date.split('-')
        target_year = int(target_date_arr[0])
        target_month = '{}-{}'.format(target_date_arr[0], target_date_arr[1])
        # 标记是否找到
        flag = False
        # 获取日期控件
        date_selector = self.driver.find_element(By.XPATH, element_xpath)
        # 点击年份按钮
        btn = date_selector.find_element(By.CSS_SELECTOR, '.tas-cb-picker-header-view .tas-cb-picker-year-btn')
        btn.click()

        while not flag:
            # 定位到年份表格
            table = WebDriverWait(date_selector, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.tas-cb-picker-content')))

            time.sleep(1)
            rows = table.find_elements(By.TAG_NAME, 'tr')
            first_cell = rows[0].find_element(By.TAG_NAME, 'td')
            # 左上角年份值
            title_value = int(first_cell.get_attribute('title'))
            print('左上角年份值：{}, 想要选择的年份值:{}'.format(title_value, target_year))
            if title_value <= target_year and target_year <= title_value + 11:
                for row in rows:
                    # 获取所有 td
                    cells = row.find_elements(By.TAG_NAME, 'td')
                    for cell in cells:
                        value = cell.get_attribute('title')
                        if str(target_year) == value:
                            cell.click()
                            flag = True
                            break
                    if flag:
                        break
            elif title_value + 11 < target_year:
                print('点击按钮展示下一页年份数据')
                next_page = date_selector.find_element(By.CSS_SELECTOR, '.tas-cb-picker-super-next-icon')
                next_page.click()
            else:
                print('点击按钮展示上一页年份数据')
                prev = date_selector.find_element(By.CSS_SELECTOR, '.tas-cb-picker-super-prev-icon')
                prev.click()

        if is_single:
            # 如果是单个日期控件，选择月份需要先点击月份按钮
            month_btn = WebDriverWait(date_selector, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.tas-cb-picker-month-btn')))
            month_btn.click()

        # 选择月份
        month_table = WebDriverWait(date_selector, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.tas-cb-picker-content')))
        month_cells = month_table.find_elements(By.TAG_NAME, 'td')
        for cell in month_cells:
            value = cell.get_attribute('title')
            if value == target_month:
                cell.click()
                break
        time.sleep(1)
        # 选择日期
        if is_single:
            # 如果是单个日期控件
            day_table = WebDriverWait(date_selector, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.tas-cb-picker-content')))
            day_cells = day_table.find_elements(By.TAG_NAME, 'td')
        else:
            WebDriverWait(date_selector, 10).until(
                EC.visibility_of_element_located((By.XPATH, '//*[contains(@class, "tas-cb-picker-panels")]')))
            tables = date_selector.find_elements(By.CSS_SELECTOR, '.tas-cb-picker-panel')
            day_cells = tables[0].find_elements(By.TAG_NAME, 'td')
        for cell in day_cells:
            value = cell.get_attribute('title')
            if value == target_date:
                cell.click()
                break
        time.sleep(1)

    def select_hover_list_by_text(self, hover_xpath, list_css, text):
        """
        通过鼠标悬停的方式弹出下拉框，并根据文字选择元素进行点击
        :param hover_xpath: 鼠标悬停处的XPATH
        :param list_css: 弹出的下拉框对应的css（尽量选可以和别的下拉框不一样的那个css）
        :param text: 要点击的内容
        :return:
        """
        # hover_element = WebDriverWait(self.driver, 10).until(
        #     EC.visibility_of_element_located((By.XPATH, hover_xpath))  # 根据实际情况修改选择器
        # )
        # 找到悬停的元素
        hover_element = self.driver.find_element(By.XPATH, hover_xpath)  # 根据实际情况修改选择器

        # 创建 ActionChains 对象
        actions = ActionChains(self.driver)

        # 鼠标悬停
        actions.move_to_element(hover_element).perform()

        # 等待下拉框出现
        dropdown_element = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, list_css))  # 根据实际情况修改选择器
        )

        elements = dropdown_element.find_elements(By.TAG_NAME, 'li')
        # 遍历每个li元素
        for li in elements:
            # 获取li下的span元素
            span = li.find_element(By.TAG_NAME, 'span')

            # 判断span的内容
            if span.text == text:  # 替换为你要比较的内容
                # 点击li元素
                ActionChains(self.driver).move_to_element(li).click().perform()
                print(f"Clicked on: {span.text}")
                break  # 点击后可选择是否继续查找或终止

    def select_table(self, table_css, value_index, target_value, operation_index, click_element):
        """
        获取表格元素，根据某一列的值进行选择，可选多行（最后一列的index可以传-1）
        :param table_css: 表格的css
        :param value_index: 传入的值在第几列（从0开始）
        :param target_value: 查找的文字列表
        :param operation_index: 需要操作的列
        :param click_element: 要点击的标签
        :return:
        """
        # 获取表格元素，根据某一列的值进行选择，可选多行
        table = self.driver.find_element(By.CSS_SELECTOR, table_css)
        # 获取表格中所有行
        trs = table.find_elements(By.TAG_NAME, 'tr')
        num = len(target_value)
        count = 0
        # 对tr进行遍历，获取每个tr中的所有td，根据传入的位置和值点击前面的多选框
        for tr in trs:
            tds = tr.find_elements(By.TAG_NAME, 'td')
            # 获取需要根据值进行选择的那列数据
            target = tds[value_index]
            for v in target_value:
                print(target.find_element(By.TAG_NAME, 'div').text)
                if target.find_element(By.TAG_NAME, 'div').text == v:
                    tds[operation_index].find_element(By.TAG_NAME, click_element).click()
                    count += 1
                    break
            if num == count:
                break

    def collection_management_table(self):
        """
        结行国际-收款管理-点击关联订单
        :param table_css: 表格css
        :return amount: 返回订单金额
        """
        # 获取表格元素，根据某一列的值进行选择，可选多行
        # table = self.driver.find_element(By.CSS_SELECTOR, '.ca-table-tbody')
        table = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.ca-table-tbody')))
        # 获取表格第一行
        tr = table.find_elements(By.TAG_NAME, 'tr')[0]
        tds = tr.find_elements(By.TAG_NAME, 'td')
        # 获取第4列的订单金额
        amount = tds[3].find_element(By.CSS_SELECTOR, '.style_amount__yfHjU').text
        # 点击关联订单
        tds[-1].find_element(By.TAG_NAME, 'a').click()
        return float(amount)

    def associated_order(self, amount):
        """
        结行国际-收款管理-点击关联订单-勾选订单
        :param amount: 订单金额
        :return:
        """
        # 获取表格元素，根据某一列的值进行选择，可选多行
        table = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.ca-table-tbody')))

        trs = table.find_elements(By.TAG_NAME, 'tr')
        if len(trs) >= 3:
            amount1 = amount // 2
            # 如果有多个，选择前两个
            tr1 = trs[1]
            tds = tr1.find_elements(By.TAG_NAME, 'td')
            tds[0].find_element(By.CSS_SELECTOR, '.ca-checkbox-input').click()
            amount_td1 = tds[-1].find_element(By.TAG_NAME, 'input')
            # amount_td1.clear()
            for i in range(len(amount_td1.get_attribute('value'))):
                amount_td1.send_keys(Keys.BACK_SPACE)
            amount_td1.send_keys(amount1)
            tr2 = trs[2]
            tds = tr2.find_elements(By.TAG_NAME, 'td')
            tds[0].find_element(By.TAG_NAME, 'input').click()
        else:
            tr1 = trs[1]
            tds = tr1.find_elements(By.TAG_NAME, 'td')
            tds[0].find_element(By.TAG_NAME, 'input').click()

    def mysql_search(self, query):
        # 连接到 MySQL 数据库
        """
        mysql单个字段查询
        :param query: SQL语句
        :return: 返回单个结果
        """
        try:
            connection = pymysql.connect(
                host='22.50.6.9',  # 通常是 'localhost' 或 IP 地址
                user='opts_test',  # MySQL 用户名
                password='opts_test',  # MySQL 密码
                database='opts'  # 要连接的数据库名称
            )

            # 创建游标对象
            cursor = connection.cursor()

            # 执行查询
            cursor.execute(query)

            # 获取查询结果
            result = cursor.fetchone()  # 只获取一条记录
            return result

        except pymysql.MySQLError as err:
            print(f"Error: {err}")

        finally:
            # 关闭游标和连接
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def select_dropdown_option_by_text(self, tag_xpath, dropdown_xpath, option_text):
        """
        左侧菜单栏，点击菜单后再点击下拉选项中的菜单
        :param tag_xpath: 一级菜单XPATH
        :param dropdown_xpath: 包含下拉框的XPATH
        :param option_text: 最终要选择的菜单
        :return:
        """
        # 点击一级菜单
        self.click_element(tag_xpath)
        # 获取显示出的下拉列表
        dropdown = self.driver.find_element(By.XPATH, dropdown_xpath)
        # 获取下拉列表中所有选项
        # options = dropdown.find_elements(By.TAG_NAME, 'li')
        options = dropdown.find_elements(By.TAG_NAME, 'span')
        for option in options:
            # 或得li里面的span内容
            # text = option.find_element(By.TAG_NAME, 'span').text
            text = option.text
            if text == option_text:
                option.click()
                break

    def upload_picture(self, number):
        '''在页面中上传图片信息:param picture_xpath: :return: '''
        image_path = "D:/pythonProject/new_front_test/picture/北京结慧科技有限公司执照副本.jpg"
        time.sleep(2)
        for i in range(number):
            upload_input_elements = self.driver.find_elements(By.XPATH, "//input[@type='file']")
            upload_input_element = upload_input_elements[i]
            upload_input_element.send_keys(image_path)
        time.sleep(3)

    def upload_video(self):
        '''在页面中上传图片信息:param picture_xpath: :return: '''
        video_path = "D:/pythonProject/new_front_test/picture/一级商户上传视频.mp4"
        upload_video_element = self.driver.find_element(By.XPATH, "//input[@accept='video/*']")
        upload_video_element.send_keys(video_path)

    def login_yanzhengma(self, username_xpath, password_xpath, confirm_xpath, username, password, picture, number):
        """
        重写登录方法
        :param username_xpath: 用户名输入框的XPATH
        :param password_xpath: 密码输入框的XPATH
        :param confirm_xpath: 登录按钮的XPATH
        """
        self.enter_text(username_xpath, username)
        self.enter_text(password_xpath, password)
        if picture == '' and number == '':
            self.driver.find_element(By.ID, "captchaCode").send_keys("0")
            self.driver.find_element(By.ID, "phoneCode").click()
            self.driver.find_element(By.ID, "phoneCode").send_keys("0000")
        else:
            self.driver.find_element(By.ID, "captchaCode").send_keys(picture)
            self.driver.find_element(By.ID, "phoneCode").click()
            self.driver.find_element(By.ID, "phoneCode").send_keys(number)
        self.click_element(confirm_xpath)
        print("登录成功")
        time.sleep(1)

    def select_cascade_box(self, css, text_list, index):
        """
        级联下拉框选取
        :param css: 包含下拉框的css
        :param text_list: 需要选择的内容（按顺序输入）
        :return:
        """
        # 获取下拉框
        drop_down_box = self.driver.find_elements(By.CSS_SELECTOR, '.ant-cascader-menus')
        drop_down_box = drop_down_box[index]
        for i, text in enumerate(text_list):
            # 按顺序获取下拉框
            ul = drop_down_box.find_elements(By.TAG_NAME, 'ul')[i]
            options = ul.find_elements(By.TAG_NAME, 'li')
            for option in options:
                if option.get_attribute('title') == text:
                    option.click()
                    # 因为需要选择完上一级，才会加载出下一级，需要显示等待加载完成
                    time.sleep(2)
                    break

    def check_xialakuang(self, xpath):
        '''
        选择下拉框内信息
        :param id:
        :return:
        '''
        self.click_element(xpath)
        # 使用键盘操作来选择下拉框选项
        action = ActionChains(self.driver)
        action.send_keys(Keys.ARROW_DOWN).perform()  # 按下箭头往下键
        action.send_keys(Keys.ENTER).perform()

    def check_many_xialakuang(self, index):
        drop_down_box = self.driver.find_elements(By.CSS_SELECTOR, '.ant-select-selection-search-input')
        drop_down_box = drop_down_box[index]
        drop_down_box.click()

    def select_date(self, target_date, element_xpath, is_single):
        """
        :param target_date:要选择的时间
        :param element_xpath：弹出的时间控件的XPATH（找到对应的id，再copy XPATH）
        :param is_single: 是否为单个日期，是为True, 不是为False
        """
        target_date_arr = target_date.split('-')
        target_year = int(target_date_arr[0])
        target_month = '{}-{}'.format(target_date_arr[0], target_date_arr[1])
        # 标记是否找到
        flag = False
        # 获取日期控件
        date_selector = self.driver.find_element(By.XPATH, element_xpath)
        # 点击年份按钮
        btn = date_selector.find_element(By.CSS_SELECTOR, '.ant-picker-header-view .ant-picker-year-btn')
        btn.click()

        while not flag:
            # 定位到年份表格
            table = WebDriverWait(date_selector, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.ant-picker-content')))

            time.sleep(1)
            rows = table.find_elements(By.TAG_NAME, 'tr')
            first_cell = rows[0].find_element(By.TAG_NAME, 'td')
            # 左上角年份值
            title_value = int(first_cell.get_attribute('title'))
            print('左上角年份值：{}, 想要选择的年份值:{}'.format(title_value, target_year))
            if title_value <= target_year and target_year <= title_value + 11:
                for row in rows:
                    # 获取所有 td
                    cells = row.find_elements(By.TAG_NAME, 'td')
                    for cell in cells:
                        value = cell.get_attribute('title')
                        if str(target_year) == value:
                            cell.click()
                            flag = True
                            break
                    if flag:
                        break
            elif title_value + 11 < target_year:
                print('点击按钮展示下一页年份数据')
                next_page = date_selector.find_element(By.CSS_SELECTOR, '.ant-picker-header-super-next-btn')
                next_page.click()
            else:
                print('点击按钮展示上一页年份数据')
                prev = date_selector.find_element(By.CSS_SELECTOR, '.ant-picker-header-super-prev-btn')
                prev.click()

        # 如果是单个日期控件，选择月份需要先点击月份按钮
        month_btn = WebDriverWait(date_selector, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.ant-picker-month-btn')))
        month_btn.click()

        # 选择月份
        month_table = WebDriverWait(date_selector, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.ant-picker-content')))
        month_cells = month_table.find_elements(By.TAG_NAME, 'td')
        for cell in month_cells:
            value = cell.get_attribute('title')
            if value == target_month:
                cell.click()
                break
        time.sleep(1)
        # 选择日期
        if is_single:
            # 如果是单个日期控件
            day_table = WebDriverWait(date_selector, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.ant-picker-content')))
            day_cells = day_table.find_elements(By.TAG_NAME, 'td')
        else:
            WebDriverWait(date_selector, 10).until(
                EC.visibility_of_element_located((By.XPATH, '//*[contains(@class, "ant-picker-panels")]')))
            tables = date_selector.find_elements(By.CSS_SELECTOR, '.ant-picker-panel')
            day_cells = tables[0].find_elements(By.TAG_NAME, 'td')
        for cell in day_cells:
            value = cell.get_attribute('title')
            if value == target_date:
                cell.click()
                break
        time.sleep(1)

    def quit(self):
        """关闭浏览器"""
        self.driver.quit()
