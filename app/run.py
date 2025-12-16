from sys import path as sys_path
from os import path as os_path
import socket

sys_path.append(os_path.join(os_path.abspath('..')))

try:
    from gevent.pywsgi import WSGIServer
    from app import application
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
        server_address = (server_config['server'], int(application.app_port))
        http_server = WSGIServer(server_address, application.app)
        print(f'启动成功，访问地址为: http://{server_config["server"]}:{application.app_port}')
        http_server.serve_forever()
    except Exception as e:
        print(f'启动失败: {e}')
        # 如果IP地址失败，尝试使用本地地址
        print('尝试使用本地地址启动...')
        server_address = ('127.0.0.1', int(application.app_port))
        http_server = WSGIServer(server_address, application.app)
        print(f'启动成功，访问地址为: http://127.0.0.1:{application.app_port}')
        http_server.serve_forever()