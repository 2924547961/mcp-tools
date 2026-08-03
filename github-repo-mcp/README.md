# GitHub Repository MCP

一个独立的 stdio MCP Server，用于让支持 MCP 的客户端安全地创建 GitHub 仓库、发布本地代码、同步后续改动、拉取更新和克隆仓库。

## 主要用途

当 Codex 已经在本机生成代码，用户希望“自动在 GitHub 建库并提交代码”时，直接调用 `github_repository` 工具的 `create_and_publish` 动作。

## 工具

MCP 只暴露一个统一工具：`github_repository`。通过 `action` 选择具体操作。

| `action` | 用途 |
| --- | --- |
| `create` | 创建空 GitHub 仓库，默认私有 |
| `create_and_publish` | 一次完成“创建仓库 + 初始化 Git + 提交 + 推送” |
| `publish` | 把本地目录发布到已有 GitHub 仓库 |
| `sync` | 检测改动，有改动时提交并推送 |
| `pull` | 拉取远程更新，默认仅允许 fast-forward |
| `clone` | 克隆仓库到允许的本地目录 |
| `status` | 查看分支、远程地址和未提交文件 |

## 安装

需要 Node.js 18+ 和 Git。

```powershell
npm install
npm run check
```

编译后的入口是：

```text
dist/src/index.js
```

## MCP 配置

Windows 示例：

```toml
[mcp_servers.github-repository]
command = 'D:\software\Node.js\node.exe'
args = ['C:\Users\xyh\Documents\Codex\2026-07-25\wo\outputs\mcp-tools\github-repo-mcp\dist\src\index.js']

[mcp_servers.github-repository.env]
GITHUB_MCP_ALLOWED_ROOTS = 'C:\;D:\;E:\'
GITHUB_MCP_GIT_EMAIL = "r2c-ids@local.invalid"
GITHUB_MCP_GIT_NAME = "R2C-IDS Automation"
```

`GITHUB_TOKEN` / `GH_TOKEN` 可选。如果没有设置，MCP 会调用 `git credential fill`，复用系统中的 Git Credential Manager 登录状态。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `GITHUB_TOKEN` / `GH_TOKEN` | GitHub API 认证；没有时尝试 Git Credential Manager |
| `GITHUB_MCP_ALLOWED_ROOTS` | 允许访问的本地根目录；Windows 用分号分隔，macOS/Linux 用冒号分隔 |
| `GITHUB_MCP_GIT_NAME` | Git 没有提交者姓名时使用 |
| `GITHUB_MCP_GIT_EMAIL` | Git 没有提交者邮箱时使用 |
| `GITHUB_MCP_GIT_PATH` | 自定义 Git 可执行文件，默认 `git` |
| `GITHUB_API_URL` | GitHub Enterprise API 地址，默认 `https://api.github.com` |

如果没有配置 `GITHUB_MCP_ALLOWED_ROOTS`，只允许操作 MCP 进程的当前工作目录。

## 调用示例

Codex 生成代码后，自动创建仓库并发布整个项目：

```json
{
  "action": "create_and_publish",
  "localPath": "E:\\my-project",
  "name": "my-project",
  "description": "My project",
  "private": false,
  "branch": "main",
  "commitMessage": "chore: initial publish"
}
```

提交并推送后续改动：

```json
{
  "action": "sync",
  "localPath": "E:\\my-project",
  "commitMessage": "feat: update project",
  "includeUntracked": true
}
```

`action: "sync"` 默认只提交已跟踪文件的改动。只有明确设置 `includeUntracked: true` 时，才会加入新文件。

## 安全行为

- 新仓库默认是私有仓库。
- 所有本地路径必须位于 `GITHUB_MCP_ALLOWED_ROOTS` 中。
- Git 命令通过参数数组执行，不经过 shell 拼接。
- 首次发布遇到 `.env`、私钥、证书或常见凭据文件时默认拒绝。
- 已存在的 `origin` 指向其他仓库时不会自动覆盖。
- 拉取默认使用 `--ff-only`，避免自动生成合并提交。
- 本 MCP 不提供删除仓库工具。
- 如果 GitHub 仓库已经创建，但本地提交或推送失败，返回结果会明确说明远程仓库已经存在，不会尝试静默删除。

## 验证

```powershell
npm run check
```

测试包含路径白名单、仓库地址解析、真实 stdio MCP 握手和工具调用。
