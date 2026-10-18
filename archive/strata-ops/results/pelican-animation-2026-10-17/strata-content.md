```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>鹈鹕骑自行车动画</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background-color: #87CEEB;
            overflow: hidden;
        }
        svg {
            max-width: 100%;
            max-height: 100vh;
        }
    </style>
</head>
<body>
    <svg viewBox="0 0 800 400" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <style>
                /* 动画定义 */
                @keyframes wheelSpin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
                @keyframes bobbing {
                    0%, 100% { transform: translateY(0px); }
                    50% { transform: translateY(-5px); }
                }
                @keyframes legPedal {
                    0% { transform: rotate(0deg); }
                    25% { transform: rotate(15deg); }
                    50% { transform: rotate(0deg); }
                    75% { transform: rotate(-15deg); }
                    100% { transform: rotate(0deg); }
                }
                @keyframes legPedalOpposite {
                    0% { transform: rotate(0deg); }
                    25% { transform: rotate(-15deg); }
                    50% { transform: rotate(0deg); }
                    75% { transform: rotate(15deg); }
                    100% { transform: rotate(0deg); }
                }
                @keyframes wingFlap {
                    0%, 100% { transform: rotate(0deg); }
                    50% { transform: rotate(-10deg); }
                }

                .wheel {
                    animation: wheelSpin 1s linear infinite;
                    transform-origin: center;
                }
                .body-bob {
                    animation: bobbing 0.5s ease-in-out infinite;
                }
                .leg-left {
                    animation: legPedal 1s ease-in-out infinite;
                    transform-origin: 400px 280px;
                }
                .leg-right {
                    animation: legPedalOpposite 1s ease-in-out infinite;
                    transform-origin: 400px 280px;
                }
                .wing {
                    animation: wingFlap 0.5s ease-in-out infinite;
                    transform-origin: 380px 220px;
                }
            </style>
        </defs>

        <!-- 背景装饰 -->
        <circle cx="700" cy="80" r="40" fill="#FFD700" opacity="0.8"/>
        <path d="M0 350 Q 200 330 400 350 T 800 350 L 800 400 L 0 400 Z" fill="#228B22"/>
        <path d="M0 350 Q 200 330 400 350 T 800 350" fill="none" stroke="#006400" stroke-width="2"/>

        <!-- 自行车后轮 -->
        <g class="wheel" style="transform-origin: 250px 300px;">
            <circle cx="250" cy="300" r="40" fill="none" stroke="#333" stroke-width="4"/>
            <circle cx="250" cy="300" r="35" fill="none" stroke="#666" stroke-width="1"/>
            <!-- 辐条 -->
            <line x1="250" y1="260" x2="250" y2="340" stroke="#666" stroke-width="2"/>
            <line x1="210" y1="300" x2="290" y2="300" stroke="#666" stroke-width="2"/>
            <line x1="222" y1="272" x2="278" y2="328" stroke="#666" stroke-width="2"/>
            <line x1="222" y1="328" x2="278" y2="272" stroke="#666" stroke-width="2"/>
            <circle cx="250" cy="300" r="5" fill="#333"/>
        </g>

        <!-- 自行车前轮 -->
        <g class="wheel" style="transform-origin: 550px 300px;">
            <circle cx="550" cy="300" r="40" fill="none" stroke="#333" stroke-width="4"/>
            <circle cx="550" cy="300" r="35" fill="none" stroke="#666" stroke-width="1"/>
            <!-- 辐条 -->
            <line x1="550" y1="260" x2="550" y2="340" stroke="#666" stroke-width="2"/>
            <line x1="510" y1="300" x2="590" y2="300" stroke="#666" stroke-width="2"/>
            <line x1="522" y1="272" x2="578" y2="328" stroke="#666" stroke-width="2"/>
            <line x1="522" y1="328" x2="578" y2="272" stroke="#666" stroke-width="2"/>
            <circle cx="550" cy="300" r="5" fill="#333"/>
        </g>

        <!-- 自行车车架 -->
        <path d="M250 300 L350 220 L450 220 L550 300" fill="none" stroke="#333" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M350 220 L400 280 L450 220" fill="none" stroke="#333" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="400" y1="280" x2="400" y2="300" stroke="#333" stroke-width="6" stroke-linecap="round"/>
        <!-- 车把 -->
        <path d="M450 220 L480 180 L520 180" fill="none" stroke="#333" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
        <!-- 车座 -->
        <ellipse cx="350" cy="210" rx="15" ry="8" fill="#333"/>

        <!-- 鹈鹕身体 -->
        <g class="body-bob">
            <!-- 尾巴 -->
            <path d="M320 210 Q 300 200 290 220 Q 300 230 320 220 Z" fill="#F0F0F0" stroke="#333" stroke-width="2"/>
            
            <!-- 身体 -->
            <ellipse cx="380" cy="210" rx="40" ry="30" fill="#F0F0F0" stroke="#333" stroke-width="2"/>
            
            <!-- 翅膀 -->
            <g class="wing">
                <path d="M380 210 Q 350 180 320 200 Q 340 220 380 210 Z" fill="#E0E0E0" stroke="#333" stroke-width="2"/>
            </g>

            <!-- 脖子 -->
            <path d="M410 200 Q 430 180 440 160" fill="none" stroke="#F0F0F0" stroke-width="15" stroke-linecap="round"/>
            <path d="M410 200 Q 430 180 440 160" fill="none" stroke="#333" stroke-width="2" stroke-linecap="round"/>

            <!-- 头部 -->
            <circle cx="445" cy="155" r="12" fill="#F0F0F0" stroke="#333" stroke-width="2"/>
            
            <!-- 眼睛 -->
            <circle cx="448" cy="152" r="2" fill="#333"/>
            
            <!-- 鹈鹕大嘴 -->
            <path d="M455 155 Q 520 150 530 170 Q 520 180 455 165 Z" fill="#FFA500" stroke="#333" stroke-width="2"/>
            <!-- 嘴袋细节 -->
            <path d="M460 160 Q 510 165 520 170" fill="none" stroke="#333" stroke-width="1" opacity="0.5"/>
            
            <!-- 腿 -->
            <g class="leg-left">
                <line x1="380" y1="230" x2="400" y2="280" stroke="#FFA500" stroke-width="4" stroke-linecap="round"/>
                <line x1="400" y1="280" x2="400" y2="300" stroke="#FFA500" stroke-width="4" stroke-linecap="round"/>
                <!-- 脚 -->
                <path d="M400 300 L390 310 L410 310 Z" fill="#FFA500" stroke="#333" stroke-width="1"/>
            </g>
            <g class="leg-right">
                <line x1="380" y1="230" x2="400" y2="280" stroke="#FFA500" stroke-width="4" stroke-linecap="round"/>
                <line x1="400" y1="280" x2="400" y2="300" stroke="#FFA500" stroke-width="4" stroke-linecap="round"/>
                <!-- 脚 -->
                <path d="M400 300 L390 310 L410 310 Z" fill="#FFA500" stroke="#333" stroke-width="1"/>
            </g>
        </g>
    </svg>
</body>
</html>
```