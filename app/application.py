import sys
import os

# 限制 OpenBLAS / OMP 线程数，必须在 numpy 等库加载之前设置
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

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
    from api.http_rag_document import rag_document_opt
    from api.http_test_case_generate import test_case_gen_opt
    from api.http_rag_document_v2 import rag_document_opt_v2
    from api.http_rag_iteration import rag_iteration_opt
    from api.http_document_comparison import comparison_bp
    from api.http_page_test_case_generate import page_test_case_bp
    from api.http_api_interface_xmind import api_interface_xmind_bp
    from api.http_api_auto_test import api_auto_test_bp
except Exception as e:
    print('异常信息' + str(e))
    exit(0)

# 读取AI配置，设置API Key环境变量
def _load_api_keys():
    """从配置文件加载API Keys"""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'app', 'ai_config.json')
    if os.path.exists(config_path):
        try:
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                api_key = config.get('api_key')
                if api_key:
                    os.environ['DASHSCOPE_API_KEY'] = api_key
                    print(f"[OK] Loaded Tongyi API Key")
                base_url = config.get('base_url')
                if base_url:
                    os.environ['DASHSCOPE_BASE_URL'] = base_url
        except Exception as e:
            print(f"[WARN] Failed to load API config: {e}")

_load_api_keys()

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


def check_database_connection():
    """检查数据库连接池配置状态（不建立实际连接）"""
    try:
        # 显示连接池配置信息，不进行实际连接测试
        pool_info = "连接池配置: 10基础+20溢出=30最大 | 30秒超时 | 1小时回收 | 连接前健康检查"

        return True, f"数据库连接池已配置 | {pool_info}"

    except Exception as e:
        return False, f"数据库配置错误: {e}"


def check_rag_service_status():
    """检查RAG服务状态"""
    try:
        # 首先检查配置文件（相对于application.py的位置）
        app_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(app_dir, "config")
        if not os.path.exists(config_dir):
            return False, f"配置文件目录不存在: {config_dir}"

        # 读取向量数据库配置
        vector_config_path = os.path.join(config_dir, "vector_db", "vector_db.json")
        rag_config_path = os.path.join(config_dir, "rag", "rag.json")

        # 调试信息
        # print(f"检查配置文件: {vector_config_path}, {rag_config_path}")

        if not os.path.exists(vector_config_path) or not os.path.exists(rag_config_path):
            return False, "RAG配置文件缺失"

        import json
        with open(vector_config_path, 'r', encoding='utf-8') as f:
            vector_config = json.load(f)

        with open(rag_config_path, 'r', encoding='utf-8') as f:
            rag_config = json.load(f)

        db_type = vector_config.get('db_type', 'unknown')
        embedding_provider = rag_config.get('embedding_provider', 'unknown')
        embedding_model = rag_config.get('embedding_model', 'unknown')

        status_parts = []

        # 向量数据库状态
        if db_type == "chroma":
            host = vector_config.get('host', 'localhost')
            port = vector_config.get('port', 8000)

            if host in ['localhost', '127.0.0.1', '']:
                # 本地ChromaDB
                chroma_dir = "./chroma_data"
                if os.path.exists(chroma_dir):
                    try:
                        files = os.listdir(chroma_dir)
                        db_size = sum(os.path.getsize(os.path.join(chroma_dir, f)) for f in files if os.path.isfile(os.path.join(chroma_dir, f)))
                        status_parts.append(f"本地ChromaDB (持久化存储, {len(files)}个文件, {db_size/1024:.1f}KB)")
                    except Exception:
                        status_parts.append("本地ChromaDB (持久化存储)")
                else:
                    status_parts.append("本地ChromaDB (数据目录将自动创建)")
            else:
                # 远程ChromaDB
                status_parts.append(f"远程ChromaDB服务器 ({host}:{port})")
        elif db_type == "memory":
            status_parts.append("内存向量存储 (⚠️ 重启后数据会丢失)")
        elif db_type == "qdrant":
            host = vector_config.get('host', 'localhost')
            port = vector_config.get('port', 6333)
            status_parts.append(f"Qdrant向量数据库 ({host}:{port})")
        elif db_type == "pinecone":
            status_parts.append("Pinecone云向量数据库")
        else:
            status_parts.append(f"{db_type}向量数据库")

        # Embedding模型状态
        if embedding_provider == "local":
            status_parts.append(f"本地Embedding模型 ({embedding_model})")
        elif embedding_provider == "tongyi":
            status_parts.append(f"通义千问Embedding ({embedding_model})")
        elif embedding_provider == "openai":
            status_parts.append(f"OpenAI Embedding ({embedding_model})")
        else:
            status_parts.append(f"{embedding_provider} Embedding ({embedding_model})")

        return True, " | ".join(status_parts)

    except Exception as e:
        # 如果配置检查失败，尝试简单的文件检查
        try:
            chroma_dir = "./chroma_data"
            if os.path.exists(chroma_dir):
                files = os.listdir(chroma_dir)
                return True, f"ChromaDB配置检查失败，使用默认配置 (持久化存储, {len(files)}个文件)"
            else:
                return True, "ChromaDB配置检查失败，使用默认配置 (数据目录将自动创建)"
        except Exception:
            return False, f"RAG配置检查失败: {str(e)}"


def log_system_status():
    """记录系统状态到日志"""
    app.logger.info("="*60)
    app.logger.info("🚀 系统启动状态检查")
    app.logger.info("="*60)

    # 检查数据库连接
    db_status, db_message = check_database_connection()
    if db_status:
        app.logger.info(f"✅ 数据库状态: {db_message}")
    else:
        app.logger.warning(f"⚠️  数据库状态: {db_message}")

    # 检查RAG服务状态
    rag_status, rag_message = check_rag_service_status()
    if rag_status:
        app.logger.info(f"✅ RAG服务状态: {rag_message}")
    else:
        app.logger.error(f"❌ RAG服务状态: {rag_message}")

    # 记录API接口信息
    app.logger.info("📋 已注册的API接口:")
    app.logger.info("   🔹 数据服务: /data_service/*")
    app.logger.info("   🔹 AI服务: /ai_service/*")
    app.logger.info("   🔹 RAG服务: /rag_service/*")
    app.logger.info("   🔹 API自动化测试: /api/auto_test/*")

    # 记录服务端口
    app.logger.info(f"🌐 服务端口: {app_port}")
    app.logger.info("="*60)


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
app.register_blueprint(rag_document_opt, url_prefix="/rag_service")
app.register_blueprint(test_case_gen_opt, url_prefix="/rag_service")
app.register_blueprint(rag_document_opt_v2, url_prefix="/rag_service")
app.register_blueprint(rag_iteration_opt, url_prefix="/rag_service")
app.register_blueprint(comparison_bp, url_prefix="/comparison")
app.register_blueprint(page_test_case_bp, url_prefix="/page_test_case")
app.register_blueprint(api_interface_xmind_bp, url_prefix="/api_interface_xmind")
app.register_blueprint(api_auto_test_bp, url_prefix="/api/auto_test")


# 在应用创建后立即检查系统状态
def init_system_status():
    """初始化时显示系统状态"""
    try:
        # 数据库状态检查
        db_status, db_message = check_database_connection()
        status_icon = "[OK]" if db_status else "[FAIL]"
        print(f"DB Status: {status_icon} {db_message}")

        # RAG服务状态检查
        rag_status, rag_message = check_rag_service_status()
        status_icon = "[OK]" if rag_status else "[FAIL]"
        print(f"RAG Status: {status_icon} {rag_message}")

        print("API Ready: /rag_service/*")
        print(f"Port: {app_port}")
        print("-" * 50)

    except Exception as e:
        print(f"WARN - System status check exception: {e}")

# 执行系统状态检查
init_system_status()


if __name__ == '__main__':
    app.debug = True
    host = "127.0.0.1"
    print(f"服务启动成功，访问地址: http://{host}:{app_port}")
    app.run(host=host, port=app_port)