from sys import path as sys_path
from os import path as os_path
import socket
import os

# 设置正确的项目根目录
project_root = os_path.dirname(os_path.abspath(__file__))
sys_path.insert(0, project_root)
sys_path.insert(0, os_path.join(project_root, '..'))

try:
    from app.application import app as application, app_port
except Exception as e:
    print('[run]启动失败：' + str(e))
    exit(0)


def get_local_ip():
    """获取本机IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'


server_config = {
    'server': get_local_ip()  # 或直接使用 '127.0.0.1'
}

if __name__ == '__main__':
    try:
        # 尝试使用 gevent 服务器
        from gevent.pywsgi import WSGIServer
        server_address = (server_config['server'], int(app_port))
        http_server = WSGIServer(server_address, application)
        print(f'启动成功，访问地址为: http://{server_config["server"]}:{app_port}')
        print('生产模式启动 - 查看日志文件获取详细状态信息')
        http_server.serve_forever()
    except ImportError:
        # 如果没有 gevent，使用 Flask 内置开发服务器
        print('提示: gevent 未安装，使用 Flask 内置服务器')
        try:
            from werkzeug.serving import run_simple
            server_address = (server_config['server'], int(app_port))
            print(f'启动成功，访问地址为: http://{server_config["server"]}:{app_port}')
            print('开发模式启动 - 仅用于测试')
            run_simple(
                server_address[0],
                server_address[1],
                application,
                use_reloader=False,
                use_debugger=False,
                threaded=True
            )
        except Exception as e:
            print(f'启动失败: {e}')
            # 如果IP地址失败，尝试使用本地地址
            print('尝试使用本地地址启动...')
            try:
                from werkzeug.serving import run_simple
                server_address = ('127.0.0.1', int(app_port))
                print(f'启动成功，访问地址为: http://127.0.0.1:{app_port}')
                print('开发模式启动 - 仅用于测试')
                run_simple(
                    server_address[0],
                    server_address[1],
                    application,
                    use_reloader=False,
                    use_debugger=False,
                    threaded=True
                )
            except Exception as e2:
                print(f'启动失败: {e2}')
