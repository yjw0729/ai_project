import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import sys
    from flask import Flask
    from logging import getLogger, Formatter, INFO
    from logging.handlers import TimedRotatingFileHandler
    from flask.logging import default_handler
    from utils.read_config_path.read_app_dir import get_xml_path, read_xml
    from utils.read_config_path.read_logs_dir import create_log_file
    from api.http_bank_card_no import bankcard_number_opt
    from api.http_create_address import generate_address_opt
    from api.http_create_idCardNo import generate_idCardNo_opt
    from api.http_create_customer import generate_information_opt
    from api.http_create_phone import create_phone_opt
    from api.http_create_picture import draw_picture_opt
    from api.http_ai_generate_cases import ai_generate_opt
    from api.http_ai_doc_parser import doc_parser_opt
    from api.http_database_config import db_config_opt
    from api.http_environment_config import env_config_opt
    from api.http_api_config import api_config_opt
    from api.http_test_execution import test_exec_opt
except Exception as e:
    print('异常信息' + str(e))
    exit(0)

# 创建Flask应用实例
app = Flask(__name__)

# 从XML配置文件中读取应用端口号
app_port = read_xml(get_xml_path(), 'app_port')

# 移除Flask默认的日志处理器
app.logger.removeHandler(default_handler)

# 获取根日志记录器
logger = getLogger()

# 创建日志文件并返回日志文件路径
logs_dir = create_log_file()

class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    TimedRotatingFileHandler 在 Windows 上如果文件被占用（例如被查看）时，rename 会抛 PermissionError。
    这里捕获并静默忽略该错误，继续写当前文件，避免线程异常和多余日志。
    """

    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError as e:
            # 继续写入当前文件
            if self.stream is None:
                self.stream = self._open()


# 按小时切分日志文件，最多保留7天（168小时），delay=True 减少文件长时间占用
lfh = SafeTimedRotatingFileHandler(
    logs_dir,
    when='H',
    interval=1,
    backupCount=168,
    encoding='utf-8',
    utc=False,
    delay=True
)

# 创建日志格式器，定义更易读的输出格式
formatter = Formatter(
    fmt="%(asctime)s [%(levelname)s] [thread:%(threadName)s] %(name)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# 为文件处理器设置格式器
lfh.setFormatter(formatter)

# 为根日志记录器添加文件处理器
lfh.setLevel(INFO)
logger.addHandler(lfh)

# 设置日志记录级别为INFO（如需调试可改为DEBUG）
logger.setLevel(INFO)

# 为Flask应用日志器添加处理者
app.logger.addHandler(lfh)


app.register_blueprint(bankcard_number_opt, url_prefix="/data_service")
app.register_blueprint(generate_address_opt, url_prefix="/data_service")
app.register_blueprint(generate_information_opt, url_prefix="/data_service")
app.register_blueprint(generate_idCardNo_opt, url_prefix="/data_service")
app.register_blueprint(create_phone_opt, url_prefix="/data_service")
app.register_blueprint(draw_picture_opt, url_prefix="/data_service")
app.register_blueprint(ai_generate_opt, url_prefix="/ai_service")
app.register_blueprint(doc_parser_opt, url_prefix="/ai_service")
app.register_blueprint(db_config_opt, url_prefix="/data_service")
app.register_blueprint(env_config_opt, url_prefix="/data_service")
app.register_blueprint(api_config_opt, url_prefix="/data_service")
app.register_blueprint(test_exec_opt, url_prefix="/data_service")


if __name__ == '__main__':
    app.debug = True
    host = "172.16.46.138"
    print(f"服务启动成功，访问地址: http://{host}:{app_port}")
    app.run(host=host, port=app_port)