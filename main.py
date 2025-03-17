"""
IP Address API Service
Version: 1.2.0
Author: API Team
"""

from flask import Flask, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from ipaddress import ip_address, IPv4Address, IPv6Address
import logging
from typing import Optional, Union

# 初始化 Flask 应用
app = Flask(__name__)


# ====================
# 生产环境配置
# ====================
class ProductionConfig:
    TRUSTED_PROXIES = {'127.0.0.1', '::1'}  # 可信代理服务器IP
    PROXY_LAYERS = 5  # 代理层数（根据实际架构调整）
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'


app.config.from_object(ProductionConfig)

# ====================
# 代理中间件配置
# ====================
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=app.config['PROXY_LAYERS'],
    x_proto=app.config['PROXY_LAYERS'],
    x_host=app.config['PROXY_LAYERS'],
    x_port=app.config['PROXY_LAYERS'],
    x_prefix=app.config['PROXY_LAYERS']
)

# ====================
# 日志配置
# ====================
logging.basicConfig(
    level=app.config['LOG_LEVEL'],
    format=app.config['LOG_FORMAT']
)
logger = logging.getLogger(__name__)


# ====================
# 工具函数
# ====================
def validate_ip(ip_str: str) -> Optional[Union[IPv4Address, IPv6Address]]:
    """验证IP地址格式有效性"""
    try:
        return ip_address(ip_str.strip())
    except ValueError:
        return None


def get_real_client_ip() -> str:
    """
    安全获取客户端真实IP的优先顺序：
    1. X-Forwarded-For (最左侧可信IP)
    2. X-Real-IP
    3. remote_addr
    """
    client_ip = 'unknown'

    # 处理 X-Forwarded-For
    if "X-Forwarded-For" in request.headers:
        xff = request.headers.get('X-Forwarded-For')
        proxies = [ip.strip() for ip in xff.split(',')]
        # 根据代理层数获取有效IP
        trusted_proxies = app.config['TRUSTED_PROXIES']
        for ip in reversed(proxies):
            if validate_ip(ip) and ip not in trusted_proxies:
                client_ip = ip
                break

    # 回退到 X-Real-IP
    if client_ip == 'unknown' and ("X-Real-IP" in request.headers):
        xri = request.headers.get('X-Real-IP')
        if validate_ip(xri):
            client_ip = xri

    # 最终回退到 remote_addr
    if client_ip == 'unknown':
        client_ip = request.remote_addr or 'unknown'

    return client_ip


# ====================
# 请求处理管道
# ====================
@app.before_request
def before_request():
    """请求预处理"""
    # 记录原始请求信息
    logger.info(f"Incoming request | Headers: {dict(request.headers)}")


@app.after_request
def after_request(response):
    """响应后处理"""
    # 记录访问日志
    client_ip = get_real_client_ip()
    logger.info(
        f"{client_ip} - "
        f"{request.method} {request.path} - "
        f"Status: {response.status_code}"
    )
    return response


# ====================
# API 端点
# ====================
@app.route('/ip', methods=['GET'])
def get_client_ip():
    """主API端点"""
    client_ip = get_real_client_ip()

    return jsonify({
        'ip': client_ip,
        'network': {
            'is_global': validate_ip(client_ip).is_global if validate_ip(client_ip) else False,
            'version': 'v4' if isinstance(validate_ip(client_ip), IPv4Address) else 'v6' if validate_ip(
                client_ip) else 'invalid'
        },
        'meta': {
            'forwarded_for': request.headers.get('X-Forwarded-For'),
            'real_ip': request.headers.get('X-Real-IP'),
            'remote_addr': request.remote_addr
        }
    })


@app.route('/', methods=['GET'])
def home():
    """主页"""
    return jsonify({'message': 'Welcome to IP Address API Service!'})


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({'status': 'healthy', 'version': '1.2.0'})


# ====================
# 错误处理
# ====================
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# ====================
# 主程序入口
# ====================
if __name__ == '__main__':
    # 开发模式运行（生产环境应使用 Gunicorn）
    app.run(
        host='0.0.0.0',
        port=6005,
        debug=False  # 生产环境必须关闭debug模式
    )
