# MCP Tools

可复用 MCP Server 的合集仓库。每个 MCP 使用一个独立子目录，拥有自己的源码、依赖、测试和使用文档。

## 已包含的 MCP

| 目录 | 用途 | 版本 |
| --- | --- | --- |
| [`github-repo-mcp`](./github-repo-mcp/) | 创建 GitHub 仓库，以及安全发布、自动同步、拉取和克隆代码 | 0.3.0 |

## 目录约定

```text
mcp-tools/
├── github-repo-mcp/
│   ├── src/
│   ├── test/
│   ├── package.json
│   └── README.md
└── another-mcp/
    ├── src/
    ├── test/
    └── README.md
```

以后新增 MCP 时，在仓库根目录创建同级子目录即可。各 MCP 独立安装、构建和发布，根目录只负责分类和索引。

## 使用 github-repo-mcp

```powershell
cd .\github-repo-mcp
npm ci
npm run check
```

详细配置和工具参数见 [`github-repo-mcp/README.md`](./github-repo-mcp/README.md)。
