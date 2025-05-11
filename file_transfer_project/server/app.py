from flask import Flask, request, send_from_directory, redirect, url_for, render_template_string, abort
import os

app = Flask(__name__)
UPLOAD_FOLDER = os.path.abspath("../shared_files")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 确保能找到HTML模板文件
try:
    with open("server/index.html", "r", encoding="utf-8") as file:
        HTML_TEMPLATE = file.read()
except FileNotFoundError:
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <body>
        <h1>模板文件未找到</h1>
        <p>请检查server/index.html文件是否存在</p>
    </body>
    </html>
    """

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        f = request.files['file']
        if f:
            # 防止上传文件夹（Flask的FileStorage对象始终是文件）
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], f.filename))
            return redirect(url_for('upload_file'))
    
    # 过滤掉文件夹，只显示文件
    files = []
    try:
        for item in os.listdir(app.config['UPLOAD_FOLDER']):
            item_path = os.path.join(app.config['UPLOAD_FOLDER'], item)
            if os.path.isfile(item_path):
                files.append(item)
    except Exception as e:
        print(f"无法列出文件: {e}")
    
    return render_template_string(HTML_TEMPLATE, files=files)

@app.route('/files/<path:filename>')
def download_file(filename):
    # 构建完整路径
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # 安全检查：确保是文件且存在
    if not os.path.isfile(file_path):
        abort(404, description="文件不存在或不是文件")
    
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# 添加404错误处理
@app.errorhandler(404)
def page_not_found(e):
    return f"""
    <!DOCTYPE html>
    <html>
    <body>
        <h1>404 - 页面未找到</h1>
        <p>请求的URL: {request.path} 不存在</p>
        <p>请检查URL拼写或返回 <a href="/">主页</a></p>
    </body>
    </html>
    """, 404

if __name__ == '__main__':
    import socket
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    port = 8000
    print(f"服务已启动：在手机浏览器中访问 http://{ip}:{port} 上传/下载文件")
    print(f"上传目录: {UPLOAD_FOLDER}")
    app.run(host='0.0.0.0', port=port, debug=True)