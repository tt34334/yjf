# 足球综合服务平台（Football Service Platform）

一个集场地预订、散场拼团、球队管理、赛事组织、教练预约、康复机构查询、社区动态于一体的足球综合服务平台。

## 技术栈

- **后端**: Java 17, Spring Boot 3.3.4, Spring Data JPA, MySQL
- **前端**: Vue 3, Vite, Element Plus, Vue Router, Axios, ECharts
- **构建工具**: Maven, npm

## 功能模块

| 模块 | 说明 |
|------|------|
| 用户系统 | 注册 / 登录 / 手机号验证码登录 / 个人信息管理 / 头像上传 |
| 场地服务 | 场地列表 / 附近场地（基于地理位置）/ 场地详情 / 场地预订 / 场地评价 |
| 散场拼团 | 发起拼场 / 加入拼场 / 拼场管理 |
| 球队管理 | 创建球队 / 加入球队 / 球队招募 / 球队成员管理 |
| 赛事系统 | 赛事创建 / 球队报名 / 赛程管理 / 比分记录 |
| 专业服务 | 教练列表 / 教练预约 / 康复机构查询 |
| 社区动态 | 发布动态 / 评论 / 点赞 |
| 后台管理 | 场地管理 / 用户管理 / 赛事管理 / 活动管理 |
| AI 助手 | 内置 AI 问答助手 |

## 快速开始

### 环境要求

- JDK 17+
- Maven 3.6+
- Node.js 16+
- MySQL 8.0+

### 1. 数据库准备

确保本地 MySQL 已启动，并创建数据库（应用会自动创建，也可手动执行）：

```sql
CREATE DATABASE IF NOT EXISTS football DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

默认连接配置（见 `backend/src/main/resources/application.yml`）：
- 地址: `localhost:3306`
- 用户名: `root`
- 密码: `123456`

> 如需修改，请编辑 `application.yml` 中的 `spring.datasource` 配置。

### 2. 启动后端

```bash
cd backend
mvn spring-boot:run
```

后端服务地址: `http://localhost:8080`

首次启动会自动执行 `src/main/resources/sql/full_schema.sql` 建表，并通过 `CommandLineRunner` 初始化基础数据（角色、测试用户、示例场地）。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端服务地址: `http://localhost:5173`

### 4. 一键启动（Windows）

项目根目录提供了启动脚本：

- `start_all.bat` — 双击运行，自动启动前后端
- `start.ps1` — PowerShell 版本启动脚本

> 脚本已使用相对路径，无需修改即可在任意目录运行。

## 默认账号

| 角色 | 账号 | 密码 | 说明 |
|------|------|------|------|
| 超级管理员 | `superadmin` | `123456` | 平台超级管理员 |
| 场地管理员 | `admin` | `123456` | 球场管理员 |
| 普通用户 | `demo` | `123456` | 测试用户 |

## 项目结构

```
足球散场拼团/
├── backend/                 # Spring Boot 后端
│   ├── src/main/java/com/football/
│   │   ├── config/          # 配置类（CORS、静态资源、Jackson）
│   │   ├── controller/      # REST API 控制器
│   │   ├── domain/          # JPA 实体
│   │   ├── dto/             # 数据传输对象
│   │   ├── repo/            # Spring Data JPA Repository
│   │   └── util/            # 工具类
│   ├── src/main/resources/
│   │   ├── application.yml  # 主配置文件
│   │   └── sql/             # 建表与初始化 SQL
│   └── uploads/             # 上传文件存储（头像、场地图片）
├── frontend/                # Vue 3 前端
│   ├── src/
│   │   ├── components/      # 公共组件
│   │   ├── pages/           # 页面组件
│   │   ├── utils/           # 工具函数
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── router.ts
│   ├── index.html
│   └── vite.config.ts
├── uploads/                 # 其他上传文件
├── db_dictionary.csv        # 数据库字典
├── start_all.bat            # Windows 一键启动脚本
├── start.ps1                # PowerShell 启动脚本
└── README.md
```

## 数据库

数据库字典见根目录 `db_dictionary.csv`，包含所有表结构、字段说明及索引信息。

## 注意事项

- 项目为演示/学习用途，密码等敏感信息为硬编码，请勿直接用于生产环境。
- 图片上传功能依赖本地文件系统，部署到服务器时请确保 `backend/uploads/` 目录可写。
- 前端通过 Vite 代理将 `/api` 请求转发到 `http://localhost:8080`，如需修改后端地址请同步修改 `frontend/vite.config.ts`。
- 高德地图 JS API 安全密钥配置在 `frontend/index.html` 中，如需部署到公网，建议替换为你自己的高德地图密钥。

## License

MIT
