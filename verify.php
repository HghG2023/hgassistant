<?php
// 检查密码是否设置
if(isset($_POST['password'])) {
    $password = $_POST['password'];
    
    // 此处替换为您自己的密码
    $correct_password = 'your_password_here';
    
    // 验证密码是否正确
    if($password === $correct_password) {
        // 密码正确，重定向到受保护页面
        header("Location: url1.php");
        exit;
    } else {
        // 密码错误，返回到密码输入页面
        header("Location: index.php");
        exit;
    }
} else {
    // 如果密码未设置，则返回到密码输入页面
    header("Location: index.php");
    exit;
}
?>
