# Green Receipt API 前端接口文档

本文档面向前端接入使用，接口定义以 `app/main.py` 和 `app/models/schemas.py` 当前实现为准。

## 基础信息

- 服务框架：FastAPI
- 默认本地地址：`http://localhost:8000`
- 线上/测试环境地址：以后端实际部署地址为准
- 请求格式：`Content-Type: application/json`
- 响应格式：JSON
- 鉴权：当前接口未做登录态或 token 鉴权
- CORS：当前后端允许所有来源、方法和请求头
- 交互式文档：`GET /docs`

## 推荐接入流程

前端可以按产品体验选择两种流程。

1. 先分析，再由用户确认铸造 NFT：
   - 调用 `POST /api/receipts/analyze` 获取绿色报告、证据哈希、报告哈希和 metadata URI。
   - 用户确认后，带上分析接口返回的字段调用 `POST /api/receipts/mint`。

2. 一步完成分析和铸造：
   - 调用 `POST /api/receipts/analyze-and-mint`。
   - 适合 demo 或不需要用户二次确认的流程。

## 通用错误响应

FastAPI 校验失败时返回 `422`，格式通常如下：

```json
{
  "detail": [
    {
      "type": "string_pattern_mismatch",
      "loc": ["body", "to"],
      "msg": "String should match pattern '^0x[0-9a-fA-F]{40}$'",
      "input": "0x123"
    }
  ]
}
```

业务或服务异常时返回：

```json
{
  "detail": "error message"
}
```

常见状态码：

- `200`：请求成功。
- `422`：请求体字段缺失、格式不合法或不满足约束。
- `500`：分析、AI、存储等后端内部流程失败。
- `502`：链上 mint 流程失败，例如 RPC、合约、私钥、ABI、交易回执解析异常。

## GET /health

健康检查接口，用于确认后端服务是否运行。

### 请求

无请求参数。

### 响应示例

```json
{
  "status": "ok",
  "ai_mode": "mock"
}
```

### 字段说明

- `status`：服务状态，当前成功时固定为 `ok`。
- `ai_mode`：后端当前 AI 模式，常见值为 `mock` 或 `openai`。

## GET /api/reports/{reportHash}

根据 NFT metadata 中的 `reportHash` 查询后端本地保存的完整报告。

适用场景：前端查看某个 NFT 时，先读取 NFT 的 metadata URI，再从 metadata 顶层字段 `reportHash` 拿到报告哈希，最后调用该接口获取完整 report。

### 请求

```http
GET /api/reports/0x2222222222222222222222222222222222222222222222222222222222222222
```

### 路径参数

- `reportHash`：必填，必须是 `0x` 开头的 64 位十六进制字符串。

### 成功响应

```json
{
  "reportHash": "0x2222222222222222222222222222222222222222222222222222222222222222",
  "reportURI": "local://reports/2222222222222222.json",
  "report": {
    "productName": "Nike Pegasus Trail 5 DV3865-602",
    "brand": "Nike",
    "score": 62,
    "grade": "Medium Risk",
    "summary": "...",
    "positiveSignals": ["..."],
    "riskSignals": ["..."],
    "greenwashingRisk": "Medium",
    "findings": ["..."],
    "evidences": [],
    "alternatives": ["..."],
    "createdAt": "2026-05-10T02:00:00.000000"
  }
}
```

### 错误响应

- `404`：本地没有找到该 `reportHash` 对应的报告文件。
- `409`：本地文件存在，但重新计算出的报告哈希和请求的 `reportHash` 不一致。
- `422`：`reportHash` 格式不合法。

## POST /api/receipts/analyze

分析商品并生成 Green Receipt 报告，但不铸造 NFT。

适用场景：前端先展示分析结果，用户确认后再 mint。

### 请求体

```json
{
  "productName": "Nike Pegasus Trail 5 DV3865-602",
  "productUrl": "https://www.nike.com/example-product",
  "brand": "Nike"
}
```

### 请求字段

- `productName`：必填，字符串，最小长度为 1。商品名称或 SKU，建议前端必填。
- `productUrl`：选填，字符串。商品页面 URL；后端当前允许空字符串。
- `brand`：选填，字符串。品牌名；后端当前允许空字符串。

### 成功响应

```json
{
  "productName": "Nike Pegasus Trail 5 DV3865-602",
  "brand": "Nike",
  "score": 62,
  "grade": "Medium Risk",
  "summary": "Nike has published brand-level sustainability commitments...",
  "findings": [
    "Product-level LCA: NOT FOUND - Low Transparency",
    "Carbon footprint per pair: NOT FOUND - Low Transparency"
  ],
  "evidences": [
    {
      "title": "Nike Move to Zero - Sustainability Commitment",
      "source": "Nike Official Sustainability Page",
      "url": "https://www.nike.com/sustainability",
      "excerpt": "Nike's Move to Zero journey is our commitment...",
      "claim": "Nike targets 70% recycled polyester across all products by 2025.",
      "confidence": "High",
      "hash": "0x1111111111111111111111111111111111111111111111111111111111111111"
    }
  ],
  "reportHash": "0x2222222222222222222222222222222222222222222222222222222222222222",
  "evidenceMerkleRoot": "0x3333333333333333333333333333333333333333333333333333333333333333",
  "reportURI": "local://reports/2222222222222222.json",
  "metadataURI": "local://metadata/2222222222222222_meta.json"
}
```

### 响应字段

- `productName`：商品名称。
- `brand`：品牌名。
- `score`：环境评分，整数，范围 `0-100`。
- `grade`：评级文本，例如 `Medium Risk`、`A (Low Risk)`。
- `summary`：报告摘要。
- `findings`：分析结论列表。
- `evidences`：证据列表，每条证据会带上后端计算出的 `hash`。
- `reportHash`：完整报告 JSON 的 keccak256 哈希，格式为 `0x` + 64 位十六进制。
- `evidenceMerkleRoot`：证据哈希构建出的 Merkle Root，格式为 `0x` + 64 位十六进制。
- `reportURI`：报告存储地址。当前本地存储格式为 `local://reports/<filename>.json`。
- `metadataURI`：ERC-721 metadata 存储地址。当前本地存储格式为 `local://metadata/<filename>_meta.json`。

## POST /api/receipts/mint

使用已生成的报告哈希、证据 Merkle Root 和 metadata URI 铸造 Green Receipt NFT。

适用场景：前端已经调用过 `/api/receipts/analyze`，并拿到了 mint 所需字段。

### 请求体

```json
{
  "to": "0x1111111111111111111111111111111111111111",
  "productName": "Nike Pegasus Trail 5 DV3865-602",
  "brand": "Nike",
  "score": 62,
  "grade": "Medium Risk",
  "reportHash": "0x2222222222222222222222222222222222222222222222222222222222222222",
  "evidenceMerkleRoot": "0x3333333333333333333333333333333333333333333333333333333333333333",
  "metadataURI": "local://metadata/2222222222222222_meta.json"
}
```

### 请求字段

- `to`：必填，NFT 接收地址，必须匹配 `^0x[0-9a-fA-F]{40}$`。
- `productName`：必填，商品名称。建议直接使用 analyze 接口返回值。
- `brand`：必填，品牌名。建议直接使用 analyze 接口返回值。
- `score`：必填，整数，范围 `0-100`。建议直接使用 analyze 接口返回值。
- `grade`：必填，评级文本。建议直接使用 analyze 接口返回值。
- `reportHash`：必填，必须匹配 `^0x[0-9a-fA-F]{64}$`。
- `evidenceMerkleRoot`：必填，必须匹配 `^0x[0-9a-fA-F]{64}$`。
- `metadataURI`：必填，metadata URI。建议直接使用 analyze 接口返回值。

### 成功响应

```json
{
  "tokenId": 1,
  "transactionHash": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "contractAddress": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}
```

### 响应字段

- `tokenId`：链上 NFT token ID。
- `transactionHash`：mint 交易哈希。
- `contractAddress`：后端当前配置的 GreenReceiptNFT 合约地址。

### 前端注意事项

- 该接口会等待链上交易回执，耗时可能明显长于普通 HTTP 请求。
- 建议前端展示 loading 状态，并做好超时、重试或失败提示。
- 如果后端未配置 `PRIVATE_KEY`、`CONTRACT_ADDRESS`、`MONAD_RPC_URL` 或 ABI 文件，接口会返回 `502`。

## POST /api/receipts/analyze-and-mint

一步完成商品分析、报告存储、metadata 生成和 NFT 铸造。

适用场景：demo、快速验证或无需用户在分析后确认的流程。

### 请求体

```json
{
  "productName": "Nike Pegasus Trail 5 DV3865-602",
  "productUrl": "https://www.nike.com/example-product",
  "brand": "Nike",
  "to": "0x1111111111111111111111111111111111111111"
}
```

### 请求字段

- `productName`：必填，字符串，最小长度为 1。
- `productUrl`：选填，字符串，可为空字符串。
- `brand`：选填，字符串，可为空字符串。
- `to`：必填，NFT 接收地址，必须匹配 `^0x[0-9a-fA-F]{40}$`。

### 成功响应

```json
{
  "productName": "Nike Pegasus Trail 5 DV3865-602",
  "brand": "Nike",
  "score": 62,
  "grade": "Medium Risk",
  "summary": "Nike has published brand-level sustainability commitments...",
  "findings": [
    "Product-level LCA: NOT FOUND - Low Transparency",
    "Carbon footprint per pair: NOT FOUND - Low Transparency"
  ],
  "evidences": [
    {
      "title": "Nike Move to Zero - Sustainability Commitment",
      "source": "Nike Official Sustainability Page",
      "url": "https://www.nike.com/sustainability",
      "excerpt": "Nike's Move to Zero journey is our commitment...",
      "claim": "Nike targets 70% recycled polyester across all products by 2025.",
      "confidence": "High",
      "hash": "0x1111111111111111111111111111111111111111111111111111111111111111"
    }
  ],
  "reportHash": "0x2222222222222222222222222222222222222222222222222222222222222222",
  "evidenceMerkleRoot": "0x3333333333333333333333333333333333333333333333333333333333333333",
  "reportURI": "local://reports/2222222222222222.json",
  "metadataURI": "local://metadata/2222222222222222_meta.json",
  "tokenId": 1,
  "transactionHash": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "contractAddress": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}
```

### 响应字段

该接口响应等于 `/api/receipts/analyze` 的报告字段，加上 `/api/receipts/mint` 的链上字段：

- 报告字段：`productName`、`brand`、`score`、`grade`、`summary`、`findings`、`evidences`、`reportHash`、`evidenceMerkleRoot`、`reportURI`、`metadataURI`。
- 链上字段：`tokenId`、`transactionHash`、`contractAddress`。

## 数据模型

### Evidence

```json
{
  "title": "Evidence title",
  "source": "Source name",
  "url": "https://example.com",
  "excerpt": "Quoted or summarized evidence text",
  "claim": "Claim verified by this evidence",
  "confidence": "High",
  "hash": "0x1111111111111111111111111111111111111111111111111111111111111111"
}
```

字段说明：

- `title`：证据标题。
- `source`：来源名称。
- `url`：来源链接，可能为空字符串。
- `excerpt`：证据摘录。
- `claim`：该证据支持或说明的主张。
- `confidence`：置信度，只会是 `High`、`Medium`、`Low`、`Unverified` 之一。
- `hash`：后端计算出的证据哈希；请求时不需要传，响应中会返回。

### Report

分析服务内部的完整报告还包含以下字段：

```json
{
  "productName": "Nike Pegasus Trail 5 DV3865-602",
  "brand": "Nike",
  "score": 62,
  "grade": "Medium Risk",
  "summary": "...",
  "positiveSignals": ["..."],
  "riskSignals": ["..."],
  "greenwashingRisk": "Medium",
  "findings": ["..."],
  "evidences": [],
  "alternatives": ["..."],
  "createdAt": "2026-05-10T02:00:00.000000"
}
```

注意：当前 HTTP 响应只返回前端主要展示和 mint 所需字段，并未返回 `positiveSignals`、`riskSignals`、`greenwashingRisk`、`alternatives`、`createdAt`。这些字段会存在于后端保存的 report JSON 中。

## 前端校验建议

- `productName`：提交前做非空校验。
- `to`：提交前校验钱包地址格式为 `0x` 开头的 40 位十六进制地址。
- `reportHash` 和 `evidenceMerkleRoot`：如果前端允许用户手动输入，需校验为 `0x` 开头的 64 位十六进制字符串。
- `score`：展示时按 `0-100` 分处理。
- `metadataURI` 和 `reportURI`：当前是 `local://` 格式，不能直接当浏览器 URL 打开；如果后端后续切换 IPFS/Arweave，前端再按新的 URI 规则展示跳转。

## 前端调用示例

### 分析商品

```ts
async function analyzeReceipt() {
  const response = await fetch("http://localhost:8000/api/receipts/analyze", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      productName: "Nike Pegasus Trail 5 DV3865-602",
      productUrl: "",
      brand: "Nike"
    })
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}
```

### 铸造 NFT

```ts
async function mintReceipt(analyzeResult: any, to: string) {
  const response = await fetch("http://localhost:8000/api/receipts/mint", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      to,
      productName: analyzeResult.productName,
      brand: analyzeResult.brand,
      score: analyzeResult.score,
      grade: analyzeResult.grade,
      reportHash: analyzeResult.reportHash,
      evidenceMerkleRoot: analyzeResult.evidenceMerkleRoot,
      metadataURI: analyzeResult.metadataURI
    })
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}
```
