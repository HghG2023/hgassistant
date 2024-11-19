

import smtplib
from email.mime.text import MIMEText
gmail_app_psw = 'arel dreq ecvw bpwq'


# Gmail SMTP 配置
smtp_server = "smtp.gmail.com"
smtp_port = 587
sender_email = "hg020309@gmail.com"
password = gmail_app_psw

# 接收方信息
phone_number = "1264661272"  # 替换为目标号码
carrier_gateway = "qq.com"  # 替换为对应运营商的短信网关
recipient_email = f"{phone_number}@{carrier_gateway}"

# 邮件内容
message = MIMEText("你好，我是测试，请不要删除")
message["From"] = sender_email
message["To"] = recipient_email
message["Subject"] = "Test SMS"  # 可省略，部分网关不显示主题

try:
    # 建立连接
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()  # 启用加密
        server.login(sender_email, password)
        server.sendmail(sender_email, recipient_email, message.as_string())
    print("短信已发送！")
except Exception as e:
    print(f"发送失败: {e}")
